# -*- coding: utf-8 -*-
"""
p1_enhanced_qr_detect.py
強化版QRコード検出スクリプト
- 複数の前処理手法
- 複数のスケール
- エッジ検出ベース
- コントラスト強調
"""
import cv2
import numpy as np
from pathlib import Path
from urllib.parse import parse_qsl, unquote_plus
import unicodedata
import re

def repair_mojibake(s: str) -> str:
    if not s: return s
    t = unquote_plus(s)
    # 既に綺麗ならそのまま
    if any('\u3040' <= ch <= '\u30ff' or '\u4e00' <= ch <= '\u9fff' for ch in t):
        return unicodedata.normalize("NFC", t)
    raw = s.encode("latin-1", errors="ignore")
    for enc in ("cp932","shift_jis","euc_jp"):
        try:
            fixed = raw.decode(enc)
            if any('\u3040' <= ch <= '\u30ff' or '\u4e00' <= ch <= '\u9fff' for ch in fixed):
                return unicodedata.normalize("NFC", fixed)
        except Exception:
            pass
    return unicodedata.normalize("NFC", t)

def load_image_enhanced(path: Path):
    """強化版画像読み込み"""
    try:
        # 複数の方法で画像を読み込み
        data = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is not None:
            return img
    except Exception:
        pass
    
    try:
        img = cv2.imread(str(path))
        if img is not None:
            return img
    except Exception:
        pass
    
    return None

def preprocess_image_enhanced(img):
    """強化版前処理"""
    variants = []
    
    # 元画像
    variants.append(img)
    
    # グレースケール
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    variants.append(gray)
    
    # 複数のスケール
    for scale in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        if scale != 1.0:
            h, w = img.shape[:2]
            new_h, new_w = int(h * scale), int(w * scale)
            scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            variants.append(scaled)
            variants.append(cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY))
    
    # コントラスト強調
    for variant in [img, gray]:
        # CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        if len(variant.shape) == 3:
            lab = cv2.cvtColor(variant, cv2.COLOR_BGR2LAB)
            lab[:,:,0] = clahe.apply(lab[:,:,0])
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            variants.append(enhanced)
            variants.append(cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY))
        else:
            variants.append(clahe.apply(variant))
    
    # エッジ検出ベース
    for variant in [img, gray]:
        if len(variant.shape) == 3:
            variant_gray = cv2.cvtColor(variant, cv2.COLOR_BGR2GRAY)
        else:
            variant_gray = variant
        
        # Cannyエッジ
        edges = cv2.Canny(variant_gray, 50, 150)
        variants.append(edges)
        
        # Sobelエッジ
        sobelx = cv2.Sobel(variant_gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(variant_gray, cv2.CV_64F, 0, 1, ksize=3)
        sobel = np.sqrt(sobelx**2 + sobely**2)
        sobel = np.uint8(sobel * 255 / sobel.max())
        variants.append(sobel)
    
    # 二値化
    for variant in [img, gray]:
        if len(variant.shape) == 3:
            variant_gray = cv2.cvtColor(variant, cv2.COLOR_BGR2GRAY)
        else:
            variant_gray = variant
        
        # 適応的二値化
        binary = cv2.adaptiveThreshold(variant_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        variants.append(binary)
        
        # 反転
        variants.append(cv2.bitwise_not(binary))
        
        # Otsu二値化
        _, otsu = cv2.threshold(variant_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(otsu)
        variants.append(cv2.bitwise_not(otsu))
    
    # モルフォロジー処理
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
    for variant in [img, gray]:
        if len(variant.shape) == 3:
            variant_gray = cv2.cvtColor(variant, cv2.COLOR_BGR2GRAY)
        else:
            variant_gray = variant
        
        # クロージング
        closing = cv2.morphologyEx(variant_gray, cv2.MORPH_CLOSE, kernel)
        variants.append(closing)
        
        # オープニング
        opening = cv2.morphologyEx(variant_gray, cv2.MORPH_OPEN, kernel)
        variants.append(opening)
    
    return variants

def detect_qr_enhanced(path: Path):
    """強化版QRコード検出"""
    img = load_image_enhanced(path)
    if img is None:
        print(f"[ERR] 画像読み込み失敗: {path}")
        return None
    
    variants = preprocess_image_enhanced(img)
    det = cv2.QRCodeDetector()
    
    print(f"[INFO] {path.name}: {len(variants)}種類の前処理を試行中...")
    
    for i, variant in enumerate(variants):
        try:
            # 単一QRコード検出
            data, pts, _ = det.detectAndDecode(variant)
            if data and len(data.strip()) > 10:  # 最低10文字以上
                print(f"[SUCCESS] 単一QR検出成功 (variant {i}): {data[:50]}...")
                return data
            
            # 複数QRコード検出
            retval, decoded_info, _, _ = det.detectAndDecodeMulti(variant)
            if retval and decoded_info:
                for d in decoded_info:
                    if d and len(d.strip()) > 10:
                        print(f"[SUCCESS] 複数QR検出成功 (variant {i}): {d[:50]}...")
                        return d
        except Exception as e:
            continue
    
    print(f"[FAIL] 全前処理で検出失敗: {path.name}")
    return None

def parse_qr_payload(text: str):
    """QRコード内容解析"""
    if not text:
        return None, None
    
    # URLデコード
    text = repair_mojibake(text)
    
    # クエリパラメータ解析
    qs = text.lstrip('?&')
    kv = {k.lower(): v for k,v in parse_qsl(qs, keep_blank_values=True)}
    
    # 患者ID取得
    pid = None
    for k in ["pidnum", "pid", "patient_id", "patient", "patid", "mrn", "id", "no"]:
        if k in kv and kv[k] and kv[k].lower() not in ["pidnum", "pid", "patient_id", "patient", "patid", "mrn", "id", "no"]:
            pid = kv[k]
            break
    
    # 日付取得
    date = None
    for k in ["cdate", "date", "visit", "visit_date", "day", "surg", "surgery_date", "dt", "tm", "tmstamp"]:
        if k in kv and kv[k]:
            raw = kv[k].split()[0]
            # YYYYMMDD形式をYYYY-MM-DDに変換
            if re.fullmatch(r"20\d{6}", raw):
                date = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
                break
    
    # 患者名取得
    pname = kv.get("pname", "")
    
    return {
        "patient_id": pid,
        "visit_date": date,
        "patient_name": pname,
        "full_text": text
    }

def main():
    # 対象画像
    target_files = [
        "Patients/UNKNOWN/UNKNOWN/raw/IMG_7008.JPG",
        "Patients/UNKNOWN/UNKNOWN/raw/IMG_7010.JPG", 
        "Patients/UNKNOWN/UNKNOWN/raw/IMG_7016.JPG"
    ]
    
    print("=== 強化版QRコード検出開始 ===")
    
    for file_path in target_files:
        path = Path(file_path)
        if not path.exists():
            print(f"[ERR] ファイル不存在: {file_path}")
            continue
        
        print(f"\n--- {path.name} ---")
        qr_text = detect_qr_enhanced(path)
        
        if qr_text:
            result = parse_qr_payload(qr_text)
            print(f"[RESULT] {path.name}:")
            print(f"  患者ID: {result['patient_id']}")
            print(f"  診察日: {result['visit_date']}")
            print(f"  患者名: {result['patient_name']}")
            print(f"  QR文字数: {len(result['full_text'])}")
        else:
            print(f"[RESULT] {path.name}: 検出失敗")
    
    print("\n=== 検出完了 ===")

if __name__ == "__main__":
    main()
