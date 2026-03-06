"""
勘定科目マッピングルール
銀行取引の摘要から勘定科目・税区分を自動判定する
"""
import re

# ===== 法人別口座マッピング =====
ENTITY_MAP = {
    "ルミナス": {
        "accounts": ["ルミナス 常陽銀行", "ルミナス常陽銀行", "ルミナス楽天口座", "ルミナス楽天"],
        "credit_accounts": {
            "ルミナス 常陽銀行": "普通預金（常陽）",
            "ルミナス常陽銀行": "普通預金（常陽）",
            "ルミナス楽天口座": "普通預金（楽天）",
            "ルミナス楽天": "普通預金（楽天）",
        },
    },
    "恵聖会": {
        "accounts": [
            "さくら眼科クリニック（SMBC）",
            "さくら眼科クリニック",
            "医療法人 恵聖会（常陽銀行）",
            "医療法人 恵聖会（イケイセイカイ）",
            "恵聖会（常陽銀行）",
            "恵聖会（イケイセイカイ）",
            "楽天銀行 医療法人",
            "楽天銀行医療法人",
            "その他",
        ],
        "credit_accounts": {
            "さくら眼科クリニック（SMBC）": "普通預金（SMBC）",
            "さくら眼科クリニック": "普通預金（SMBC）",
            "医療法人 恵聖会（常陽銀行）": "普通預金（常陽）",
            "恵聖会（常陽銀行）": "普通預金（常陽）",
            "医療法人 恵聖会（イケイセイカイ）": "普通預金（イケイセイカイ）",
            "恵聖会（イケイセイカイ）": "普通預金（イケイセイカイ）",
            "楽天銀行 医療法人": "普通預金（楽天）",
            "楽天銀行医療法人": "普通預金（楽天）",
            "その他": "普通預金",
        },
    },
}

# ===== キーワード→勘定科目ルール =====
# (キーワードパターン, 勘定科目, 税区分) - 優先順位順
KEYWORD_RULES = [
    # 人件費
    (r"給与|給料|サラリー|キュウヨ", "給料賃金", "対象外"),
    (r"賞与|ボーナス", "給料賃金", "対象外"),
    (r"社会保険|厚生年金|健保|雇用保険|労働保険", "法定福利費", "対象外"),
    # 通信費
    (r"NTT|電話|テレホン|ﾃﾚﾎﾝ", "通信費", "課仕10%"),
    (r"レイヤード|レイヤ-ド|LAYERED", "通信費", "課仕10%"),
    (r"インターネット|ﾌﾚｯﾂ|フレッツ|プロバイダ", "通信費", "課仕10%"),
    (r"切手|郵便|ゆうパック|ﾕｳﾊﾟｯｸ", "通信費", "課仕10%"),
    # 業務委託
    (r"ALSOK|アルソック|綜合警備", "業務委託料", "課仕10%"),
    (r"清掃|クリーニング", "業務委託料", "課仕10%"),
    # 保険
    (r"保険|ホケン|ケンホケンイキョウカイ", "保険料", "対象外"),
    # 備品・消耗品
    (r"アマゾン|AMAZON|ｱﾏｿﾞﾝ", "備品・消耗品費", "課仕10%"),
    (r"楽天市場|ﾗｸﾃﾝ|RAKUTEN", "備品・消耗品費", "課仕10%"),
    (r"消耗品|備品|文具|ぶんぐ", "備品・消耗品費", "課仕10%"),
    # クレジットカード引落
    (r"クレジット|ｸﾚｼﾞｯﾄ|カード引落|ｶｰﾄﾞﾋｷｵﾄ", "未払金", "対象外"),
    (r"JCB|VISA|ﾏｽﾀｰ|MASTER|ﾗｸﾃﾝｶｰﾄﾞ|楽天カード", "未払金", "対象外"),
    # 地代家賃
    (r"家賃|ヤチン|賃料|チンリョウ", "地代家賃", "非課税"),
    # 水道光熱費
    (r"水道|スイドウ|ｽｲﾄﾞｳ", "水道光熱費", "課仕10%"),
    (r"電気|デンキ|ﾃﾞﾝｷ|東京電力|東電|TEPCO", "水道光熱費", "課仕10%"),
    (r"ガス|ｶﾞｽ|東京ガス|大阪ガス", "水道光熱費", "課仕10%"),
    # 医薬品
    (r"医薬品|イヤクヒン|薬|クスリ", "医薬品費", "課仕10%"),
    # 検査委託
    (r"検査|ケンサ|臨床検査", "検査委託費", "課仕10%"),
    # 広告
    (r"広告|コウコク|HP|ホームページ|WEB|ウェブ", "広告宣伝費", "課仕10%"),
    # 修繕
    (r"修繕|シュウゼン|修理|工事", "修繕費", "課仕10%"),
    # リース
    (r"リース|ﾘｰｽ|LEASE|レンタル", "リース料", "課仕10%"),
    # 支払報酬
    (r"税理士|ゼイリシ|社労士|シャロウシ|弁護士|司法書士|行政書士", "支払報酬", "課仕10%"),
    # 研修
    (r"研修|ケンシュウ|セミナー|講習", "研修費", "課仕10%"),
    # 接待交際費
    (r"接待|セッタイ|交際|贈答", "接待交際費", "課仕10%"),
    # 旅費交通費
    (r"交通費|コウツウヒ|タクシー|新幹線|飛行機|JR|ＪＲ", "旅費交通費", "課仕10%"),
    # 振込手数料
    (r"振込手数料|ﾌﾘｺﾐﾃｽｳﾘｮｳ|手数料|テスウリョウ", "支払手数料", "課仕10%"),
    # 収入系（入金）
    (r"診療報酬|社保|国保|シャホ|コクホ", "売上高", "対象外"),
    (r"窓口|マドグチ|自費|ジヒ", "売上高", "課仕10%"),
    # 振替（口座間）
    (r"振替|フリカエ|口座間", "普通預金", "対象外"),
    # 税金
    (r"源泉|ゲンセン|所得税|住民税|法人税", "租税公課", "対象外"),
    (r"印紙|消費税|固定資産税", "租税公課", "対象外"),
]


def get_entity(bank_account_name):
    """口座名から法人名を判定"""
    for entity, info in ENTITY_MAP.items():
        for acc in info["accounts"]:
            if acc in bank_account_name or bank_account_name in acc:
                return entity
    return "不明"


def get_credit_account(bank_account_name):
    """口座名から貸方科目（普通預金の補助科目）を取得"""
    for entity, info in ENTITY_MAP.items():
        for acc, credit in info["credit_accounts"].items():
            if acc in bank_account_name or bank_account_name in acc:
                return credit
    return "普通預金"


def classify_transaction(description, amount=0, is_deposit=False):
    """
    摘要テキストから勘定科目を自動判定

    Returns: (debit_account, tax_category, status)
        status: '自動' or '要確認'
    """
    desc_upper = description.upper() if description else ""

    for pattern, account, tax in KEYWORD_RULES:
        if re.search(pattern, desc_upper, re.IGNORECASE):
            return account, tax, "自動"

    return "不明", "", "要確認"


def create_journal_entry(
    date, description, amount, bank_account_name, is_deposit=False
):
    """
    1取引から仕訳データを作成

    Returns: dict with journal entry fields
    """
    credit_base = get_credit_account(bank_account_name)
    entity = get_entity(bank_account_name)
    account, tax, status = classify_transaction(description, amount, is_deposit)

    if is_deposit:
        # 入金：借方=普通預金、貸方=収益科目
        debit_account = credit_base
        credit_account = account if account != "不明" else "売上高"
    else:
        # 出金：借方=費用科目、貸方=普通預金
        debit_account = account
        credit_account = credit_base

    return {
        "date": date,
        "debit_account": debit_account,
        "debit_amount": amount,
        "credit_account": credit_account,
        "credit_amount": amount,
        "tax_category": tax,
        "description": description,
        "vendor": "",
        "invoice_number": "",
        "status": status,
        "entity": entity,
        "bank_account": bank_account_name,
    }
