# ============================================
#  HARUHI：PDG保存モジュール（完全修正版）
# ============================================

import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

from supabase_client import supabase

from pdg_question_detector_v2 import is_question
from pdg_question_vectorizer_v2 import generate_question_vector
from pdg_lineage_v2 import determine_parent_id

# 重要：HARUHI専用RAGエンジン
from main.haruhi_rag_engine import RagEngineHARUHI
rag_engine = RagEngineHARUHI()

load_dotenv()


def save_chat_message_with_pdg(user_id: str, session_id: str, message: str, role: str):
    record_id = str(uuid.uuid4())

    # ============================================
    # assistant（HARUHI応答）はPDG処理なし
    # ============================================
    if role == "assistant":

        supabase.table("haruhi_chat_logs").insert({
            "id": record_id,
            "user_id": user_id,
            "session_id": session_id,
            "role": role,
            "message": None,
            "response": message,
            "is_question": False,
            "question_vector": None,
            "parent_id": None,
            "evidence": None,
            "timestamp": datetime.utcnow().isoformat()
        }).execute()

        print(f"[PDG保存完了] {record_id}")
        return {
            "record_id": record_id,
            "session_id": session_id,
            "parent_id": None
        }

    # ============================================
    # user（質問）はPDG処理
    # ============================================

    # 問い判定
    question_flag = is_question(message)

    # ベクトル生成
    vector = generate_question_vector(message) if question_flag else None

    # 親問い推定（系譜）
    parent_id = None
    if question_flag:
        try:
            pdg_result = determine_parent_id(message)
            parent_id = pdg_result[0]
        except Exception as e:
            print("[PDG error]", e)

    # ============================================
    # PDGエビデンス（学習指導要領の RAG）
    # ============================================

    try:
        evidence_chunks = rag_engine.search_curriculum(
            query=message,
            k=3,                 # PDG用なので少量で十分
            threshold=0.60
        )
    except Exception as e:
        print("RAGエラー:", e)
        evidence_chunks = []

    # ============================================
    # Supabase 保存
    # ============================================
    supabase.table("haruhi_chat_logs").insert({
        "id": record_id,
        "user_id": user_id,
        "session_id": session_id,
        "role": role,
        "message": message,
        "response": None,
        "is_question": question_flag,
        "question_vector": vector,
        "parent_id": parent_id,
        "evidence": evidence_chunks,
        "timestamp": datetime.utcnow().isoformat()
    }).execute()

    print(f"[PDG保存完了] {record_id}")

    return {
        "record_id": record_id,
        "session_id": session_id,
        "parent_id": parent_id
    }
