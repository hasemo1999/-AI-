"""
Google Driveから仕訳データをダウンロードするスクリプト
使い方: python download_gdrive.py [--entity luminous|keiseikai|both]
"""
import os
import sys
import argparse
import gdown


# Google Drive フォルダID
FOLDERS = {
    "恵聖会": {
        "folder_id": "1RgogmSoSYcaMENDlA1oG6e8QgwRHMX3R",
        "output_dir": "data/恵聖会",
    },
    "ルミナス": {
        "folder_id": "1eiAlcbIedZKJCWvwo4-qD3b7ozooJK1E",
        "output_dir": "data/ルミナス",
    },
}


def download_folder(entity_name, folder_info, base_dir):
    """Google Driveフォルダの全ファイルをダウンロード"""
    output_dir = os.path.join(base_dir, folder_info["output_dir"])
    os.makedirs(output_dir, exist_ok=True)

    url = f"https://drive.google.com/drive/folders/{folder_info['folder_id']}"
    print(f"\n{'='*60}")
    print(f"ダウンロード中: {entity_name}")
    print(f"  フォルダID: {folder_info['folder_id']}")
    print(f"  保存先: {output_dir}")
    print(f"{'='*60}")

    try:
        gdown.download_folder(
            url=url,
            output=output_dir,
            quiet=False,
            remaining_ok=True,
        )
        print(f"✓ {entity_name} ダウンロード完了")
        # ダウンロードしたファイル一覧
        files = os.listdir(output_dir)
        if files:
            print(f"  ファイル一覧:")
            for f in sorted(files):
                fpath = os.path.join(output_dir, f)
                size = os.path.getsize(fpath)
                print(f"    - {f} ({size:,} bytes)")
        else:
            print("  ⚠ ファイルが見つかりませんでした")
        return output_dir
    except Exception as e:
        print(f"✗ {entity_name} ダウンロードエラー: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Google Driveから仕訳データをダウンロード")
    parser.add_argument(
        "--entity",
        choices=["luminous", "keiseikai", "both"],
        default="both",
        help="ダウンロード対象（luminous=ルミナス, keiseikai=恵聖会, both=両方）",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        help="出力ベースディレクトリ（デフォルト: 経理_請求書処理/）",
    )
    args = parser.parse_args()

    base_dir = args.output_dir
    results = {}

    if args.entity in ("keiseikai", "both"):
        results["恵聖会"] = download_folder("恵聖会", FOLDERS["恵聖会"], base_dir)
    if args.entity in ("luminous", "both"):
        results["ルミナス"] = download_folder("ルミナス", FOLDERS["ルミナス"], base_dir)

    print(f"\n{'='*60}")
    print("ダウンロード結果サマリー")
    print(f"{'='*60}")
    for name, path in results.items():
        status = "✓ 成功" if path else "✗ 失敗"
        print(f"  {name}: {status} → {path or 'N/A'}")

    print(f"\n次のステップ:")
    print(f"  python generate_mf_csv.py --input-dir {base_dir}/data/ --output-dir {base_dir}/output/")


if __name__ == "__main__":
    main()
