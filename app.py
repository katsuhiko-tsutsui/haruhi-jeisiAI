# app.py（整理版）
import os
import uuid
import requests
import markdown
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, jsonify
from dotenv import load_dotenv
from collections import OrderedDict
from main import main_bp  # ✅ routes.py Blueprint

import openai

# 環境変数ロード
load_dotenv()

# Flask初期化
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_haruhi_secret")
app.register_blueprint(main_bp)

# Supabase情報
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
app.jinja_env.filters['markdown'] = lambda text: markdown.markdown(text)

# ✅ OpenAI新APIクライアント
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ------------------------------------------------------------
# 🌸 初期ページ：HARUHIチャットUIへリダイレクト
# ------------------------------------------------------------
@app.route("/")
def index():
    guest_user_id = str(uuid.uuid4())
    new_session_id = str(uuid.uuid4())
    return redirect(url_for('chat_ui', user_id=guest_user_id) + f'?session_id={new_session_id}')


# ------------------------------------------------------------
# 🌸 HARUHIモード別プロンプト生成
# ------------------------------------------------------------
def generate_system_prompt(mode):
    prompts = {
        "reflective": (
            "あなたは思考の補助を重視する教育AI HARUHI です。"
            "ユーザーが深く考えることを支援し、問い返しや省察を促してください。"
            "断定や即答を避け、思考の余地を作ってください。"
        ),
        "creative": (
            "あなたは創造的な教育AI HARUHI です。"
            "発想を広げ、自由な例示や新しい視点を提供してください。"
        ),
        "factual": (
            "あなたは正確な知識を重視する教育AI HARUHI です。"
            "事実や根拠（法令・教育指導要領など）を明示して回答してください。"
        ),
        "meta-cognitive": (
            "あなたは省察を促す教育AI HARUHI です。"
            "ユーザーが自分の学び方を意識できるように導いてください。"
        ),
    }
    return prompts.get(mode, prompts["reflective"])


# ------------------------------------------------------------
# 🌸 HARUHIメインチャット
# ------------------------------------------------------------
@app.route("/chat_ui/<user_id>", methods=["GET", "POST"])
def chat_ui(user_id):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    if request.method == "POST":
        session_id = request.form.get("session_id")
        message = request.form.get("message")
        mode = request.form.get("mode", "reflective")

        if not session_id or not message:
            return jsonify({"error": "Missing session_id or message"}), 400

        system_prompt = generate_system_prompt(mode)
        try:
            response_obj = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ]
            )
            response = response_obj.choices[0].message.content.strip()
        except Exception as e:
            response = f"⚠️ HARUHI応答エラー: {str(e)}"

        # Supabaseへ保存
        data = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_id": user_id,
            "message": message,
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        }
        requests.post(f"{SUPABASE_URL}/rest/v1/haruhi_chat_logs", headers=headers, json=data)

        return redirect(f"/chat_ui/{user_id}?session_id={session_id}&mode={mode}")

    # GET時：ログ表示
    session_id = request.args.get("session_id")
    mode = request.args.get("mode", "reflective")

    query_url = f"{SUPABASE_URL}/rest/v1/haruhi_chat_logs"
    query_param = f"?session_id=eq.{session_id}" if session_id else f"?user_id=eq.{user_id}"
    res = requests.get(f"{query_url}{query_param}&order=timestamp", headers=headers)
    logs = res.json() if res.status_code == 200 else []

    # 全セッションリスト取得
    all_res = requests.get(
        f"{SUPABASE_URL}/rest/v1/haruhi_chat_logs?user_id=eq.{user_id}&order=timestamp",
        headers=headers
    )
    all_logs = all_res.json() if all_res.status_code == 200 else []
    sessions = OrderedDict()
    for log in all_logs:
        sid = log.get("session_id")
        if sid and sid not in sessions:
            sessions[sid] = log

    return render_template("chat_ui.html", logs=logs, user_id=user_id, sessions=sessions, mode=mode)


# ------------------------------------------------------------
# 🌸 FAQポップアップ画面
# ------------------------------------------------------------
@app.route("/faq_popup")
def faq_popup():
    return render_template("faq_popup.html")


# ------------------------------------------------------------
# 起動
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
