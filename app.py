

import streamlit as st
import google.generativeai as genai
import json
from datetime import datetime
import sqlite3
import os

# --- ページ設定 ---
st.set_page_config(
    page_title="日報作成支援 PoC",
    page_icon="✍️",
    layout="centered"
)

# --- APIキーの設定とモデルの初期化 ---
try:
    # StreamlitのSecretsからAPIキーを読み込む
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    # ★★★ 修正点1: JSONモードを有効にしてモデルを初期化 ★★★
    model = genai.GenerativeModel(
        'models/gemini-2.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )
except Exception as e:
    st.error(f"APIキーの設定またはモデルの初期化中にエラーが発生しました。'secrets.toml'を確認してください。: {e}")
    st.stop()

# --- プロンプトテンプレート ---
# ★★★ 修正点2: JSONモードに適したプロンプトに更新 ★★★
PROMPT_TEMPLATE = """
あなたは保育サービスの日報を構造化・翻訳するプロフェッショナルアシスタントです。
以下の日報テキストをもとに、「社内向け報告書」と「保護者向け連絡文」の2種類に整形し、指定されたJSONスキーマで出力してください。

# 出力方針

## ◆ 社内向け（internal_report）
- 事実を正確に、簡潔かつ客観的に記述すること
- 主観表現・感情語を避け、業務記録として利用できる形式に整える
- 「状況 → 対応 → 子どもの反応・結果」という構成を意識する
- 元の情報を省略せず、できるだけ網羅する
- 5〜7行程度にまとめる（長すぎない報告書調）
- 箇条書きは使用しない（短い段落でまとめる）

## ◆ 保護者向け（customer_report）
- 優しく安心感のあるトーンで書く
- 専門用語や内部事情は避け、温かい自然な文章にする
- ネガティブな出来事は、子どもの成長の一部としてやわらかく表現する
- 2〜4行程度で読みやすくまとめる
- 最後に保護者への簡単な気遣い・感謝のひと言を添える
- 以下のような文体を参考にすること：

### ◆ 保護者向けの参考文体（例）
今日は午前中とてもよく寝ていた〇〇くん。  
時々微笑みながら寝る姿がとてもかわいらしかったです♡  
どんな夢を見ているのかなぁ？  
お母様も日中無理せず寝てくださいね。  
本日もありがとうございました。

# 日報テキスト
{report_text}

# 出力JSONスキーマ
{{
  "internal_report": "string",
  "customer_report": "string"
}}
"""


# --- DB設定 ---
DB_PATH = os.path.join(os.path.dirname(__file__), "reports.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        input_text TEXT,
        internal_report TEXT,
        customer_report TEXT
    )''')
    conn.commit()
    conn.close()

def insert_report(created_at: str, input_text: str, internal_report: str, customer_report: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO reports (created_at, input_text, internal_report, customer_report)
                 VALUES (?, ?, ?, ?)''', (created_at, input_text, internal_report, customer_report))
    conn.commit()
    conn.close()

def fetch_all_reports():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT created_at, input_text, internal_report, customer_report FROM reports ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    return rows

def reset_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()

# --- 状態管理 ---
if 'internal_report' not in st.session_state:
    st.session_state.internal_report = ""
if 'customer_report' not in st.session_state:
    st.session_state.customer_report = ""
if 'reports_generated' not in st.session_state:
    st.session_state.reports_generated = False
if 'input_text' not in st.session_state:
    st.session_state.input_text = ""

# DBファイルがなければ初回のみ初期化
if not os.path.exists(DB_PATH):
    init_db()

# --- UI ---
st.title("✍️ 日報作成支援 PoC")
st.caption("かたひも")

st.markdown("---")


# --- UI ---
st.subheader("1. 日報内容の入力")
st.session_state.input_text = st.text_area(
    "こちらに日報の元となるテキストを入力してください。",
    value=st.session_state.input_text,
    height=150,
    placeholder="例：夜泣きが収まらず、お母さんはほとんど睡眠時間を取れていないとのことで午前中は別室で寝ていた。育児のがんばりに寄り添いながらねぎらいの言葉がけを心がけた。午前中は嘉浩くんも長い睡眠をとることができて、午後は機嫌よく遊ぶことができた。いないいないばあをすると喜ぶ姿が見られた。"
)

if st.button("🤖 日報を生成する", type="primary", use_container_width=True):
    if not st.session_state.input_text:
        st.warning("日報内容を入力してください。")
    else:
        with st.spinner("Gemini APIと通信中..."):
            try:
                prompt = PROMPT_TEMPLATE.format(report_text=st.session_state.input_text)
                response = model.generate_content(prompt)
                reports = json.loads(response.text)
                st.session_state.internal_report = reports["internal_report"]
                st.session_state.customer_report = reports["customer_report"]
                st.session_state.reports_generated = True
                st.success("日報の生成が完了しました！")
            except Exception as e:
                st.error(f"APIリクエスト中にエラーが発生しました: {e}")
                if 'response' in locals():
                    st.error(f"受信したテキスト: {response.text}")
                st.session_state.reports_generated = False

st.markdown("---")

st.subheader("2. 生成された日報の確認・編集・保存")

if st.session_state.reports_generated:
    col1, col2 = st.columns(2)
    with col1:
        st.info("🏢 社内向けレポート")
        internal_report_edit = st.text_area(
            "internal_report_edit",
            value=st.session_state.internal_report,
            height=200,
            label_visibility="collapsed",
            key="internal_report_edit"
        )
    with col2:
        st.info("👨‍👩‍👧‍👦 顧客向けレポート")
        customer_report_edit = st.text_area(
            "customer_report_edit",
            value=st.session_state.customer_report,
            height=200,
            label_visibility="collapsed",
            key="customer_report_edit"
        )
    st.markdown(":rainbow[編集後の内容で保存する場合は下のボタンを押してください]")
    if st.button("💾 レポート送信（DB保存）", key="send_both", use_container_width=True, type="primary"):
        insert_report(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            st.session_state.input_text,
            internal_report_edit,
            customer_report_edit
        )
        st.success("レポートを保存しました！")
        st.session_state.internal_report = internal_report_edit
        st.session_state.customer_report = customer_report_edit
else:
    st.info("ここに生成されたレポートが表示されます。")

st.markdown("---")

# 3. DB全件ダウンロード & 件数表示 & DB初期化
st.subheader("3. 保存済みレポートのダウンロード")
all_reports = fetch_all_reports()
st.caption(f"現在の保存件数: {len(all_reports)} 件")
col_dl, col_reset = st.columns([3,1])
with col_dl:
    if all_reports:
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator='\n')
        writer.writerow(["日時", "入力データ", "社内向けレポート", "顧客向けレポート"])
        for row in all_reports:
            writer.writerow(row)
        csv_data = output.getvalue().encode('utf-8-sig')
        st.download_button(
            label="📥 全レポートCSVダウンロード",
            data=csv_data,
            file_name=f"all_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime='text/csv',
            use_container_width=True
        )
    else:
        st.info("保存済みレポートはありません。")
with col_reset:
    if st.button("🗑️ DB初期化", type="secondary", use_container_width=True):
        reset_db()
        st.success("データベースを初期化しました")
