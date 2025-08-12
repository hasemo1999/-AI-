import cv2
import numpy as np
import os
from complete_patient_decoder import parse_qr_data

def enhanced_qr_detection_with_pyzbar(image_path):
    """pyzbarとOpenCVを組み合わせた高精度QRコード検出"""
    # 画像を読み込み（日本語パス対応）
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    
    if image is None:
        return None, "画像の読み込みに失敗"
    
    h, w = image.shape[:2]
    
    # 1. OpenCV QRCodeDetector（元画像）
    try:
        qr_detector = cv2.QRCodeDetector()
        data, bbox, straight_qrcode = qr_detector.detectAndDecode(image)
        if data:
            return data, "OpenCV元画像で成功"
    except:
        pass
    
    # 2. pyzbar（元画像）
    try:
        from pyzbar import pyzbar
        from PIL import Image
        
        # OpenCV画像をPIL画像に変換
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        
        decoded = pyzbar.decode(pil_image)
        if decoded:
            data = decoded[0].data.decode('utf-8')
            return data, "pyzbar元画像で成功"
    except:
        pass
    
    # 3. グレースケール変換
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 4. 前処理手法（軽量版）
    preprocessing_methods = [
        ("CLAHE", lambda img: cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8)).apply(img)),
        ("ヒストグラム平坦化", lambda img: cv2.equalizeHist(img)),
        ("ガウシアンブラー", lambda img: cv2.GaussianBlur(img, (5,5), 0)),
        ("ノイズ除去", lambda img: cv2.fastNlMeansDenoising(img)),
        ("エッジ強調", lambda img: cv2.filter2D(img, -1, np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]]))),
        ("アダプティブ閾値", lambda img: cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)),
    ]
    
    # 各前処理手法で検出
    for method_name, process_func in preprocessing_methods:
        try:
            processed = process_func(gray)
            
            # OpenCV
            data, bbox, straight_qrcode = qr_detector.detectAndDecode(processed)
            if data:
                return data, f"OpenCV+{method_name}で成功"
            
            # pyzbar
            pil_processed = Image.fromarray(processed)
            decoded = pyzbar.decode(pil_processed)
            if decoded:
                data = decoded[0].data.decode('utf-8')
                return data, f"pyzbar+{method_name}で成功"
        except:
            continue
    
    # 5. スケール変更（効率的な範囲）
    scales = [0.5, 0.6, 0.7, 0.8, 0.9, 1.1, 1.2, 1.3, 1.4, 1.5, 1.8, 2.0, 2.5, 3.0]
    
    for scale in scales:
        new_width = int(w * scale)
        new_height = int(h * scale)
        resized = cv2.resize(image, (new_width, new_height))
        
        # OpenCV
        try:
            data, bbox, straight_qrcode = qr_detector.detectAndDecode(resized)
            if data:
                return data, f"OpenCV+スケール{scale}で成功"
        except:
            pass
        
        # pyzbar
        try:
            resized_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            pil_resized = Image.fromarray(resized_rgb)
            decoded = pyzbar.decode(pil_resized)
            if decoded:
                data = decoded[0].data.decode('utf-8')
                return data, f"pyzbar+スケール{scale}で成功"
        except:
            pass
        
        # スケール変更 + 前処理
        resized_gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        
        for method_name, process_func in preprocessing_methods:
            try:
                processed = process_func(resized_gray)
                
                # OpenCV
                data, bbox, straight_qrcode = qr_detector.detectAndDecode(processed)
                if data:
                    return data, f"OpenCV+スケール{scale}+{method_name}で成功"
                
                # pyzbar
                pil_processed = Image.fromarray(processed)
                decoded = pyzbar.decode(pil_processed)
                if decoded:
                    data = decoded[0].data.decode('utf-8')
                    return data, f"pyzbar+スケール{scale}+{method_name}で成功"
            except:
                continue
    
    return None, "全ての手法で検出失敗"

def test_enhanced_system():
    """強化システムのテスト"""
    print("=== 強化QRコード検出システム（pyzbar + OpenCV） ===")
    
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
        print(f"--- 強化検出: {image_name} ---")
        print(f"{'='*60}")
        
        # 強化検出を実行
        qr_data, status = enhanced_qr_detection_with_pyzbar(image_path)
        
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
    
    print(f"\n=== 強化システム結果 ===")
    print(f"テスト画像数: {len(test_images)}")
    print(f"検出成功: {success_count}")
    print(f"成功率: {success_count/len(test_images)*100:.1f}%")
    
    if success_count > 0:
        print(f"🎉 改善成功！{success_count}枚の画像で検出に成功しました！")
    else:
        print("⚠️ さらなる改善が必要です。")

if __name__ == '__main__':
    test_enhanced_system()
