# routes.py
import os
from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, session, flash
from supabase_client import supabase
import openai

main_bp = Blueprint('main', __name__)

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def save_chat_to_supabase(user_id, message, response):
    data = {
        "user_id": user_id,
        "message": message,
        "response": response,
        "timestamp": datetime.now().isoformat()
    }

    supabase.table("haruhi_chat_logs").insert(data).execute()

# 🌸 FAQ回答取得
def get_faq_answer(faq_question):
    faq_response = supabase.table("haruhi_faqs") \
        .select("answer") \
        .ilike("question", f"%{faq_question}%") \
        .execute()

    print(f"🌸 Sakura Debug: FAQ response data →", faq_response.data)

    if faq_response.data and len(faq_response.data) > 0:
        answer_text = faq_response.data[0]["answer"]
    else:
        answer_text = "🌸 FAQに該当する回答が見つかりませんでした。"

    return answer_text

# 🌸 GPT回答取得
def normal_chat_answer(question):
    sakura_prompt = "あなたは HARUHI のナビゲーター『さくら』です。ユーザーの様々な疑問に対して丁寧に案内してください。"

    response = client.chat.completions.create(
        model="o3",
        messages=[
            {"role": "system", "content": sakura_prompt},
            {"role": "user", "content": question},
        ]
    )

    sakura_reply = response.choices[0].message.content.strip()
    return sakura_reply

# 🌸 さくら応答メイン処理
@main_bp.route("/sakura", methods=["POST"])
def sakura_answer():
    user_question = request.form.get("sakura_question", "").strip()
    mode = request.form.get("mode", "").strip()

    print(f"🌸 Sakura Debug: Mode → {mode}")
    print(f"🌸 Sakura Debug: Question → {user_question}")

    sakura_reply = ""

    if mode == "faq":
        # FAQクリック → Supabase先に探す
        sakura_reply = get_faq_answer(user_question)
    else:
        # フォーム送信 → まずSupabase探し → なければGPT
        faq_answer = get_faq_answer(user_question)
        if "FAQに該当する回答が見つかりませんでした。" in faq_answer:
            print("🌸 FAQ未ヒット → GPT回答")
            sakura_reply = normal_chat_answer(user_question)
        else:
            print("🌸 FAQヒット → Supabase回答使用")
            sakura_reply = faq_answer

    save_chat_to_supabase(user_id="guest_user", message=user_question, response=sakura_reply)

    return sakura_reply
