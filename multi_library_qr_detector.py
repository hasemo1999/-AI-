import cv2
import numpy as np
import os
from complete_patient_decoder import parse_qr_data

def multi_library_qr_detection(image_path):
    """複数ライブラリを組み合わせたQRコード検出"""
    # 画像を読み込み
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    
    if image is None:
        return None, "画像の読み込みに失敗"
    
    h, w = image.shape[:2]
    
    # 1. OpenCV QRCodeDetector
    try:
        qr_detector = cv2.QRCodeDetector()
        data, bbox, straight_qrcode = qr_detector.detectAndDecode(image)
        if data:
            return data, "OpenCVで成功"
    except:
        pass
    
    # 2. pyzbarライブラリ（利用可能な場合）
    try:
        from pyzbar import pyzbar
        from PIL import Image
        
        # OpenCV画像をPIL画像に変換
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        
        decoded = pyzbar.decode(pil_image)
        if decoded:
            data = decoded[0].data.decode('utf-8')
            return data, "pyzbarで成功"
    except ImportError:
        pass
    except:
        pass
    
    # 3. qreaderライブラリ（利用可能な場合）
    try:
        from qreader import QReader
        qreader = QReader()
        
        data = qreader.detect_and_decode(image=image)
        if data:
            return data, "qreaderで成功"
    except ImportError:
        pass
    except:
        pass
    
    # 4. 複数スケールでの検出
    scales = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.1, 1.2, 1.3, 1.4, 1.5, 1.8, 2.0, 2.5, 3.0, 3.5, 4.0]
    
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
    
    return None, "全てのライブラリで検出失敗"

def test_multi_library_system():
    """複数ライブラリシステムのテスト"""
    print("=== 複数ライブラリQRコード検出システム ===")
    
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
        print(f"--- 複数ライブラリ検出: {image_name} ---")
        print(f"{'='*60}")
        
        # 複数ライブラリ検出を実行
        qr_data, status = multi_library_qr_detection(image_path)
        
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
    
    print(f"\n=== 複数ライブラリシステム結果 ===")
    print(f"テスト画像数: {len(test_images)}")
    print(f"検出成功: {success_count}")
    print(f"成功率: {success_count/len(test_images)*100:.1f}%")

if __name__ == '__main__':
    test_multi_library_system()
