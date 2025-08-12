# -*- coding: utf-8 -*-
"""
p1_easyocr_detect_img7015.py
IMG_7015.JPG専用のEasyOCR検出スクリプト
"""
import cv2
import numpy as np
from pathlib import Path
import re
import easyocr

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
    try:
        img = cv2.imread(str(path))
        if img is None:
            print(f"[ERR] 画像読み込み失敗: {path}")
            return None
    except Exception as e:
        print(f"[ERR] 画像読み込み失敗: {e}")
        return None
    
    # EasyOCR初期化（日本語対応）
    try:
        reader = easyocr.Reader(['ja', 'en'], gpu=False)
    except Exception as e:
        print(f"[ERR] EasyOCR初期化失敗: {e}")
        return None
    
    print(f"[INFO] {path.name}: EasyOCR処理中...")
    
    try:
        # EasyOCRでテキスト検出
        results = reader.readtext(img)
        
        if results:
            # 信頼度の高い結果を選択
            avg_confidence = np.mean([result[2] for result in results])
            print(f"[DEBUG] {len(results)}個のテキスト検出、平均信頼度: {avg_confidence:.3f}")
            
            # 患者情報を抽出
            patient_info = extract_patient_info_from_text(results)
            return patient_info
        else:
            print(f"[DEBUG] テキスト検出なし")
            return None
            
    except Exception as e:
        print(f"[DEBUG] EasyOCR処理エラー: {e}")
        return None

def main():
    # IMG_7015.JPGのみ対象
    target_file = "Patients/UNKNOWN/UNKNOWN/raw/IMG_7015.JPG"
    
    print("=== IMG_7015.JPG EasyOCR検出開始 ===")
    
    path = Path(target_file)
    if not path.exists():
        print(f"[ERR] ファイル不存在: {target_file}")
        return
    
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
