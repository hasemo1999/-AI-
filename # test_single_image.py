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
    detector = cv2.QRCodeDetector()
    
    # 通常
    data, pts, _ = detector.detectAndDecode(img)
    print(f"QR検出（通常）: {data if data else 'なし'}")
    
    # グレースケール
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    data, pts, _ = detector.detectAndDecode(gray)
    print(f"QR検出（グレー）: {data if data else 'なし'}")
    
    # 縮小版
    small = cv2.resize(gray, (0,0), fx=0.5, fy=0.5)
    data, pts, _ = detector.detectAndDecode(small)
    print(f"QR検出（縮小）: {data if data else 'なし'}")