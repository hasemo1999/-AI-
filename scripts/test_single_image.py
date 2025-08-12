# test_single_image.py
import cv2
from pathlib import Path
from PIL import Image

# 1枚テスト
img_path = Path("Patients/UNKNOWN/UNKNOWN/raw/IMG_7001.JPG")

print(f"画像: {img_path}")
print(f"存在確認: {img_path.exists()}")

# 画像情報
if img_path.exists():
    pil = Image.open(img_path)
    print(f"サイズ: {pil.size}")
    print(f"形式: {pil.format}")
    
    # OpenCVでQR検出
    img = cv2.imread(str(img_path))
    if img is not None:
        detector = cv2.QRCodeDetector()
        
        # 通常
        data, pts, _ = detector.detectAndDecode(img)
        print(f"QR検出（通常）: {data if data else 'なし'}")
        
        # グレースケール
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        data, pts, _ = detector.detectAndDecode(gray)
        print(f"QR検出（グレー）: {data if data else 'なし'}")
    else:
        print("OpenCVで画像を読み込めません")
else:
    print("ファイルが見つかりません")
    
    # 実際にあるファイルを探す
    unknown_dir = Path("Patients/UNKNOWN/UNKNOWN