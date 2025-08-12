@'
# -*- coding: utf-8 -*-
"""
UNKNOWN修復ツール（最小安定版）:
- Patients 以下で 'UNKNOWN' を含む画像を探索
- QR再読取（URLクエリ解析）、EXIF/ファイル名で日付補完
- --apply 指定時に {PID}/{YYYY-MM-DD}/raw へ移動
- master.csv の patient_id / visit_date / source_relpath を sha1 で更新
"""

import argparse, csv, hashlib, os, re, sys, shutil
from pathlib import Path
from datetime import datetime
from dateutil import parser as dtparser
from urllib.parse import parse_qsl

import numpy as np
import cv2
from PIL import Image, ExifTags

IMG_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".webp"}
PID_KEYS  = ["pidnum","pid","patient_id","patient","patid","mrn","id","no"]
DATE_KEYS = ["cdate","date","visit","visit_date","day","surg","surgery_date","dt","tm","tmstamp"]

def sha1_file(path: Path, chunk=1024*1024):
    h = hashlib.sha1()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()

def normalize_date(s: str):
    if not s: return None
    s = s.strip()
    if re.fullmatch(r"20\\d{6}", s):  # 20250809
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    try:
        return dtparser.parse(s).date().isoformat()
    except Exception:
        return None

def read_exif_date(path: Path):
    try:
        img = Image.open(path)
        exif = img._getexif() or {}
        tagmap = {ExifTags.TAGS.get(k, k): v for k, v in (exif or {}).items()}
    except Exception:
        return None
    for key in ("DateTimeOriginal","DateTimeDigitized","DateTime"):
        if key in tagmap:
            val = str(tagmap[key]).replace(":", "-", 2)
            try:
                return dtparser.parse(val).date().isoformat()
            except Exception:
                pass
    return None

def load_gray_for_qr(path: Path):
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

def detect_qr_text(path: Path):
    img = load_gray_for_qr(path)
    if img is None:
        return None
    det = cv2.QRCodeDetector()
    for scale in (1.0, 1.5, 2.0):
        work = img
        if scale != 1.0:
            h, w = img.shape[:2]
            work = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)
        for trial in (work, cv2.adaptiveThreshold(work,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,5)):
            data, pts, _ = det.detectAndDecode(trial)
            if data:
                return data
    return None

def parse_qr_payload(text: str):
    qs = text.lstrip('?&')
    kv = {k.lower(): v for k, v in parse_qsl(qs, keep_blank_values=True)}
    pid = None
    for k in PID_KEYS:
        if k in kv and kv[k] and kv[k].lower() not in PID_KEYS:
            pid = kv[k]; break
    date = None
    for k in DATE_KEYS:
        if k in kv and kv[k]:
            raw = kv[k].split()[0]  # "20250809 115450" → "20250809"
            date = normalize_date(raw)
            if date: break
    if not date:
        m = re.search(r"(20\\d{2})[^\\d]?([01]?\\d)[^\\d]?([0-3]?\\d)", text)
        if m:
            try:
                date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date().isoformat()
            except Exception:
                pass
    return pid, date

def ensure_dirs(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def safe_name(orig_name: str, dest_dir: Path) -> str:
    base, ext = os.path.splitext(orig_name)
    cand = orig_name; i = 1
    while (dest_dir / cand).exists():
        cand = f"{base}_{i}{ext}"; i += 1
    return cand

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients-root", required=True)
    ap.add_argument("--master-csv", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    patients_root = Path(args.patients_root)
    master_csv = Path(args.master_csv)

    rows = []; by_sha1 = {}
    if master_csv.exists():
        with master_csv.open("r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                rows.append(row)
                s = (row.get("sha1") or "").lower()
                if s: by_sha1[s] = row
    else:
        print(f"[ERR] master.csv not found: {master_csv}"); sys.exit(1)

    candidates = [p for p in patients_root.rglob("*")
                  if p.is_file() and p.suffix.lower() in IMG_EXTS and "UNKNOWN" in str(p)]

    if not candidates:
        print("[INFO] UNKNOWN を含む画像は見つかりませんでした。")
        return

    fixed = 0; moved = 0
    for path in candidates:
        try:
            sha1 = sha1_file(path).lower()
            qr = detect_qr_text(path)
            pid = date = None
            if qr:
                pid, date = parse_qr_payload(qr)
            if not date:
                date = read_exif_date(path) or date
                if not date:
                    m = re.search(r"(20\\d{2})[-_\\.]?(0?\\d)[-_\\.]?(0?\\d)", path.name)
                    if m:
                        try:
                            date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date().isoformat()
                        except Exception:
                            pass
            if not pid and not date:
                print(f"[SKIP] {path} :: QR/EXIF/名前から特定できず"); continue

            pid_final  = pid if pid else "UNKNOWN"
            date_final = date if date else "UNKNOWN"
            dest_dir   = patients_root / pid_final / date_final / "raw"
            dest_path  = dest_dir / safe_name(path.name, dest_dir)

            row = by_sha1.get(sha1)
            if row:
                if pid:  row["patient_id"] = pid
                if date: row["visit_date"] = date
                row["source_relpath"] = str((dest_dir / path.name).relative_to(patients_root))
                fixed += 1

            print(f"[FIX] {path}  ->  PID={pid_final}  DATE={date_final}  DEST={dest_path}")
            if args.apply:
                ensure_dirs(dest_dir)
                shutil.move(str(path), str(dest_path))
                moved += 1

        except Exception as e:
            print(f"[ERR] {path}: {e}")

    if args.apply and fixed:
        header = list(rows[0].keys()) if rows else []
        with master_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader(); w.writerows(rows)

    print(f"Done. targets={len(candidates)}, fixed_rows={fixed}, moved_files={moved}, apply={args.apply}")

if __name__ == "__main__":
    main()
'@ | Set-Content -Encoding UTF8 .\p1_repair_unknown.py
