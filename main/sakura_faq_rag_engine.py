import os
from typing import List, Dict, Any
import openai
from supabase_client import supabase

# ===============================
# OpenAI 設定
# ===============================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

EMBED_MODEL = "text-embedding-3-small"   # JEISI標準（1536次元）
CHAT_MODEL = "gpt-4o-mini"               # FAQ案内は軽量モデルで十分


# ===============================
# Utility
# ===============================
def _safe_float(x, default=0.0) -> float:
    try:
        return float(x or 0)
    except:
        return default


# ======================================================
# さくら専用 FAQ RAG エンジン（HARUHIと完全分離）
# ======================================================

class RagEngineSakuraFAQ:
    """
    JEISI ナビゲーターBot『さくら』専用 FAQ RAG エンジン

    特徴：
        - FAQテーブルのみ参照（haruhi_faqs）
        - JEISIの思想・使い方説明に特化
        - HARUHIの教育的RAG（指導要領/指導案）とは完全分離
    """

    def __init__(self, top_k=3, min_score=0.30):
        self.top_k = top_k
        self.min_score = min_score

    # ================================
    # FAQ検索
    # ================================
    def search_faqs(self, query: str, k: int = 3):
        """
        FAQテーブル（haruhi_faqs）を semantic search する。
        """

        # 1. クエリ埋め込み
        qvec = client.embeddings.create(
            model=EMBED_MODEL,
            input=query
        ).data[0].embedding

        # 2. Supabase RPC 呼び出し
        resp = supabase.rpc(
            "match_faqs",
            {"query_embedding": qvec, "match_count": k}
        ).execute()

        return resp.data or []

    # ================================
    # プロンプト構築（さくら専用）
    # ================================
    def build_prompt(self, user_query: str, faqs: List[Dict[str, Any]]):
        """
        FAQコンテキストしか参照しないナビゲーション用プロンプト
        """

        faq_lines = []
        for i, f in enumerate(faqs[: self.top_k], 1):
            faq_lines.append(
                f"[FAQ#{i}] Q: {f['question']}\nA: {f['answer']}"
            )

        faq_block = "\n\n".join(faq_lines) if faq_lines else "（該当FAQなし）"

        system = (
            "あなたはJEISIのナビゲーター『さくら』です。\n"
            "役割：\n"
            "・HARUHIの使い方説明\n"
            "・JEISIの思想の案内\n"
            "・思考モードやPDG、RAGについての説明\n"
            "以下のFAQコンテキストのみを根拠として回答してください。\n"
            "FAQにない内容は推測せず『私のFAQ知識ベースにはありません』と伝えてください。\n"
        )

        rag_context = (
            "=== FAQ RAG ===\n"
            f"{faq_block}\n"
            "================"
        )

        user = f"{rag_context}\n\n質問：\n{user_query}"

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    # ================================
    # GPT応答生成
    # ================================
    def generate(self, messages):
        try:
            resp = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=messages,
                max_tokens=300,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print("❌ SakuraFAQ generate error:", e)
            return "応答生成中にエラーが発生しました。"

    # ================================
    # 統合処理（FAQのみ）
    # ================================
    def answer(self, user_query: str):
        """
        JEISI FAQ専用の軽量RAG（教育的内容は参照しない）
        """

        # 1. FAQ検索
        faqs = self.search_faqs(user_query, k=self.top_k)
        faqs = [f for f in faqs if _safe_float(f.get("score")) >= self.min_score]

        # 2. プロンプト構築
        messages = self.build_prompt(user_query, faqs)

        # 3. GPT応答生成
        reply = self.generate(messages)

        meta = {
            "used_faqs": [
                {
                    "id": f.get("id"),
                    "question": f.get("question"),
                    "score": _safe_float(f.get("score")),
                }
                for f in faqs
            ]
        }

        return reply, meta
