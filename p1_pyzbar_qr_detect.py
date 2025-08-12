# -*- coding: utf-8 -*-
"""
p1_pyzbar_qr_detect.py
pyzbarライブラリを使用したQRコード検出スクリプト
- pyzbarはより強力なQRコード検出機能を持つ
- 複数の前処理手法
- 詳細なデバッグ情報
"""
import cv2
import numpy as np
from pathlib import Path
from urllib.parse import parse_qsl, unquote_plus
import unicodedata
import re
from pyzbar import pyzbar
from PIL import Image

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

def load_image_pyzbar(path: Path):
    """pyzbar用画像読み込み"""
    try:
        # PILで読み込み
        pil_img = Image.open(path)
        return pil_img
    except Exception as e:
        print(f"[ERR] PIL読み込み失敗: {e}")
        return None

def preprocess_for_pyzbar(img):
    """pyzbar用前処理"""
    variants = []
    
    # 元画像
    variants.append(("original", img))
    
    # グレースケール変換
    if img.mode != 'L':
        gray = img.convert('L')
        variants.append(("gray", gray))
    else:
        gray = img
        variants.append(("gray", gray))
    
    # 複数のスケール
    for scale in [0.5, 0.75, 1.25, 1.5, 2.0]:
        w, h = img.size
        new_w, new_h = int(w * scale), int(h * scale)
        scaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        variants.append((f"scale_{scale}", scaled))
        
        # スケールしたグレースケール
        if scaled.mode != 'L':
            scaled_gray = scaled.convert('L')
            variants.append((f"scale_{scale}_gray", scaled_gray))
    
    # コントラスト強調
    for name, variant in [("original", img), ("gray", gray)]:
        # ヒストグラム平坦化
        if variant.mode == 'L':
            enhanced = variant.point(lambda x: int(255 * (x / 255) ** 0.7))
            variants.append((f"{name}_enhanced", enhanced))
    
    # 二値化
    for name, variant in [("original", img), ("gray", gray)]:
        if variant.mode == 'L':
            # 適応的二値化（簡易版）
            threshold = np.array(variant).mean()
            binary = variant.point(lambda x: 0 if x < threshold else 255)
            variants.append((f"{name}_binary", binary))
            
            # 反転
            binary_inv = variant.point(lambda x: 255 if x < threshold else 0)
            variants.append((f"{name}_binary_inv", binary_inv))
    
    return variants

def detect_qr_pyzbar(path: Path):
    """pyzbarを使用したQRコード検出"""
    img = load_image_pyzbar(path)
    if img is None:
        print(f"[ERR] 画像読み込み失敗: {path}")
        return None
    
    variants = preprocess_for_pyzbar(img)
    print(f"[INFO] {path.name}: {len(variants)}種類の前処理を試行中...")
    
    for i, (name, variant) in enumerate(variants):
        try:
            # pyzbarでQRコード検出
            barcodes = pyzbar.decode(variant)
            
            for barcode in barcodes:
                data = barcode.data.decode('utf-8')
                barcode_type = barcode.type
                
                if barcode_type == 'QRCODE' and len(data.strip()) > 10:
                    print(f"[SUCCESS] pyzbar検出成功 ({name}): {data[:50]}...")
                    return data
                elif barcode_type == 'QRCODE':
                    print(f"[INFO] QRコード検出 (短すぎる): {data}")
                else:
                    print(f"[INFO] 他のバーコード検出 ({barcode_type}): {data[:30]}...")
                    
        except Exception as e:
            print(f"[DEBUG] {name}でエラー: {e}")
            continue
    
    print(f"[FAIL] pyzbar全前処理で検出失敗: {path.name}")
    return None

def detect_qr_opencv_enhanced(path: Path):
    """OpenCV強化版（pyzbarと併用）"""
    try:
        img = cv2.imread(str(path))
        if img is None:
            return None
        
        # より多くの前処理バリエーション
        variants = []
        
        # 元画像
        variants.append(img)
        variants.append(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        
        # より細かいスケール
        for scale in [0.3, 0.4, 0.6, 0.8, 1.2, 1.4, 1.6, 1.8, 2.2, 2.5]:
            h, w = img.shape[:2]
            new_h, new_w = int(h * scale), int(w * scale)
            scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            variants.append(scaled)
            variants.append(cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY))
        
        # より強力なコントラスト強調
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        variants.append(enhanced)
        
        # ガウシアンブラーでノイズ除去
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        variants.append(blurred)
        
        # メディアンフィルタ
        median = cv2.medianBlur(gray, 5)
        variants.append(median)
        
        det = cv2.QRCodeDetector()
        
        for i, variant in enumerate(variants):
            try:
                data, pts, _ = det.detectAndDecode(variant)
                if data and len(data.strip()) > 10:
                    print(f"[SUCCESS] OpenCV強化検出成功 (variant {i}): {data[:50]}...")
                    return data
                
                retval, decoded_info, _, _ = det.detectAndDecodeMulti(variant)
                if retval and decoded_info:
                    for d in decoded_info:
                        if d and len(d.strip()) > 10:
                            print(f"[SUCCESS] OpenCV強化複数検出成功 (variant {i}): {d[:50]}...")
                            return d
            except Exception:
                continue
        
        return None
        
    except Exception as e:
        print(f"[ERR] OpenCV強化版エラー: {e}")
        return None

def parse_qr_payload(text: str):
    """QRコード内容解析"""
    if not text:
        return None
    
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
    
    print("=== pyzbar + OpenCV強化版QRコード検出開始 ===")
    
    for file_path in target_files:
        path = Path(file_path)
        if not path.exists():
            print(f"[ERR] ファイル不存在: {file_path}")
            continue
        
        print(f"\n--- {path.name} ---")
        
        # 方法1: pyzbar
        print("[METHOD 1] pyzbar試行中...")
        qr_text = detect_qr_pyzbar(path)
        
        # 方法2: OpenCV強化版
        if not qr_text:
            print("[METHOD 2] OpenCV強化版試行中...")
            qr_text = detect_qr_opencv_enhanced(path)
        
        if qr_text:
            result = parse_qr_payload(qr_text)
            print(f"[RESULT] {path.name}:")
            print(f"  患者ID: {result['patient_id']}")
            print(f"  診察日: {result['visit_date']}")
            print(f"  患者名: {result['patient_name']}")
            print(f"  QR文字数: {len(result['full_text'])}")
        else:
            print(f"[RESULT] {path.name}: 全方法で検出失敗")
    
    print("\n=== 検出完了 ===")

if __name__ == "__main__":
    main()
