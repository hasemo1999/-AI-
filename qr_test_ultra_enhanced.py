import cv2
import numpy as np
import os
from complete_patient_decoder import parse_qr_data

def ultra_enhanced_qr_detection(image_path):
    """超高性能QRコード検出システム"""
    # 画像を読み込み（日本語パス対応）
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    
    if image is None:
        return None, "画像の読み込みに失敗"
    
    qr_detector = cv2.QRCodeDetector()
    h, w = image.shape[:2]
    
    # 1. 元画像での検出
    data, bbox, straight_qrcode = qr_detector.detectAndDecode(image)
    if data:
        return data, "元画像で成功"
    
    # 2. グレースケール変換
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 3. 複数の前処理手法を試行
    preprocessing_methods = [
        ("CLAHE", lambda img: cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8)).apply(img)),
        ("ヒストグラム平坦化", lambda img: cv2.equalizeHist(img)),
        ("ガウシアンブラー", lambda img: cv2.GaussianBlur(img, (5,5), 0)),
        ("メディアンフィルタ", lambda img: cv2.medianBlur(img, 5)),
        ("バイラテラルフィルタ", lambda img: cv2.bilateralFilter(img, 9, 75, 75)),
        ("ノイズ除去", lambda img: cv2.fastNlMeansDenoising(img)),
        ("エッジ強調", lambda img: cv2.filter2D(img, -1, np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]]))),
        ("アダプティブ閾値", lambda img: cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)),
        ("Otsu二値化", lambda img: cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]),
        ("モルフォロジー処理", lambda img: cv2.morphologyEx(img, cv2.MORPH_CLOSE, np.ones((3,3), np.uint8))),
    ]
    
    # 各前処理手法で検出
    for method_name, process_func in preprocessing_methods:
        try:
            processed = process_func(gray)
            data, bbox, straight_qrcode = qr_detector.detectAndDecode(processed)
            if data:
                return data, f"{method_name}で成功"
        except:
            continue
    
    # 4. 複数のスケールで前処理を組み合わせ
    scales = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.1, 1.2, 1.3, 1.4, 1.5, 1.8, 2.0, 2.5, 3.0, 3.5, 4.0]
    
    for scale in scales:
        new_width = int(w * scale)
        new_height = int(h * scale)
        resized = cv2.resize(image, (new_width, new_height))
        
        # 元のサイズで検出
        data, bbox, straight_qrcode = qr_detector.detectAndDecode(resized)
        if data:
            return data, f"スケール{scale}で成功"
        
        # スケール変更 + 前処理
        resized_gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        
        for method_name, process_func in preprocessing_methods:
            try:
                processed = process_func(resized_gray)
                data, bbox, straight_qrcode = qr_detector.detectAndDecode(processed)
                if data:
                    return data, f"スケール{scale}+{method_name}で成功"
            except:
                continue
    
    # 5. 回転を試行
    angles = [90, 180, 270, -90, -180, -270]
    for angle in angles:
        try:
            # 回転行列を計算
            center = (w // 2, h // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(image, rotation_matrix, (w, h))
            
            data, bbox, straight_qrcode = qr_detector.detectAndDecode(rotated)
            if data:
                return data, f"回転{angle}度で成功"
        except:
            continue
    
    # 6. ROI（関心領域）の抽出を試行
    # 画像の中心部分を切り出し
    roi_margins = [0.1, 0.2, 0.3, 0.4]
    for margin in roi_margins:
        try:
            margin_pixels = int(min(w, h) * margin)
            roi = image[margin_pixels:h-margin_pixels, margin_pixels:w-margin_pixels]
            
            data, bbox, straight_qrcode = qr_detector.detectAndDecode(roi)
            if data:
                return data, f"ROI切り出し{margin}で成功"
        except:
            continue
    
    return None, "全ての手法で検出失敗"

def test_ultra_enhanced_system():
    """超高性能システムのテスト"""
    print("=== 超高性能QRコード検出システム ===")
    
    # テスト対象の画像（失敗した画像を中心に）
    test_images = [
        "IMG_7001.JPG",
        "IMG_7008.JPG", 
        "IMG_7015.JPG",
        "IMG_7010.JPG",
        "IMG_7016.JPG"
    ]
    
    # Googleドライブパス
    drive_path = r"G:\マイドライブ\INBOX"
    
    success_count = 0
    
    for image_name in test_images:
        image_path = os.path.join(drive_path, image_name)
        
        if not os.path.exists(image_path):
            print(f"❌ ファイルが見つかりません: {image_name}")
            continue
        
        print(f"\n{'='*60}")
        print(f"--- 超高性能検出: {image_name} ---")
        print(f"{'='*60}")
        
        # 超高性能検出を実行
        qr_data, status = ultra_enhanced_qr_detection(image_path)
        
        if qr_data:
            print(f"✅ 検出成功: {status}")
            print(f"生データ: {qr_data}")
            
            # 患者情報を解析
            patient_info = parse_qr_data(qr_data)
            print(f"患者ID: {patient_info.get('pidnum', 'N/A')}")
            print(f"患者名(文字化け): {patient_info.get('pname', 'N/A')}")
            print(f"患者名(修正後): {patient_info.get('pname_corrected', 'N/A')}")
            print(f"日付: {patient_info.get('cdate', 'N/A')}")
            print(f"タイムスタンプ: {patient_info.get('tmstamp', 'N/A')}")
            success_count += 1
        else:
            print(f"❌ 検出失敗: {status}")
        
        print(f"{'='*60}")
    
    print(f"\n=== 超高性能システム結果 ===")
    print(f"テスト画像数: {len(test_images)}")
    print(f"検出成功: {success_count}")
    print(f"成功率: {success_count/len(test_images)*100:.1f}%")

if __name__ == '__main__':
    test_ultra_enhanced_system()
