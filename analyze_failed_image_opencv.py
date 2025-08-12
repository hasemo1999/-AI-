import cv2
import numpy as np
import os

def analyze_image_details(image_path):
    """画像の詳細分析"""
    print(f"=== 画像詳細分析: {os.path.basename(image_path)} ===")
    
    # 画像を読み込み
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    
    if image is None:
        print("❌ 画像の読み込みに失敗")
        return
    
    # 基本情報
    h, w = image.shape[:2]
    print(f"画像サイズ: {w} x {h}")
    print(f"アスペクト比: {w/h:.2f}")
    
    # グレースケール変換
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 画像の統計情報
    mean_brightness = np.mean(gray)
    std_brightness = np.std(gray)
    min_brightness = np.min(gray)
    max_brightness = np.max(gray)
    
    print(f"平均輝度: {mean_brightness:.1f}")
    print(f"輝度標準偏差: {std_brightness:.1f}")
    print(f"最小輝度: {min_brightness}")
    print(f"最大輝度: {max_brightness}")
    print(f"コントラスト: {max_brightness - min_brightness}")
    
    # エッジ検出
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.sum(edges > 0) / (w * h)
    print(f"エッジ密度: {edge_density:.4f}")
    
    # ノイズレベル推定
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    noise = cv2.absdiff(gray, blurred)
    noise_level = np.mean(noise)
    print(f"推定ノイズレベル: {noise_level:.1f}")
    
    # 画像の品質評価
    if mean_brightness < 50:
        print("⚠️ 画像が暗すぎます")
    elif mean_brightness > 200:
        print("⚠️ 画像が明るすぎます")
    
    if std_brightness < 20:
        print("⚠️ コントラストが低すぎます")
    
    if edge_density < 0.01:
        print("⚠️ エッジが少なすぎます（ぼやけている可能性）")
    
    if noise_level > 10:
        print("⚠️ ノイズが多すぎます")
    
    return {
        'size': (w, h),
        'brightness': mean_brightness,
        'contrast': max_brightness - min_brightness,
        'edge_density': edge_density,
        'noise_level': noise_level
    }

def test_extreme_preprocessing(image_path):
    """極端な前処理を試行"""
    print(f"\n=== 極端前処理テスト: {os.path.basename(image_path)} ===")
    
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 極端な前処理手法
    extreme_methods = [
        ("極端CLAHE", lambda img: cv2.createCLAHE(clipLimit=10.0, tileGridSize=(4,4)).apply(img)),
        ("極端ガウシアン", lambda img: cv2.GaussianBlur(img, (15,15), 0)),
        ("極端メディアン", lambda img: cv2.medianBlur(img, 15)),
        ("極端バイラテラル", lambda img: cv2.bilateralFilter(img, 15, 75, 75)),
        ("極端ノイズ除去", lambda img: cv2.fastNlMeansDenoising(img, None, 30, 7, 21)),
        ("極端エッジ強調", lambda img: cv2.filter2D(img, -1, np.array([[-2,-2,-2], [-2,17,-2], [-2,-2,-2]]))),
        ("極端アダプティブ閾値", lambda img: cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 21, 5)),
        ("極端Otsu閾値", lambda img: cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]),
        ("モルフォロジー処理", lambda img: cv2.morphologyEx(img, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))),
        ("極端スケールアップ", lambda img: cv2.resize(img, (img.shape[1]*4, img.shape[0]*4), interpolation=cv2.INTER_CUBIC)),
    ]
    
    qr_detector = cv2.QRCodeDetector()
    
    for method_name, process_func in extreme_methods:
        try:
            processed = process_func(gray)
            
            # OpenCV
            data, bbox, straight_qrcode = qr_detector.detectAndDecode(processed)
            if data:
                print(f"✅ {method_name}: OpenCVで成功")
                return data, f"極端{method_name}+OpenCV"
                
        except Exception as e:
            print(f"❌ {method_name}: エラー - {e}")
            continue
    
    print("❌ 全ての極端前処理で失敗")
    return None, "極端前処理失敗"

def test_region_extraction(image_path):
    """画像の特定領域を抽出してテスト"""
    print(f"\n=== 領域抽出テスト: {os.path.basename(image_path)} ===")
    
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    h, w = image.shape[:2]
    
    # 画像を9分割して各領域をテスト
    regions = [
        ("左上", (0, 0, w//3, h//3)),
        ("中央上", (w//3, 0, 2*w//3, h//3)),
        ("右上", (2*w//3, 0, w, h//3)),
        ("左中央", (0, h//3, w//3, 2*h//3)),
        ("中央", (w//3, h//3, 2*w//3, 2*h//3)),
        ("右中央", (2*w//3, h//3, w, 2*h//3)),
        ("左下", (0, 2*h//3, w//3, h)),
        ("中央下", (w//3, 2*h//3, 2*w//3, h)),
        ("右下", (2*w//3, 2*h//3, w, h))
    ]
    
    qr_detector = cv2.QRCodeDetector()
    
    for region_name, (x1, y1, x2, y2) in regions:
        try:
            # 領域を抽出
            roi = image[y1:y2, x1:x2]
            
            # OpenCV
            data, bbox, straight_qrcode = qr_detector.detectAndDecode(roi)
            if data:
                print(f"✅ {region_name}領域: OpenCVで成功")
                return data, f"{region_name}領域+OpenCV"
                
        except Exception as e:
            print(f"❌ {region_name}領域: エラー - {e}")
            continue
    
    print("❌ 全ての領域で失敗")
    return None, "領域抽出失敗"

def test_rotation_angles(image_path):
    """回転角度を変えてテスト"""
    print(f"\n=== 回転テスト: {os.path.basename(image_path)} ===")
    
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    h, w = image.shape[:2]
    
    # 回転中心
    center = (w // 2, h // 2)
    
    # 回転角度
    angles = [90, 180, 270, -90, -180, -270]
    
    qr_detector = cv2.QRCodeDetector()
    
    for angle in angles:
        try:
            # 回転行列
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            
            # 回転後の画像サイズを計算
            cos_val = abs(rotation_matrix[0, 0])
            sin_val = abs(rotation_matrix[0, 1])
            new_w = int((h * sin_val) + (w * cos_val))
            new_h = int((h * cos_val) + (w * sin_val))
            
            # 平行移動を調整
            rotation_matrix[0, 2] += (new_w / 2) - center[0]
            rotation_matrix[1, 2] += (new_h / 2) - center[1]
            
            # 回転実行
            rotated = cv2.warpAffine(image, rotation_matrix, (new_w, new_h))
            
            # QRコード検出
            data, bbox, straight_qrcode = qr_detector.detectAndDecode(rotated)
            if data:
                print(f"✅ 回転{angle}度: OpenCVで成功")
                return data, f"回転{angle}度+OpenCV"
                
        except Exception as e:
            print(f"❌ 回転{angle}度: エラー - {e}")
            continue
    
    print("❌ 全ての回転で失敗")
    return None, "回転失敗"

def main():
    """メイン処理"""
    image_path = r"G:\マイドライブ\INBOX\IMG_7010.JPG"
    
    if not os.path.exists(image_path):
        print(f"❌ ファイルが見つかりません: {image_path}")
        return
    
    # 1. 画像詳細分析
    analysis = analyze_image_details(image_path)
    
    # 2. 極端前処理テスト
    qr_data, status = test_extreme_preprocessing(image_path)
    
    if qr_data:
        print(f"\n🎉 極端前処理で成功！")
        print(f"手法: {status}")
        print(f"データ: {qr_data}")
        return
    
    # 3. 領域抽出テスト
    qr_data, status = test_region_extraction(image_path)
    
    if qr_data:
        print(f"\n🎉 領域抽出で成功！")
        print(f"手法: {status}")
        print(f"データ: {qr_data}")
        return
    
    # 4. 回転テスト
    qr_data, status = test_rotation_angles(image_path)
    
    if qr_data:
        print(f"\n🎉 回転で成功！")
        print(f"手法: {status}")
        print(f"データ: {qr_data}")
        return
    
    print(f"\n❌ 全ての手法で失敗")
    print("この画像にはQRコードが存在しないか、検出不可能な状態の可能性があります。")
    print("IMG_7010.JPGには実際にQRコードが含まれていない可能性が高いです。")

if __name__ == '__main__':
    main()
