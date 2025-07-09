import os
import openai
import requests
import uuid
import markdown
import uuid
import random
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request
from dotenv import load_dotenv
from collections import OrderedDict
from main import main_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_haruhi_secret")
app.register_blueprint(main_bp)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
app.jinja_env.filters['markdown'] = lambda text: markdown.markdown(text)

@app.route("/")
def index():
    guest_user_id = str(uuid.uuid4())
    new_session_id = str(uuid.uuid4())
    return redirect(url_for('chat_ui', user_id=guest_user_id) + f'?session_id={new_session_id}')

# 🌸 HARUHI モード別 System Prompt 生成
def generate_system_prompt(mode):
    if mode == "reflective":
        return (
            "あなたは思考の補助を重視する教育AI HARUHI です。"
            "ユーザーが深く考えることを支援し、問い返しや省後を促してください。"
            "即答や断定を避け、思考の余地を作ってください。"
            "回答はできる限り適切な段落・缸項書き・美しい表情文字を効果的に活用してください。"
        )
    elif mode == "creative":
        return (
            "あなたは創造的な教育AI HARUHI です。"
            "ユーザーの発想を広げ、自由なアイデア、例示、ユニークな視点を提供してください。"
            "回答は段落・缸項書き・美しい表情文字を効果的に活用してください。"
        )
    elif mode == "factual":
        return (
            "あなたは正確な知識を重視する教育AI HARUHI です。"
            "事実確認された内容を提供し、根拠(日本国の六法や教育小六法）を明示して誤解させないように説明してください。"
            "推測は抵え、段落・缸項書き・美しい表情文字で視覚的に整理してください。"
        )
    elif mode == "meta-cognitive":
        return (
            "あなたは省後を促す教育AI HARUHI です。"
            "ユーザーが自身の学び方を意識できるように問いかけてください。"
            "段落・缸項書き・美しい表情文字を使って整理してください。"
        )
    else:
        return generate_system_prompt("reflective")

# 🌸 OpenAI APIクライアント初期化
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/chat_logs/<user_id>")
def chat_logs(user_id):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }

    params = {
        "user_id": f"eq.{user_id}",
        "order": "timestamp"
    }

    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/haruhi_chat_logs",
        headers=headers,
        params=params
    )

    if res.status_code == 200:
        logs = res.json()
        return render_template("chat_logs.html", logs=logs)
    else:
        return "ログ取得エラー", 500

@app.route("/chat_ui/<user_id>", methods=["GET", "POST"])
def chat_ui(user_id):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    if request.method == "POST":
        # 🌸 session_id を受け取る
        session_id = request.form.get("session_id")
        if not session_id:
           return "Error: Missing session_id", 400


        message = request.form.get("message")
        mode = request.form.get("mode", "reflective")

        system_prompt = generate_system_prompt(mode)

        try:
            response_obj = client.chat.completions.create(
                model="4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ]
            )
            response = response_obj.choices[0].message.content.strip()
        except Exception as e:
            response = f"⚠️ HARUHI応答エラー: {str(e)}"

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

    # GET場合
    session_id = request.args.get("session_id")
    mode = request.args.get("mode", "reflective")

    query_url = f"{SUPABASE_URL}/rest/v1/haruhi_chat_logs"
    if session_id:
        query_url += f"?session_id=eq.{session_id}&order=timestamp"
    else:
        query_url += f"?user_id=eq.{user_id}&order=timestamp"

    get_res = requests.get(query_url, headers=headers)
    logs = get_res.json() if get_res.status_code == 200 else []

    all_res = requests.get(
        f"{SUPABASE_URL}/rest/v1/haruhi_chat_logs?user_id=eq.{user_id}&order=timestamp",
        headers=headers
    )
    all_logs = all_res.json() if all_res.status_code == 200 else []

    sessions = OrderedDict()
    for log in all_logs:
        sid = log['session_id']
        if sid and sid not in sessions:
            sessions[sid] = log

    return render_template("chat_ui.html", logs=logs, user_id=user_id, sessions=sessions, mode=mode)

@app.route("/save_chat", methods=["POST"])
def save_chat():
    data = request.json
    user_id = data.get("user_id", "guest")
    message = data.get("message")
    response = data.get("response")
    session_id = data.get("session_id", str(uuid.uuid4()))  # 🔗 session_id を受け取る

    if not message or not response:
        return jsonify({"error": "Missing data"}), 400

    payload = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "session_id": session_id,  # 🔗 session_id を含める
        "message": message,
        "response": response,
        "timestamp": datetime.utcnow().isoformat()
    }

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/haruhi_chat_logs",
        headers=headers,
        json=payload
    )

    if res.status_code in [200, 201]:
        return jsonify({"message": "Saved successfully"}), 200
    else:
        return jsonify({"error": res.text}), res.status_code

@app.route("/faq_popup")
def faq_popup():
    return render_template("faq_popup.html")

if __name__ == "__main__":
    app.run(debug=True)
