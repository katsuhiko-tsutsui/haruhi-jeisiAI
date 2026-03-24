import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
import openai

from .haruhi_rag_engine import RagEngineHARUHI
from .sakura_faq_rag_engine import RagEngineSakuraFAQ
from .haruhi_save_with_pdg_v2 import save_chat_message_with_pdg

from supabase_client import supabase
from dotenv import load_dotenv
load_dotenv()

main_bp = Blueprint("main", __name__)
# =====================================================
# 認証チェック用ヘルパー
# =====================================================
def get_current_user():
    """
    sessionからuser_idを取得する。
    フロントエンドからのAPIリクエストはAuthorization headerから取得。
    """
    # APIリクエスト（JSON）の場合はAuthorization headerを確認
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        # Supabaseでトークン検証
        import requests as req
        res = req.get(
            f"{os.getenv('SUPABASE_URL')}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": os.getenv("SUPABASE_KEY")
            }
        )
        if res.status_code == 200:
            return res.json().get("id")
    return None


def require_login():
    """未認証の場合はloginページへリダイレクト"""
    user_id = get_current_user()
    if not user_id:
        return redirect(url_for("main.login")), None
    return None, user_id
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# =====================================================
# 2系統AI：HARUHI（教育RAG） & さくら（FAQ RAG）
# =====================================================

# HARUHI →　指導要領・指導案・PDG
haruhi_engine = RagEngineHARUHI(top_k=5, threshold=0.70)

# さくら → FAQのみ
sakura_engine = RagEngineSakuraFAQ(top_k=3, min_score=0.30)


# =====================================================
# Utility：Rawログ保存
# =====================================================
def save_raw_log(user_id, session_id, role, message, evidence=None):
    try:
        supabase.table("haruhi_chat_logs").insert(
            {
                "user_id": user_id,
                "session_id": session_id,
                "role": role,
                "message": message if role == "user" else None,
                "response": message if role == "assistant" else None,
                "timestamp": datetime.utcnow().isoformat(),
                "evidence": evidence,
            }
        ).execute()
    except Exception as e:
        print("[ERROR] save_raw_log:", e)


# =====================================================
# 新規セッション作成
# =====================================================
@main_bp.route("/create_session", methods=["POST"])
def create_session():
    data = request.get_json() or {}
    user_id = get_current_user() or data.get("user_id", "guest_user")

    session_id = str(uuid.uuid4())

    # セッションテーブル作成
    supabase.table("haruhi_sessions").insert(
        {
            "id": session_id,
            "user_id": user_id,
            "title": None,
        }
    ).execute()

    # HARUHI初期メッセージ
    supabase.table("haruhi_chat_logs").insert(
        {
            "user_id": user_id,
            "session_id": session_id,
            "role": "assistant",
            "response": "こんにちは。今日はどんなことを考えますか？",
            "source": "haruhi",
            "timestamp": datetime.utcnow().isoformat(),
        }
    ).execute()

    return jsonify({"session_id": session_id})


# =====================================================
# HARUHI（教育思考支援AI）メインチャット
# =====================================================
@main_bp.route("/haruhi_chat", methods=["POST"])
def haruhi_chat():
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()
        session_id = data.get("session_id")
        user_id = get_current_user() or data.get("user_id", "guest_user")

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        if session_id is None:
            return jsonify({"error": "No session"}), 400

        # --------------------------
        # 1. コンテキスト構築（PDG親ノード + 直近3往復）
        # --------------------------
        context_messages = []
        seen_ids = set()

        try:
            # ① 直近3往復（6件）をDBから取得
            recent_rows = (
                supabase.table("haruhi_chat_logs")
                .select("id, role, message, response, parent_id, timestamp")
                .eq("session_id", session_id)
                .neq("role", "system")
                .order("timestamp", desc=True)
                .limit(6)
                .execute()
            )
            recent = list(reversed(recent_rows.data or []))

            for r in recent:
                rid = r.get("id")
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                content = r["message"] if r["role"] == "user" else r["response"]
                if content:
                    context_messages.append({
                        "role": r["role"],
                        "content": content
                    })

            # ② PDG親ノードを取得（直近ユーザー発話のparent_id）
            last_user = next(
                (r for r in reversed(recent) if r["role"] == "user"), None
            )
            if last_user and last_user.get("parent_id"):
                parent_id = last_user["parent_id"]
                if parent_id not in seen_ids:
                    parent_row = (
                        supabase.table("haruhi_chat_logs")
                        .select("id, role, message, timestamp")
                        .eq("id", parent_id)
                        .execute()
                    )
                    if parent_row.data:
                        p = parent_row.data[0]
                        seen_ids.add(p["id"])
                        if p.get("message"):
                            # 親ノードは先頭に挿入（系譜の起点として）
                            context_messages.insert(0, {
                                "role": "user",
                                "content": f"[PDG親問い] {p['message']}"
                            })

            print(f"[DEBUG] context_messages count: {len(context_messages)}")

        except Exception as e:
            print("[ERROR] context build:", e)
            context_messages = []

        # --------------------------
        # 2. HARUHI 専用RAG
        # --------------------------
        result = haruhi_engine.answer(
            user_query=user_message,
            context_messages=context_messages if context_messages else None
        )

        if result is None:
            raise RuntimeError("haruhi_engine.answer() returned None")

        reply, rag_meta = result

        print("\n[DEBUG] Curriculum RAG results:")
        print(rag_meta.get("curriculum"))

        print("\n[DEBUG] LessonPlan RAG results:")
        print(rag_meta.get("lesson_plans"))

        # --------------------------
        # 3. PDG保存（ユーザー発話）
        # --------------------------
        user_log = save_chat_message_with_pdg(
            user_id=user_id,
            session_id=session_id,
            message=user_message,
            role="user",
        )

        if user_log is None:
            return jsonify({"error": "PDG保存エラー"}), 500

        # --------------------------
        # 4. アシスタント応答保存
        # --------------------------
        evidence = {
            "curriculum": rag_meta.get("curriculum"),
            "lesson_plans": rag_meta.get("lesson_plans"),
        }

        save_raw_log(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            message=reply,
            evidence=evidence,
        )

        # --------------------------
        # 5. セッションタイトル生成
        # --------------------------
        try:
            ses = (
                supabase.table("haruhi_sessions")
                .select("title")
                .eq("id", session_id)
                .execute()
            )

            if ses.data and ses.data[0]["title"] is None:
                title_prompt = f"次の内容を15文字以内で要約した日本語タイトルを生成：\n{user_message}"

                title_res = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "短く簡潔なタイトルを生成する"},
                        {"role": "user", "content": title_prompt},
                    ],
                    max_tokens=50,
                )

                new_title = title_res.choices[0].message.content.strip()

                supabase.table("haruhi_sessions").update(
                    {"title": new_title}
                ).eq("id", session_id).execute()

        except Exception as e:
            print("[ERROR] session title:", e)

        return jsonify(
            {
                "reply": reply,
                "session_id": session_id,
                "evidence": evidence,
            }
        )

    except Exception as e:
        print("[ERROR] haruhi_chat:", e)
        return jsonify({"error": "server error"}), 500


# =====================================================
# さくら FAQ チャット
# =====================================================
@main_bp.route("/sakura_faq_chat", methods=["POST"])
def sakura_faq_chat():
    try:
        data = request.get_json()
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"error": "empty question"}), 400

        # さくら専用RAG
        reply, meta = sakura_engine.answer(question)

        return jsonify(
            {
                "answer": reply,
                "faq_evidence": meta,
            }
        )

    except Exception as e:
        print("[ERROR] sakura_faq_chat:", e)
        return jsonify({"error": "server error"}), 500


# =====================================================
# セッション読み込み
# =====================================================
@main_bp.route("/get_session_messages/<session_id>", methods=["GET"])
def get_session_messages(session_id):
    try:
        rows = (
            supabase.table("haruhi_chat_logs")
            .select("role, message, response, timestamp")
            .eq("session_id", session_id)
            .order("timestamp", desc=False)
            .execute()
        )

        messages = []
        for r in rows.data:
            content = r["message"] if r["role"] == "user" else r["response"]
            messages.append({"role": r["role"], "content": content})

        return jsonify({"messages": messages})

    except Exception as e:
        print("[ERROR] get_session_messages:", e)
        return jsonify({"messages": []})


# =====================================================
# セッション一覧
# =====================================================
@main_bp.route("/get_sessions", methods=["GET"])
def get_sessions():
    try:
        data = request.args
        user_id = get_current_user() or data.get("user_id", "guest_user")

        rows = (
            supabase.table("haruhi_sessions")
            .select("id, title, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        out = []
        for r in rows.data:
            out.append(
                {
                    "session_id": r["id"],
                    "title": r["title"] if r["title"] else "新しいチャット",
                }
            )

        return jsonify({"sessions": out})

    except Exception as e:
        print("[ERROR] get_sessions:", e)
        return jsonify({"sessions": []})


# =====================================================
# セッションタイトル変更
# =====================================================
@main_bp.route("/update_session_title", methods=["POST"])
def update_session_title():
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        new_title = data.get("title", "").strip()

        if not session_id or not new_title:
            return jsonify({"error": "invalid parameters"}), 400

        supabase.table("haruhi_sessions").update(
            {"title": new_title}
        ).eq("id", session_id).execute()

        return jsonify({"message": "ok", "title": new_title})

    except Exception as e:
        print("[ERROR] update_session_title:", e)
        return jsonify({"error": "server error"}), 500


# =====================================================
# FAQ一覧（さくらTOPに表示する3件）
# =====================================================
@main_bp.route("/get_faqs", methods=["GET"])
def get_faqs():
    try:
        rows = (
            supabase.table("haruhi_faqs")
            .select("id, question, answer, importance")
            .order("importance", desc=True)
            .limit(3)
            .execute()
        )
        return jsonify({"faqs": rows.data})

    except Exception as e:
        print("[ERROR] get_faqs:", e)
        return jsonify({"faqs": []})


# =====================================================
# 初期画面
# =====================================================
@main_bp.route("/", methods=["GET"])
def index():
    token = request.args.get("token", "")
    if not token:
        return redirect(url_for("main.login"))
    return render_template("chat_ui.html")

# =====================================================
# PDG Tree取得
# =====================================================
@main_bp.route("/get_pdg_tree/<user_id>", methods=["GET"])
def get_pdg_tree(user_id):

    try:
        rows = (
            supabase.table("haruhi_chat_logs")
            .select("id, message, parent_id, timestamp")
            .eq("user_id", user_id)
            .eq("role", "user")
            .order("timestamp", desc=False)
            .execute()
        )

        nodes = []

        for r in rows.data:
            nodes.append({
                "id": r["id"],
                "text": r["message"],
                "parent": r["parent_id"],
                "time": r["timestamp"]   # created_at → timestamp
            })

        return jsonify(nodes)

    except Exception as e:
        print("[ERROR] get_pdg_tree:", e)
        return jsonify([])

# =====================================================
# ログイン画面
# =====================================================
@main_bp.route("/login", methods=["GET"])
def login():
    return render_template("login.html")


# =====================================================
# Auth コールバック（メール確認後の遷移先）
# =====================================================
@main_bp.route("/auth/callback", methods=["GET"])
def auth_callback():
    return render_template("auth_callback.html")