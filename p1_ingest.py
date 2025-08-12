# -*- coding: utf-8 -*-
"""
P1: INBOX → QR振り分け → 縦持ちCSV 骨組み（安定強化版）
- 画像(JPG/PNG/HEIC/TIFF/WebP)を走査
- QRから PID/DATE を取得（URLクエリ/混在書式を吸収）
- 日本語氏名などの文字化けを自動修復（Shift_JIS/EUC-JP考慮）
- 検出強化（拡大・自適応二値・反転・形態学処理・マルチQR）
- /Patients/{PID}/{YYYY-MM-DD}/raw へ移動(またはコピー)
- master.csv に縦持ち1行を追記（modality=unknown, eye=NA）
- --qr-debug でログ出力
"""

import argparse, csv, hashlib, os, re, shutil, sys, traceback, unicodedata
from pathlib import Path
from datetime import datetime
from dateutil import parser as dtparser
from urllib.parse import parse_qsl, unquote_plus

import numpy as np
import cv2
from PIL import Image, UnidentifiedImageError, ExifTags

# ---- optional: HEIC 対応（ある場合のみ） ----
try:
    import pillow_heif  # pip install pillow-heif
    pillow_heif.register_heif_opener()
    HEIF_OK = True
except Exception:
    HEIF_OK = False

IMG_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".webp"}

CSV_HEADER = [
    "patient_id","visit_date","modality","eye","eye_source","eye_confidence",
    "iop_c_od","iop_c_os","iop_nct_avg_od","iop_nct_avg_os",
    "va_sc_od","va_sc_os","va_cc_od","va_cc_os",
    "ref_s_od","ref_c_od","ref_ax_od","ref_s_os","ref_c_os","ref_ax_os",
    "preop_dx_norm","planned_proc_norm","planned_proc_eye","planned_proc_score",
    "iol_model","iol_power","iol_serial","iol_eye",
    "qa_flags","full_text","ma_nouns",
    "source_relpath","sha1"
]

PID_KEYS  = ["pidnum","pid","patient_id","patient","patid","mrn","id","no"]
DATE_KEYS = ["cdate","date","visit","visit_date","day","surg","surgery_date","dt","tm","tmstamp"]

def sha1_file(path: Path, chunk=1024*1024):
    h = hashlib.sha1()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()

def read_exif_date(path: Path):
    try:
        img = Image.open(path)  # HEIC は pillow-heif 登録済みなら開ける
        exif = img._getexif() or {}
    except Exception:
        return None
    tagmap = {ExifTags.TAGS.get(k,k): v for k,v in (exif or {}).items()}
    for key in ("DateTimeOriginal","DateTimeDigitized","DateTime"):
        if key in tagmap:
            val = str(tagmap[key]).replace(":", "-", 2)
            try:
                return dtparser.parse(val).date().isoformat()
            except Exception:
                pass
    return None

def normalize_date(s: str):
    if not s: return None
    s = s.strip()
    if re.fullmatch(r"20\d{6}", s):  # 20250809
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    try:
        return dtparser.parse(s).date().isoformat()
    except Exception:
        return None

def repair_mojibake(s: str) -> str:
    """URLデコード→日本語が含まれなければlatin-1経由でSJIS/EUC再デコード"""
    if not s:
        return s
    t = unquote_plus(s)
    if any('\u3040' <= ch <= '\u30ff' or '\u4e00' <= ch <= '\u9fff' for ch in t):
        return unicodedata.normalize("NFC", t)
    raw = s.encode("latin-1", errors="ignore")
    for enc in ("cp932", "shift_jis", "euc_jp"):
        try:
            fixed = raw.decode(enc)
            if any('\u3040' <= ch <= '\u30ff' or '\u4e00' <= ch <= '\u9fff' for ch in fixed):
                return unicodedata.normalize("NFC", fixed)
        except Exception:
            pass
    return unicodedata.normalize("NFC", t)

def parse_qr_payload(text: str):
    """URLクエリ/自由書式から pid/date を柔軟抽出"""
    qs = text.lstrip('?&')
    kv = {k.lower(): v for k, v in parse_qsl(qs, keep_blank_values=True)}
    pid = None
    for k in PID_KEYS:
        if k in kv and kv[k] and kv[k].lower() not in PID_KEYS:
            pid = kv[k]
            break
    date = None
    for k in DATE_KEYS:
        if k in kv and kv[k]:
            raw = kv[k].split()[0]  # "20250809 115450" → "20250809"
            date = normalize_date(raw)
            if date:
                break
    if not (pid and date):
        # 既存混在：12345_20250809 / ID:12345 Date:2025/08/09
        pats = [
            re.compile(r"(?P<pid>[0-9]{3,})[_\-\.](?P<date>20[0-9]{2}[01][0-9][0-3][0-9])"),
            re.compile(r"(?:PID|ID)[:=]?\s*(?P<pid>[0-9A-Za-z_-]+).*?(?:DATE|Date|cdate)[:=]?\s*(?P<date>[0-9]{4}[-/\.][0-9]{1,2}[-/\.][0-9]{1,2})", re.I|re.S),
        ]
        for pat in pats:
            m = pat.search(text)
            if m:
                pid = pid or m.group("pid")
                date = date or normalize_date(m.group("date"))
                break
    return pid, date

def load_gray_for_qr(path: Path):
    """どの形式でもグレースケールnp.arrayを返す（失敗時None）"""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            return img
    except Exception:
        pass
    try:
        pil = Image.open(path).convert("L")
        arr = np.array(pil)
        if arr.ndim == 2:
            return arr
        return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    except Exception:
        return None

def detect_qr(path: Path):
    """拡大・二値・反転・モルフォロジ・マルチQRまで試す"""
    img = load_gray_for_qr(path)
    if img is None:
        return None
    det = cv2.QRCodeDetector()
    variants = []
    for scale in (1.0, 1.5, 2.0):
        base = img if scale == 1.0 else cv2.resize(img, (int(img.shape[1]*scale), int(img.shape[0]*scale)), interpolation=cv2.INTER_CUBIC)
        variants.append(base)
        variants.append(cv2.adaptiveThreshold(base,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,5))
        variants.append(cv2.bitwise_not(base))  # 反転
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        variants.append(cv2.morphologyEx(base, cv2.MORPH_CLOSE, k, iterations=1))
    for work in variants:
        data, pts, _ = det.detectAndDecode(work)
        if data:
            return data
        try:
            retval, decoded_info, _, _ = det.detectAndDecodeMulti(work)
            if retval and decoded_info:
                for d in decoded_info:
                    if d:
                        return d
        except Exception:
            pass
    return None

def ensure_dirs(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def write_header_if_needed(csv_path: Path):
    if not csv_path.exists():
        ensure_dirs(csv_path.parent)
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)

def append_row(csv_path: Path, row: dict):
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([row.get(col, "") for col in CSV_HEADER])

def safe_name(orig_name: str, dest_dir: Path) -> str:
    base, ext = os.path.splitext(orig_name)
    cand = orig_name
    i = 1
    while (dest_dir / cand).exists():
        cand = f"{base}_{i}{ext}"
        i += 1
    return cand

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", required=True)
    ap.add_argument("--patients-root", required=True)
    ap.add_argument("--master-csv", required=True)
    ap.add_argument("--move", action="store_true")
    ap.add_argument("--qr-debug", action="store_true", help="QR解析ログを出す")
    args = ap.parse_args()

    inbox = Path(args.inbox)
    patients_root = Path(args.patients_root)
    master_csv = Path(args.master_csv)

    if not inbox.exists():
        print(f"[ERR] INBOX not found: {inbox}")
        sys.exit(1)

    write_header_if_needed(master_csv)

    # 既存sha1で重複スキップ
    existing_sha1 = set()
    try:
        with master_csv.open("r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                s = row.get("sha1")
                if s: existing_sha1.add(s)
    except Exception:
        pass

    total=ok=dup=err=0

    for path in inbox.rglob("*"):
        if not path.is_file(): 
            continue
        if path.suffix.lower() not in IMG_EXTS:
            continue

        total += 1
        try:
            file_sha1 = sha1_file(path)
            if file_sha1 in existing_sha1:
                dup += 1
                if args.qr_debug:
                    print(f"[SKIP] duplicate: {path.name}")
                continue

            qa = []
            pid = None
            visit_date = None
            eye = "NA"
            eye_source = "unknown"
            eye_conf = 0

            # QR
            qr_text = detect_qr(path)
            if qr_text:
                qr_text = repair_mojibake(qr_text)
                p_pid, p_date = parse_qr_payload(qr_text)
                if p_pid: pid = p_pid
                if p_date: visit_date = p_date
                if args.qr_debug:
                    short = qr_text[:160].replace(os.linesep, " ")
                    print(f"[QR] {path.name} :: raw='{short}'  -> pid={pid} date={visit_date}")
            else:
                qa.append("NO_QR")

            # 日付補完
            if not visit_date:
                exif_date = read_exif_date(path)
                if exif_date:
                    visit_date = exif_date
                    qa.append("DATE_FROM_EXIF")
                else:
                    m = re.search(r"(20\d{2})[-_\.]?(0?\d)[-_\.]?(0?\d)", path.name)
                    if m:
                        try:
                            visit_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date().isoformat()
                            qa.append("DATE_FROM_FILENAME")
                        except Exception:
                            pass
            if not visit_date:
                qa.append("BAD_DATE")

            # フォルダ振り分け
            pid_final = pid if pid else "UNKNOWN"
            date_final = visit_date if visit_date else "UNKNOWN"
            dest_raw = patients_root / pid_final / date_final / "raw"
            ensure_dirs(dest_raw)
            dest_path = dest_raw / safe_name(path.name, dest_raw)

            if args.move:
                shutil.move(str(path), str(dest_path))
            else:
                shutil.copy2(str(path), str(dest_path))

            # CSV追記
            row = {
                "patient_id": pid or "",
                "visit_date": visit_date or "",
                "modality": "unknown",
                "eye": eye,
                "eye_source": eye_source,
                "eye_confidence": eye_conf,
                "iop_c_od": "", "iop_c_os": "",
                "iop_nct_avg_od": "", "iop_nct_avg_os": "",
                "va_sc_od": "", "va_sc_os": "", "va_cc_od": "", "va_cc_os": "",
                "ref_s_od": "", "ref_c_od": "", "ref_ax_od": "",
                "ref_s_os": "", "ref_c_os": "", "ref_ax_os": "",
                "preop_dx_norm": "", "planned_proc_norm": "", "planned_proc_eye": "", "planned_proc_score": "",
                "iol_model": "", "iol_power": "", "iol_serial": "", "iol_eye": "",
                "qa_flags": ",".join(sorted(set(qa))) if qa else "",
                "full_text": (qr_text or ""),
                "ma_nouns": "",
                "source_relpath": str(dest_path.relative_to(patients_root)),
                "sha1": file_sha1,
            }
            append_row(master_csv, row)
            existing_sha1.add(file_sha1)
            ok += 1
            if not args.qr_debug:
                print(f"[OK] {dest_path}")

        except Exception as e:
            err += 1
            print(f"[ERR] {path.name}: {e}")
            traceback.print_exc(limit=1)

    print(f"\nDone. total={total}, ok={ok}, dup={dup}, err={err}")

if __name__ == "__main__":
    main()
