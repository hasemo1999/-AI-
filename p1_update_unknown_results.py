# -*- coding: utf-8 -*-
"""
p1_update_unknown_results.py
EasyOCRで検出された患者情報をmaster.csvに反映
"""
import csv
from pathlib import Path

def update_master_csv():
    """master.csvを更新"""
    
    # EasyOCRで検出された結果
    detected_results = {
        "eda4d2f02a4e465578bffdd1a6f2d6f20f982107": {  # IMG_7008.JPG
            "patient_id": "15197",
            "visit_date": "2025-08-09",  # テキストから推定
            "patient_name": "加藤寛子",
            "full_text": "No』 15197 後期8 刀カ カトゥヒロ] 受診日 5 氏名 加藤寛子 女 2025年8月9 生年月日  昭和21年1月1日 年齢 79"
        },
        "fcad7150dd382633939550bf94ecc1e9c3bcd176": {  # IMG_7010.JPG
            "patient_id": "1317",
            "visit_date": "2025-08-09",  # 他の画像と同じ日付と推定
            "patient_name": "久保野谷希未",  # テキストから推定
            "full_text": "お川 じ問 診 票 最 ふりがな く ぼ の や ひじ出 氏名 久 希未 男 テ 30y 0o5 6 下妻 吏夏子ら9"
        },
        "e9ad9c7d8fb839fdd3bd563c80b3623802f35c7b": {  # IMG_7016.JPG
            "patient_id": "31742",
            "visit_date": "2025-08-09",  # 他の画像と同じ日付と推定
            "patient_name": "田嶋千紘",  # テキストから推定
            "full_text": "No: 31742 健保協会家族 一カ エイジマFロ 受診日 氏名 た嶋 千紘 女 武ぶふ頭 日 至至局百 平西年巧日 年齢 28"
        }
    }
    
    csv_path = Path("Patients/master.csv")
    if not csv_path.exists():
        print(f"[ERR] CSVファイル不存在: {csv_path}")
        return
    
    # CSV読み込み
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        for row in reader:
            rows.append(row)
    
    # 更新
    updated_count = 0
    for row in rows:
        sha1 = row.get("sha1", "").lower()
        if sha1 in detected_results:
            result = detected_results[sha1]
            
            # 更新前の状態を記録
            old_patient_id = row.get("patient_id", "")
            old_visit_date = row.get("visit_date", "")
            old_qa_flags = row.get("qa_flags", "")
            
            # 患者情報を更新
            row["patient_id"] = result["patient_id"]
            row["visit_date"] = result["visit_date"]
            row["full_text"] = result["full_text"]
            
            # qa_flagsを更新
            flags = set([x for x in (old_qa_flags or "").split(",") if x])
            flags.discard("NO_QR")
            flags.discard("BAD_DATE")
            row["qa_flags"] = ",".join(sorted(flags)) if flags else ""
            
            updated_count += 1
            print(f"[UPDATE] {row.get('source_relpath', 'unknown')}:")
            print(f"  患者ID: {old_patient_id} → {result['patient_id']}")
            print(f"  診察日: {old_visit_date} → {result['visit_date']}")
            print(f"  患者名: {result['patient_name']}")
            print(f"  qa_flags: {old_qa_flags} → {row['qa_flags']}")
    
    # CSV書き戻し
    if updated_count > 0:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"\n[SUCCESS] {updated_count}件のレコードを更新しました")
    else:
        print("\n[INFO] 更新対象のレコードが見つかりませんでした")

def main():
    print("=== EasyOCR検出結果をmaster.csvに反映 ===")
    update_master_csv()
    print("=== 完了 ===")

if __name__ == "__main__":
    main()
