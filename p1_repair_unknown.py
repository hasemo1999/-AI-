# -*- coding: utf-8 -*-
"""
UNKNOWN フォルダの画像を再処理して正しい患者ID・日付に振り分ける
"""
import argparse, csv, hashlib, os, re, sys, shutil
from pathlib import Path
from datetime import datetime
from dateutil import parser as dtparser
import numpy as np
import cv2
from PIL import Image, ExifTags

# 設定
IMG_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".webp"}

def sha1_file(path: Path, chunk=1024*1024):
    """ファイルのSHA1ハッシュを計算"""
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def normalize_date(s: str):
    """日付文字列を YYYY-MM-DD 形式に正規化"""
    if not s: return None
    s = s.strip()
    # 20250809 → 2025-08-09
    if re.fullmatch(r"20\d{6}", s):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    try:
        return dtparser.parse(s).date().isoformat()
    except Exception:
        return None

def read_exif_date(path: Path):
    """画像のEXIFから日付を取得"""
    try:
        img = Image.open(path)
        exif = img._getexif() or {}
        tagmap = {ExifTags.TAGS.get(k, k): v for k, v in (exif or {}).items()}
    except Exception:
        return None
    
    for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
        if key in tagmap:
            val = str(tagmap[key]).replace(":", "-", 2)
            try:
                return dtparser.parse(val).date().isoformat()
            except Exception:
                pass
    return None

def detect_qr_text(path: Path):
    """QRコードを読み取る"""
    try:
        # OpenCVで画像読み込み
        img = cv2.imread(str(path))
        if img is None:
            return None
        
        # QRコード検出器
        det = cv2.QRCodeDetector()
        
        # そのまま試す
        data, pts, _ = det.detectAndDecode(img)
        if data:
            return data
        
        # グレースケールで再試行
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        data, pts, _ = det.detectAndDecode(gray)
        if data:
            return data
            
    except Exception as e:
        print(f"  [QRエラー] {path.name}: {e}")
    
    return None

def parse_qr_payload(text: str):
    """QRコードの内容から患者IDと日付を抽出"""
    pid = None
    date = None
    
    # デバッグ出力
    print(f"  [QR内容] {text[:200]}")
    
    # パターン1: カンマ区切り（31742,田中太郎,2025-08-09）
    parts = text.split(',')
    if len(parts) >= 2:
        # 最初の要素が数字なら患者ID
        if parts[0].strip().isdigit():
            pid = parts[0].strip()
            # 日付を探す
            for part in parts:
                d = normalize_date(part.strip())
                if d:
                    date = d
                    break
    
    # パターン2: 5桁の数字を患者IDとして探す
    if not pid:
        m = re.search(r'\b(\d{5})\b', text)
        if m:
            pid = m.group(1)
    
    # パターン3: 日付パターンを探す
    if not date:
        patterns = [
            r'(20\d{2}[-/年]\d{1,2}[-/月]\d{1,2})',
            r'(20\d{6})',  # 20250809
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                date = normalize_date(m.group(1))
                if date:
                    break
    
    return pid, date

def ensure_dirs(p: Path):
    """ディレクトリを作成"""
    p.mkdir(parents=True, exist_ok=True)

def safe_name(orig_name: str, dest_dir: Path) -> str:
    """重複しないファイル名を生成"""
    base, ext = os.path.splitext(orig_name)
    cand = orig_name
    i = 1
    while (dest_dir / cand).exists():
        cand = f"{base}_{i}{ext}"
        i += 1
    return cand

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients-root", required=True, help="Patientsフォルダ")
    ap.add_argument("--master-csv", required=True, help="master.csvのパス")
    ap.add_argument("--apply", action="store_true", help="実際に移動を実行")
    args = ap.parse_args()
    
    patients_root = Path(args.patients_root)
    master_csv = Path(args.master_csv)
    
    # 既存のCSVを読み込み
    rows = []
    by_sha1 = {}
    if master_csv.exists():
        with master_csv.open("r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                rows.append(row)
                s = (row.get("sha1") or "").lower()
                if s:
                    by_sha1[s] = row
    
    # UNKNOWNフォルダ内の画像を探す
    candidates = []
    for p in patients_root.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMG_EXTS and "UNKNOWN" in str(p):
            candidates.append(p)
    
    if not candidates:
        print("[INFO] UNKNOWNフォルダに画像が見つかりませんでした")
        return
    
    print(f"[INFO] {len(candidates)}個のUNKNOWN画像を処理します")
    
    fixed = 0
    moved = 0
    
    for path in candidates:
        print(f"\n処理中: {path.name}")
        
        try:
            # SHA1ハッシュ計算
            sha1 = sha1_file(path).lower()
            
            # QRコード読み取り
            qr = detect_qr_text(path)
            
            pid = None
            date = None
            
            if qr:
                pid, date = parse_qr_payload(qr)
                print(f"  → PID={pid}, DATE={date}")
            else:
                print(f"  → QRコードなし")
            
            # 日付が取れなければEXIFから
            if not date:
                date = read_exif_date(path)
                if date:
                    print(f"  → EXIF日付: {date}")
            
            # それでもダメならファイル名から
            if not date:
                m = re.search(r"(20\d{2})[-_\.]?(0?\d)[-_\.]?(0?\d)", path.name)
                if m:
                    try:
                        date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date().isoformat()
                        print(f"  → ファイル名から日付: {date}")
                    except:
                        pass
            
            # 何も取れなければスキップ
            if not pid and not date:
                print(f"  [SKIP] 患者IDも日付も特定できません")
                continue
            
            # 移動先を決定
            pid_final = pid if pid else "UNKNOWN"
            date_final = date if date else "UNKNOWN"
            dest_dir = patients_root / pid_final / date_final / "raw"
            dest_path = dest_dir / safe_name(path.name, dest_dir)
            
            print(f"  [修正] → {pid_final}/{date_final}/")
            
            # CSV更新
            row = by_sha1.get(sha1)
            if row:
                if pid:
                    row["patient_id"] = pid
                if date:
                    row["visit_date"] = date
                row["source_relpath"] = str(dest_path.relative_to(patients_root))
                fixed += 1
            
            # 実際に移動
            if args.apply:
                ensure_dirs(dest_dir)
                shutil.move(str(path), str(dest_path))
                moved += 1
                print(f"  [移動完了]")
            
        except Exception as e:
            print(f"  [エラー] {e}")
    
    # CSV保存
    if args.apply and fixed > 0:
        header = list(rows[0].keys()) if rows else []
        with master_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(rows)
        print(f"\n[CSV更新] {fixed}行を修正")
    
    print(f"\n完了: 対象={len(candidates)}, CSV修正={fixed}, ファイル移動={moved}")
    if not args.apply:
        print("※ --apply を付けて実行すると実際に移動します")

if __name__ == "__main__":
    main()