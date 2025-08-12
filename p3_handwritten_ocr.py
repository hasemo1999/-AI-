# -*- coding: utf-8 -*-
"""
P3: 手書き系OCR
目標: IOP・視力の読取精度 ≥95%、qa_flags発生 ≤5%

対象:
- 接触型IOP
- 視力（裸眼/矯正）
- ROI固定＋正規化
"""
import argparse
import csv
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np
from paddleocr import PaddleOCR
import pandas as pd

# ロガー設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HandwrittenOCRProcessor:
    """手書き系OCR処理クラス"""
    
    def __init__(self, use_gpu: bool = False):
        """
        初期化
        
        Args:
            use_gpu: GPU使用フラグ
        """
        self.use_gpu = use_gpu
        self.ocr = None
        self._init_paddleocr()
        
        # 眼圧の正規表現パターン
        self.iop_patterns = [
            r'(\d{1,2})\.(\d{1,2})',  # 14.5, 15.2
            r'(\d{1,2})/(\d{1,2})',   # 14/15
            r'(\d{1,2})\s*mmHg',      # 14 mmHg
            r'(\d{1,2})',             # 14
        ]
        
        # 視力の正規表現パターン
        self.va_patterns = [
            r'(\d+\.\d+)',            # 1.0, 0.8
            r'(\d+)/(\d+)',           # 20/20, 10/10
            r'(\d+\.\d+)/(\d+\.\d+)', # 1.0/1.0
        ]
        
        # 眼別判定パターン
        self.eye_patterns = {
            'right': [r'右', r'OD', r'R', r'右眼'],
            'left': [r'左', r'OS', r'L', r'左眼'],
        }
    
    def _init_paddleocr(self) -> None:
        """PaddleOCRの初期化"""
        try:
            # 手書き用の設定でPaddleOCRを初期化
            self.ocr = PaddleOCR(
                use_angle_cls=True,
                lang='ch',  # 中国語モデル（日本語対応）
                use_gpu=self.use_gpu,
                show_log=False
            )
            logger.info("PaddleOCR初期化完了")
        except Exception as e:
            logger.error(f"PaddleOCR初期化失敗: {e}")
            raise
    
    def preprocess_image(self, image: np.ndarray) -> List[Tuple[str, np.ndarray]]:
        """
        画像の前処理バリエーションを生成
        
        Args:
            image: 入力画像
            
        Returns:
            前処理バリエーションのリスト
        """
        variants = []
        
        # 元画像
        variants.append(("original", image))
        
        # グレースケール
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        variants.append(("gray", gray))
        
        # コントラスト強調
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        variants.append(("enhanced", enhanced))
        
        # ノイズ除去
        denoised = cv2.fastNlMeansDenoising(gray)
        variants.append(("denoised", denoised))
        
        # 二値化
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(("binary", binary))
        
        # 反転
        binary_inv = cv2.bitwise_not(binary)
        variants.append(("binary_inv", binary_inv))
        
        return variants
    
    def extract_roi(self, image: np.ndarray, roi_config: Dict[str, Any]) -> np.ndarray:
        """
        指定されたROIを抽出
        
        Args:
            image: 入力画像
            roi_config: ROI設定
            
        Returns:
            ROI画像
        """
        h, w = image.shape[:2]
        
        # 相対座標を絶対座標に変換
        x1 = int(roi_config['x1'] * w)
        y1 = int(roi_config['y1'] * h)
        x2 = int(roi_config['x2'] * w)
        y2 = int(roi_config['y2'] * h)
        
        # ROI抽出
        roi = image[y1:y2, x1:x2]
        
        return roi
    
    def detect_text(self, image: np.ndarray) -> List[Tuple[List, str, float]]:
        """
        PaddleOCRでテキスト検出
        
        Args:
            image: 入力画像
            
        Returns:
            検出結果のリスト [(bbox, text, confidence), ...]
        """
        try:
            results = self.ocr.ocr(image, cls=True)
            
            if not results or not results[0]:
                return []
            
            detected_texts = []
            for line in results[0]:
                if line:
                    bbox, (text, confidence) = line
                    detected_texts.append((bbox, text, confidence))
            
            return detected_texts
            
        except Exception as e:
            logger.error(f"テキスト検出エラー: {e}")
            return []
    
    def extract_iop_values(self, texts: List[Tuple[List, str, float]]) -> Dict[str, Any]:
        """
        眼圧値を抽出
        
        Args:
            texts: 検出されたテキスト
            
        Returns:
            眼圧情報の辞書
        """
        iop_info = {
            'right_iop': None,
            'left_iop': None,
            'right_confidence': 0.0,
            'left_confidence': 0.0,
            'qa_flags': []
        }
        
        all_text = " ".join([text for _, text, _ in texts])
        logger.debug(f"眼圧抽出対象テキスト: {all_text}")
        
        # 眼別判定
        eye_indicators = {}
        for eye, patterns in self.eye_patterns.items():
            for pattern in patterns:
                if re.search(pattern, all_text):
                    eye_indicators[eye] = True
                    break
        
        # 眼圧値の抽出
        for bbox, text, confidence in texts:
            for pattern in self.iop_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    # 数値の妥当性チェック
                    for match in matches:
                        if isinstance(match, tuple):
                            # 複数グループの場合
                            values = [float(v) for v in match if v.isdigit()]
                        else:
                            # 単一値の場合
                            values = [float(match)]
                        
                        for value in values:
                            if 5 <= value <= 50:  # 眼圧の妥当範囲
                                # 眼別の判定
                                if any(re.search(p, text) for p in self.eye_patterns['right']):
                                    if iop_info['right_iop'] is None or confidence > iop_info['right_confidence']:
                                        iop_info['right_iop'] = value
                                        iop_info['right_confidence'] = confidence
                                elif any(re.search(p, text) for p in self.eye_patterns['left']):
                                    if iop_info['left_iop'] is None or confidence > iop_info['left_confidence']:
                                        iop_info['left_iop'] = value
                                        iop_info['left_confidence'] = confidence
                                else:
                                    # 眼別が不明な場合、両方に設定
                                    if iop_info['right_iop'] is None:
                                        iop_info['right_iop'] = value
                                        iop_info['right_confidence'] = confidence
                                    elif iop_info['left_iop'] is None:
                                        iop_info['left_iop'] = value
                                        iop_info['left_confidence'] = confidence
        
        # QAフラグの設定
        if iop_info['right_iop'] is None and iop_info['left_iop'] is None:
            iop_info['qa_flags'].append('NO_IOP_DETECTED')
        elif iop_info['right_confidence'] < 0.7 or iop_info['left_confidence'] < 0.7:
            iop_info['qa_flags'].append('LOW_IOP_CONFIDENCE')
        
        return iop_info
    
    def extract_va_values(self, texts: List[Tuple[List, str, float]]) -> Dict[str, Any]:
        """
        視力値を抽出
        
        Args:
            texts: 検出されたテキスト
            
        Returns:
            視力情報の辞書
        """
        va_info = {
            'right_va': None,
            'left_va': None,
            'right_confidence': 0.0,
            'left_confidence': 0.0,
            'qa_flags': []
        }
        
        all_text = " ".join([text for _, text, _ in texts])
        logger.debug(f"視力抽出対象テキスト: {all_text}")
        
        # 視力値の抽出
        for bbox, text, confidence in texts:
            for pattern in self.va_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    for match in matches:
                        if isinstance(match, tuple):
                            # 分数形式の場合
                            if len(match) == 2:
                                try:
                                    value = float(match[0]) / float(match[1])
                                    if 0.01 <= value <= 2.0:  # 視力の妥当範囲
                                        # 眼別の判定
                                        if any(re.search(p, text) for p in self.eye_patterns['right']):
                                            if va_info['right_va'] is None or confidence > va_info['right_confidence']:
                                                va_info['right_va'] = value
                                                va_info['right_confidence'] = confidence
                                        elif any(re.search(p, text) for p in self.eye_patterns['left']):
                                            if va_info['left_va'] is None or confidence > va_info['left_confidence']:
                                                va_info['left_va'] = value
                                                va_info['left_confidence'] = confidence
                                except (ValueError, ZeroDivisionError):
                                    continue
                        else:
                            # 小数形式の場合
                            try:
                                value = float(match)
                                if 0.01 <= value <= 2.0:  # 視力の妥当範囲
                                    # 眼別の判定
                                    if any(re.search(p, text) for p in self.eye_patterns['right']):
                                        if va_info['right_va'] is None or confidence > va_info['right_confidence']:
                                            va_info['right_va'] = value
                                            va_info['right_confidence'] = confidence
                                    elif any(re.search(p, text) for p in self.eye_patterns['left']):
                                        if va_info['left_va'] is None or confidence > va_info['left_confidence']:
                                            va_info['left_va'] = value
                                            va_info['left_confidence'] = confidence
                            except ValueError:
                                continue
        
        # QAフラグの設定
        if va_info['right_va'] is None and va_info['left_va'] is None:
            va_info['qa_flags'].append('NO_VA_DETECTED')
        elif va_info['right_confidence'] < 0.7 or va_info['left_confidence'] < 0.7:
            va_info['qa_flags'].append('LOW_VA_CONFIDENCE')
        
        return va_info
    
    def process_image(self, image_path: Path, roi_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        画像を処理して眼圧と視力を抽出
        
        Args:
            image_path: 画像パス
            roi_config: ROI設定（Noneの場合は全画像）
            
        Returns:
            抽出結果の辞書
        """
        logger.info(f"画像処理開始: {image_path.name}")
        
        # 画像読み込み
        image = cv2.imread(str(image_path))
        if image is None:
            return {'error': '画像読み込み失敗'}
        
        # ROI抽出
        if roi_config:
            image = self.extract_roi(image, roi_config)
        
        # 前処理バリエーション
        variants = self.preprocess_image(image)
        
        best_results = {
            'iop_info': {'right_iop': None, 'left_iop': None, 'qa_flags': ['NO_IOP_DETECTED']},
            'va_info': {'right_va': None, 'left_va': None, 'qa_flags': ['NO_VA_DETECTED']},
            'best_variant': None,
            'all_texts': []
        }
        
        # 各前処理バリエーションでOCR実行
        for variant_name, variant_image in variants:
            logger.debug(f"前処理バリエーション: {variant_name}")
            
            # テキスト検出
            detected_texts = self.detect_text(variant_image)
            if not detected_texts:
                continue
            
            # 眼圧抽出
            iop_info = self.extract_iop_values(detected_texts)
            
            # 視力抽出
            va_info = self.extract_va_values(detected_texts)
            
            # 結果の評価（QAフラグが少ないものを選択）
            current_qa_count = len(iop_info['qa_flags']) + len(va_info['qa_flags'])
            best_qa_count = len(best_results['iop_info']['qa_flags']) + len(best_results['va_info']['qa_flags'])
            
            if current_qa_count < best_qa_count:
                best_results['iop_info'] = iop_info
                best_results['va_info'] = va_info
                best_results['best_variant'] = variant_name
                best_results['all_texts'] = [text for _, text, _ in detected_texts]
        
        logger.info(f"処理完了: {image_path.name}")
        return best_results

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='P3: 手書き系OCR処理')
    parser.add_argument('--input', required=True, help='入力画像パス')
    parser.add_argument('--output', help='出力CSVパス')
    parser.add_argument('--gpu', action='store_true', help='GPU使用')
    parser.add_argument('--roi', help='ROI設定（JSON形式）')
    
    args = parser.parse_args()
    
    # 入力パス確認
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"入力ファイルが見つかりません: {input_path}")
        return
    
    # ROI設定の読み込み
    roi_config = None
    if args.roi:
        import json
        try:
            roi_config = json.loads(args.roi)
        except json.JSONDecodeError:
            logger.error("ROI設定のJSON解析に失敗しました")
            return
    
    # OCR処理実行
    processor = HandwrittenOCRProcessor(use_gpu=args.gpu)
    results = processor.process_image(input_path, roi_config)
    
    # 結果表示
    print("\n=== 処理結果 ===")
    print(f"入力画像: {input_path.name}")
    print(f"最適前処理: {results.get('best_variant', 'N/A')}")
    
    print("\n--- 眼圧 ---")
    iop_info = results.get('iop_info', {})
    print(f"右眼: {iop_info.get('right_iop', 'N/A')} mmHg (信頼度: {iop_info.get('right_confidence', 0):.2f})")
    print(f"左眼: {iop_info.get('left_iop', 'N/A')} mmHg (信頼度: {iop_info.get('left_confidence', 0):.2f})")
    if iop_info.get('qa_flags'):
        print(f"QAフラグ: {', '.join(iop_info['qa_flags'])}")
    
    print("\n--- 視力 ---")
    va_info = results.get('va_info', {})
    print(f"右眼: {va_info.get('right_va', 'N/A')} (信頼度: {va_info.get('right_confidence', 0):.2f})")
    print(f"左眼: {va_info.get('left_va', 'N/A')} (信頼度: {va_info.get('left_confidence', 0):.2f})")
    if va_info.get('qa_flags'):
        print(f"QAフラグ: {', '.join(va_info['qa_flags'])}")
    
    print("\n--- 検出テキスト ---")
    for i, text in enumerate(results.get('all_texts', [])[:10]):
        print(f"{i+1}: {text}")
    
    # CSV出力
    if args.output:
        output_data = {
            'image_name': input_path.name,
            'right_iop': iop_info.get('right_iop'),
            'left_iop': iop_info.get('left_iop'),
            'right_iop_confidence': iop_info.get('right_confidence'),
            'left_iop_confidence': iop_info.get('left_confidence'),
            'right_va': va_info.get('right_va'),
            'left_va': va_info.get('left_va'),
            'right_va_confidence': va_info.get('right_confidence'),
            'left_va_confidence': va_info.get('left_confidence'),
            'iop_qa_flags': ';'.join(iop_info.get('qa_flags', [])),
            'va_qa_flags': ';'.join(va_info.get('qa_flags', [])),
            'best_variant': results.get('best_variant'),
        }
        
        df = pd.DataFrame([output_data])
        df.to_csv(args.output, index=False, encoding='utf-8')
        logger.info(f"結果を保存しました: {args.output}")

if __name__ == "__main__":
    main()
