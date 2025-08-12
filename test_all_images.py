import cv2
import numpy as np
import os
import glob
from complete_patient_decoder import decode_patient_name, parse_qr_data

# QRコード検出器を初期化
qr_detector = cv2.QRCodeDetector()

# test_imagesフォルダの画像ファイル
image_dir = "test_images"
image_files = glob.glob(os.path.join(image_dir, "*.JPG"))

print(f"=== 全画像QRコード読み取りテスト ===")
print(f"テスト対象画像数: {len(image_files)}")

# 各画像でQRコード読み取りを試行
for i, image_path in enumerate(image_files):
    print(f"\n{'='*60}")
    print(f"--- 画像 {i+1}: {os.path.basename(image_path)} ---")
    print(f"{'='*60}")
    
    # 画像を読み込み
    image = cv2.imread(image_path)
    
    if image is None:
        print("❌ 画像の読み込みに失敗")
        continue
    
    h, w = image.shape[:2]
    print(f"画像サイズ: {w}x{h}")
    
    # 1. 元の画像でQRコード検出
    data, bbox, straight_qrcode = qr_detector.detectAndDecode(image)
    
    if data:
        print(f"✅ 元画像でQRコード検出成功")
        print(f"生データ: {data}")
        
        # 患者情報を解析
        patient_info = parse_qr_data(data)
        print(f"患者ID: {patient_info.get('pidnum', 'N/A')}")
        print(f"患者名(文字化け): {patient_info.get('pname', 'N/A')}")
        print(f"患者名(修正後): {patient_info.get('pname_corrected', 'N/A')}")
        print(f"日付: {patient_info.get('cdate', 'N/A')}")
        print(f"タイムスタンプ: {patient_info.get('tmstamp', 'N/A')}")
        
    else:
        print("❌ 元画像でのQR読み取り失敗")
        
        # 2. 複数のスケールで試行
        print("\n--- スケール変更を試行 ---")
        scales = [0.5, 0.75, 1.25, 1.5, 2.0, 2.5, 3.0]
        
        for scale in scales:
            new_width = int(w * scale)
            new_height = int(h * scale)
            resized = cv2.resize(image, (new_width, new_height))
            
            data_scaled, bbox_scaled, straight_qrcode_scaled = qr_detector.detectAndDecode(resized)
            if data_scaled:
                print(f"✅ スケール{scale}でQRコード検出成功")
                print(f"生データ: {data_scaled}")
                
                # 患者情報を解析
                patient_info = parse_qr_data(data_scaled)
                print(f"患者ID: {patient_info.get('pidnum', 'N/A')}")
                print(f"患者名(文字化け): {patient_info.get('pname', 'N/A')}")
                print(f"患者名(修正後): {patient_info.get('pname_corrected', 'N/A')}")
                print(f"日付: {patient_info.get('cdate', 'N/A')}")
                print(f"タイムスタンプ: {patient_info.get('tmstamp', 'N/A')}")
                break
            else:
                print(f"❌ スケール{scale}でもQR読み取り失敗")
        
        # 3. 画像前処理を試行
        if not data_scaled:
            print("\n--- 画像前処理を試行 ---")
            
            # グレースケール変換
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # CLAHE
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced_clahe = clahe.apply(gray)
            
            # ヒストグラム平坦化
            enhanced_hist = cv2.equalizeHist(gray)
            
            # ノイズ除去
            denoised = cv2.fastNlMeansDenoising(gray)
            
            # エッジ強調
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(gray, -1, kernel)
            
            # 二値化
            _, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            binary_adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            
            # 各前処理結果でQRコード検出を試行
            preprocessed_images = [
                ("CLAHE", enhanced_clahe),
                ("ヒストグラム平坦化", enhanced_hist),
                ("ノイズ除去", denoised),
                ("エッジ強調", sharpened),
                ("Otsu二値化", binary_otsu),
                ("適応的二値化", binary_adaptive)
            ]
            
            for name, processed_img in preprocessed_images:
                data_processed, bbox_processed, straight_qrcode_processed = qr_detector.detectAndDecode(processed_img)
                if data_processed:
                    print(f"✅ {name}でQRコード検出成功")
                    print(f"生データ: {data_processed}")
                    
                    # 患者情報を解析
                    patient_info = parse_qr_data(data_processed)
                    print(f"患者ID: {patient_info.get('pidnum', 'N/A')}")
                    print(f"患者名(文字化け): {patient_info.get('pname', 'N/A')}")
                    print(f"患者名(修正後): {patient_info.get('pname_corrected', 'N/A')}")
                    print(f"日付: {patient_info.get('cdate', 'N/A')}")
                    print(f"タイムスタンプ: {patient_info.get('tmstamp', 'N/A')}")
                    break
                else:
                    print(f"❌ {name}でもQR読み取り失敗")
    
    print(f"{'='*60}")

print(f"\n=== テスト完了 ===")
print("全ての画像でQRコード読み取りと患者名修正をテストしました。")
