# -*- coding: utf-8 -*-
"""
p1_easyocr_detect.py
EasyOCRを使用した汎用OCRでテキスト検出
- QRコードではなく、画像内のテキストから患者情報を抽出
- 日本語対応
- 複数の前処理手法
"""
import cv2
import numpy as np
from pathlib import Path
from urllib.parse import parse_qsl, unquote_plus
import unicodedata
import re
import easyocr

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

def load_image_easyocr(path: Path):
    """EasyOCR用画像読み込み"""
    try:
        img = cv2.imread(str(path))
        if img is not None:
            return img
    except Exception as e:
        print(f"[ERR] 画像読み込み失敗: {e}")
        return None

def preprocess_for_easyocr(img):
    """EasyOCR用前処理"""
    variants = []
    
    # 元画像
    variants.append(("original", img))
    
    # グレースケール
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    variants.append(("gray", gray))
    
    # 複数のスケール
    for scale in [0.5, 0.75, 1.25, 1.5, 2.0]:
        h, w = img.shape[:2]
        new_h, new_w = int(h * scale), int(w * scale)
        scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        variants.append((f"scale_{scale}", scaled))
        variants.append((f"scale_{scale}_gray", cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)))
    
    # コントラスト強調
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced_gray = clahe.apply(gray)
    variants.append(("enhanced_gray", enhanced_gray))
    
    # ガウシアンブラーでノイズ除去
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    variants.append(("blurred", blurred))
    
    # 二値化
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(("binary", binary))
    variants.append(("binary_inv", cv2.bitwise_not(binary)))
    
    return variants

def extract_patient_info_from_text(text_results):
    """テキスト結果から患者情報を抽出"""
    all_text = " ".join([result[1] for result in text_results])
    print(f"[DEBUG] 検出テキスト: {all_text[:200]}...")
    
    # 患者IDパターン
    pid_patterns = [
        r'患者ID[:\s]*(\d+)',
        r'ID[:\s]*(\d+)',
        r'(\d{4,5})',  # 4-5桁の数字
    ]
    
    # 日付パターン
    date_patterns = [
        r'(\d{4})年(\d{1,2})月(\d{1,2})日',
        r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})',
        r'(\d{8})',  # YYYYMMDD
    ]
    
    # 患者名パターン
    name_patterns = [
        r'患者名[:\s]*([^\s]+)',
        r'氏名[:\s]*([^\s]+)',
        r'([^\s]+)\s*様',
    ]
    
    patient_id = None
    visit_date = None
    patient_name = None
    
    # 患者ID検索
    for pattern in pid_patterns:
        match = re.search(pattern, all_text)
        if match:
            patient_id = match.group(1)
            print(f"[DEBUG] 患者ID検出: {patient_id}")
            break
    
    # 日付検索
    for pattern in date_patterns:
        match = re.search(pattern, all_text)
        if match:
            if len(match.groups()) == 3:
                year, month, day = match.groups()
                visit_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            elif len(match.groups()) == 1:
                date_str = match.group(1)
                if len(date_str) == 8 and date_str.startswith('20'):
                    visit_date = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
            if visit_date:
                print(f"[DEBUG] 日付検出: {visit_date}")
                break
    
    # 患者名検索
    for pattern in name_patterns:
        match = re.search(pattern, all_text)
        if match:
            patient_name = match.group(1)
            print(f"[DEBUG] 患者名検出: {patient_name}")
            break
    
    return {
        "patient_id": patient_id,
        "visit_date": visit_date,
        "patient_name": patient_name,
        "full_text": all_text
    }

def detect_text_easyocr(path: Path):
    """EasyOCRを使用したテキスト検出"""
    img = load_image_easyocr(path)
    if img is None:
        print(f"[ERR] 画像読み込み失敗: {path}")
        return None
    
    # EasyOCR初期化（日本語対応）
    try:
        reader = easyocr.Reader(['ja', 'en'], gpu=False)
    except Exception as e:
        print(f"[ERR] EasyOCR初期化失敗: {e}")
        return None
    
    variants = preprocess_for_easyocr(img)
    print(f"[INFO] {path.name}: {len(variants)}種類の前処理を試行中...")
    
    best_result = None
    best_confidence = 0
    
    for name, variant in variants:
        try:
            print(f"[DEBUG] {name}を処理中...")
            
            # EasyOCRでテキスト検出
            results = reader.readtext(variant)
            
            if results:
                # 信頼度の高い結果を選択
                avg_confidence = np.mean([result[2] for result in results])
                print(f"[DEBUG] {name}: {len(results)}個のテキスト検出、平均信頼度: {avg_confidence:.3f}")
                
                if avg_confidence > best_confidence:
                    best_confidence = avg_confidence
                    best_result = results
                    
                    # 患者情報を抽出
                    patient_info = extract_patient_info_from_text(results)
                    if patient_info["patient_id"] or patient_info["visit_date"] or patient_info["patient_name"]:
                        print(f"[SUCCESS] {name}で患者情報検出成功")
                        return patient_info
            
        except Exception as e:
            print(f"[DEBUG] {name}でエラー: {e}")
            continue
    
    if best_result:
        print(f"[INFO] 最良結果 (信頼度: {best_confidence:.3f})")
        return extract_patient_info_from_text(best_result)
    
    print(f"[FAIL] EasyOCR全前処理で検出失敗: {path.name}")
    return None

def main():
    # 対象画像
    target_files = [
        "Patients/UNKNOWN/UNKNOWN/raw/IMG_7008.JPG",
        "Patients/UNKNOWN/UNKNOWN/raw/IMG_7010.JPG", 
        "Patients/UNKNOWN/UNKNOWN/raw/IMG_7016.JPG"
    ]
    
    print("=== EasyOCR汎用OCRテキスト検出開始 ===")
    
    for file_path in target_files:
        path = Path(file_path)
        if not path.exists():
            print(f"[ERR] ファイル不存在: {file_path}")
            continue
        
        print(f"\n--- {path.name} ---")
        
        result = detect_text_easyocr(path)
        
        if result:
            print(f"[RESULT] {path.name}:")
            print(f"  患者ID: {result['patient_id']}")
            print(f"  診察日: {result['visit_date']}")
            print(f"  患者名: {result['patient_name']}")
            print(f"  テキスト長: {len(result['full_text'])}")
        else:
            print(f"[RESULT] {path.name}: 検出失敗")
    
    print("\n=== 検出完了 ===")

if __name__ == "__main__":
    main()
