# main/routes.py
import os
from datetime import datetime
from flask import Blueprint, request
from supabase_client import supabase
import openai

from .haruhi_rag_engine import RagEngine  # ✅ RAG本体

# ===============================
# Flask Blueprint 初期化
# ===============================
main_bp = Blueprint('main', __name__)

# ===============================
# OpenAIクライアント設定
# ===============================
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ RagEngineのインスタンス生成（明示的に閾値指定）
rag = RagEngine(top_k=3, min_score=0.55)

# ===============================
# Supabaseログ保存
# ===============================
def save_chat_to_supabase(user_id, message, response, source="SAKURA", meta=None):
    """チャット履歴をSupabaseに保存"""
    data = {
        "user_id": user_id,
        "message": message,
        "response": response,
        "timestamp": datetime.utcnow().isoformat(),
        "source": source,
    }
    if meta:
        data["meta"] = meta  # jsonb列を利用
    supabase.table("haruhi_chat_logs").insert(data).execute()


# ===============================
# 通常GPTフォールバック（バックアップ用）
# ===============================
def normal_chat_answer(question: str) -> str:
    """RAGが失敗した場合の標準GPT応答"""
    sakura_prompt = (
        "あなたはJEISIが開発する教育思考支援AI『HARUHI』のナビゲーター「さくら」です。"
        "教育・哲学・AI倫理などの文脈で、利用者に丁寧に寄り添うトーンで回答してください。"
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": sakura_prompt},
            {"role": "user", "content": question},
        ],
    )
    return response.choices[0].message.content.strip()


# ===============================
# 🌸 SAKURAエンドポイント（RAG統合版）
# ===============================
@main_bp.route("/sakura", methods=["POST"])
def sakura_answer():
    user_question = request.form.get("sakura_question", "").strip()
    if not user_question:
        return "質問が空です。"

    print(f"🌸 Sakura Debug: {user_question}")

    try:
        # 1️⃣ まずRAGを実行
        reply, meta = rag.answer_with_rag(user_question)
        used = meta.get("used_faqs", [])

        # 2️⃣ RAG結果が空ならGPTフォールバック
        if not used:
            print("🌸 RAG未ヒット → GPT通常応答へフォールバック")
            reply = normal_chat_answer(user_question)
            meta = {"fallback": "gpt"}

    except Exception as e:
        # 3️⃣ 例外時もフォールバック
        print("🌸 Sakura Error:", e)
        reply = normal_chat_answer(user_question)
        meta = {"fallback": "gpt", "error": str(e)}

    # 4️⃣ Supabaseログ保存
    save_chat_to_supabase(
        user_id="guest_user",
        message=user_question,
        response=reply,
        source="SAKURA",
        meta=meta,
    )

    return reply
