import cv2
import numpy as np
import os
import glob
from complete_patient_decoder import parse_qr_data

def test_qr_code_from_image(image_path):
    """画像ファイルからQRコードを読み取り"""
    try:
        # 画像を読み込み（日本語パス対応）
        image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        
        if image is None:
            return None, "画像の読み込みに失敗"
        
        # QRコード検出器を初期化
        qr_detector = cv2.QRCodeDetector()
        
        # QRコード検出
        data, bbox, straight_qrcode = qr_detector.detectAndDecode(image)
        
        if data:
            return data, "成功"
        else:
            # スケール変更を試行
            h, w = image.shape[:2]
            scales = [0.5, 0.75, 1.25, 1.5, 2.0, 2.5, 3.0]
            
            for scale in scales:
                new_width = int(w * scale)
                new_height = int(h * scale)
                resized = cv2.resize(image, (new_width, new_height))
                
                data_scaled, bbox_scaled, straight_qrcode_scaled = qr_detector.detectAndDecode(resized)
                if data_scaled:
                    return data_scaled, f"スケール{scale}で成功"
            
            return None, "QRコード検出失敗"
    except Exception as e:
        return None, f"エラー: {e}"

def main():
    """メイン処理"""
    print("=== ローカルGoogleドライブ画像QRコード読み取りテスト（修正版） ===")
    
    # GoogleドライブのINBOXフォルダパス
    drive_path = r"G:\マイドライブ\INBOX"
    
    if not os.path.exists(drive_path):
        print(f"❌ フォルダが見つかりません: {drive_path}")
        return
    
    print(f"フォルダパス: {drive_path}")
    
    # 画像ファイルを検索（複数の拡張子に対応）
    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.JPG', '*.JPEG', '*.PNG']
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(drive_path, ext)))
        # サブフォルダも検索
        image_files.extend(glob.glob(os.path.join(drive_path, "**", ext), recursive=True))
    
    if not image_files:
        print("画像ファイルが見つかりませんでした。")
        return
    
    print(f"見つかった画像ファイル数: {len(image_files)}")
    
    # 重複を除去
    image_files = list(set(image_files))
    print(f"重複除去後の画像ファイル数: {len(image_files)}")
    
    # 各画像でQRコード読み取りを試行
    success_count = 0
    
    for i, image_path in enumerate(image_files):
        print(f"\n{'='*60}")
        print(f"--- 画像 {i+1}: {os.path.basename(image_path)} ---")
        print(f"パス: {image_path}")
        print(f"{'='*60}")
        
        try:
            # QRコード読み取り
            qr_data, status = test_qr_code_from_image(image_path)
            
            if qr_data:
                print(f"✅ QRコード検出: {status}")
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
                print(f"❌ QRコード検出: {status}")
            
        except Exception as e:
            print(f"❌ エラー: {e}")
        
        print(f"{'='*60}")
    
    print(f"\n=== テスト完了 ===")
    print(f"総画像数: {len(image_files)}")
    print(f"QRコード検出成功: {success_count}")
    print(f"成功率: {success_count/len(image_files)*100:.1f}%")

if __name__ == '__main__':
    main()
