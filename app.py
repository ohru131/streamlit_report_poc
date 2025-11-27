

import streamlit as st
import google.generativeai as genai
import json
from datetime import datetime

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

# --- 状態管理 ---
if 'internal_report' not in st.session_state:
    st.session_state.internal_report = ""
if 'customer_report' not in st.session_state:
    st.session_state.customer_report = ""
if 'reports_generated' not in st.session_state:
    st.session_state.reports_generated = False

# --- UI ---
st.title("✍️ 日報作成支援 PoC")
st.caption("Streamlit版")

st.markdown("---")

# 1. 入力エリア
st.subheader("1. 日報内容の入力")
input_text = st.text_area(
    "こちらに日報の元となるテキストを入力してください。",
    height=150,
    placeholder="例：夜泣きが収まらず、お母さんはほとんど睡眠時間を取れていないとのことで午前中は別室で寝ていた。育児のがんばりに寄り添いながらねぎらいの言葉がけを心がけた。午前中は嘉浩くんも長い睡眠をとることができて、午後は機嫌よく遊ぶことができた。いないいないばあをすると喜ぶ姿が見られた。"
)

# 2. 生成ボタン
if st.button("🤖 日報を生成する", type="primary", use_container_width=True):
    if not input_text:
        st.warning("日報内容を入力してください。")
    else:
        with st.spinner("Gemini APIと通信中..."):
            # ★★★ 修正点3: API呼び出しとエラーハンドリングを強化 ★★★
            try:
                prompt = PROMPT_TEMPLATE.format(report_text=input_text)
                response = model.generate_content(prompt)
                
                # JSONモードのため、レスポンスは直接JSONとして解析できる
                reports = json.loads(response.text)

                st.session_state.internal_report = reports["internal_report"]
                st.session_state.customer_report = reports["customer_report"]
                st.session_state.reports_generated = True
                
                st.success("日報の生成が完了しました！")

            except Exception as e:
                st.error(f"APIリクエスト中にエラーが発生しました: {e}")
                # デバッグ用に、APIから返ってきた生のテキストを表示
                if 'response' in locals():
                    st.error(f"受信したテキスト: {response.text}")
                st.session_state.reports_generated = False

st.markdown("---")

# 3. 確認・出力エリア
st.subheader("2. 生成された日報の確認")

if st.session_state.reports_generated:
    col1, col2 = st.columns(2)

    with col1:
        st.info("🏢 社内向けレポート")
        st.text_area(
            "internal_report",
            value=st.session_state.internal_report,
            height=200,
            label_visibility="collapsed"
        )

    with col2:
        st.info("👨‍👩‍👧‍👦 顧客向けレポート")
        st.text_area(
            "customer_report",
            value=st.session_state.customer_report,
            height=200,
            label_visibility="collapsed"
        )

    st.markdown("---")
    
    # 4. ダウンロード
    st.subheader("3. レポートのダウンロード")
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # CSVエクスポート用にダブルクォートをエスケープ
    internal_escaped = st.session_state.internal_report.replace('"', '""')
    customer_escaped = st.session_state.customer_report.replace('"', '""')
    internal_csv = f'日時,内容\n"{now}","{internal_escaped}"'
    customer_csv = f'日時,内容\n"{now}","{customer_escaped}"'

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            label="📥 社内向けCSVをダウンロード",
            data=internal_csv.encode('utf-8-sig'), # BOM付きUTF-8
            file_name=f"internal_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime='text/csv',
            use_container_width=True
        )
    with col_dl2:
        st.download_button(
            label="📥 顧客向けCSVをダウンロード",
            data=customer_csv.encode('utf-8-sig'), # BOM付きUTF-8
            file_name=f"customer_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime='text/csv',
            use_container_width=True
        )
else:
    st.info("ここに生成されたレポートが表示されます。")
