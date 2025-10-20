import os
from typing import List, Dict, Any, Tuple
import openai
from supabase_client import supabase

# ===============================
# OpenAI設定
# ===============================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# モデル設定
EMBED_MODEL = "text-embedding-3-small"  # 1536次元・安価・教育用途向け
CHAT_MODEL  = "gpt-4o"                  # 応答品質重視（JEISI標準）


# ===============================
# 埋め込み関数群
# ===============================
def _embed(texts: List[str]) -> List[List[float]]:
    """OpenAI APIでベクトル埋め込みを生成"""
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]

def _embed_one(text: str) -> List[float]:
    return _embed([text])[0]


# ===============================
# RAGエンジン本体
# ===============================
class RagEngine:
    """
    JEISI教育AI RAGモジュール（HARUHI／SAKURA共通利用）
    """
    def __init__(self, top_k: int = 3, min_score: float = 0.55):
        self.top_k = top_k
        self.min_score = float(min_score)

    # ---------- FAQ埋め込み更新 ----------
    def backfill_faq_embeddings(self, batch_size: int = 200) -> int:
        """embeddingがNULLのFAQに埋め込みを付与"""
        total = 0
        offset = 0
        while True:
            res = supabase.table("haruhi_faqs") \
                .select("id, question, answer") \
                .is_("embedding", None) \
                .range(offset, offset + batch_size - 1).execute()
            rows = res.data or []
            if not rows:
                break
            texts = [f"Q: {r['question']}\nA: {r['answer']}" for r in rows]
            vecs = _embed(texts)
            for r, v in zip(rows, vecs):
                supabase.table("haruhi_faqs").update({"embedding": v}).eq("id", r["id"]).execute()
            total += len(rows)
            offset += batch_size
        return total

    # ---------- FAQ検索 ----------
    def search_faqs(self, query: str, k=3) -> List[Dict[str, Any]]:
        """Supabase RPCによるFAQ類似検索"""
        embedding = client.embeddings.create(model=EMBED_MODEL, input=query)
        qvec = embedding.data[0].embedding

        rpc = supabase.rpc("match_faqs", {
            "query_embedding": qvec,
            "match_count": k
        }).execute()

        print("🔍 match_faqs result:", rpc.data)
        return rpc.data or []

    # ---------- プロンプト構築 ----------
    def build_prompt(self, user_query: str, faqs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        top = faqs[: self.top_k]
        ctx_lines = []
        for i, f in enumerate(top, 1):
            ctx_lines.append(f"[FAQ#{i}] Q: {f['question']}\nA: {f['answer']}")
        ctx = "\n\n".join(ctx_lines) if top else "（該当FAQなし）"

        system = (
            "あなたはJEISIの教育思考支援AI『HARUHI』のナビゲーターSAKURAです。"
            "以下のRAGコンテキストのみを根拠として回答してください。"
            "外部知識や一般的な推測で置き換えず、教育的・哲学的文脈を重視して答えてください。"
            "根拠が存在しない場合は、『私の知識ベースにはその情報がありません』と答えてください。"
        )
        rag_instructions = (
            "=== RAGコンテキスト ===\n"
            f"{ctx}\n"
            "======================="
        )
        user = f"{rag_instructions}\n\nユーザーからの質問:\n{user_query}"

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    # ---------- 応答生成 ----------
    def generate(self, messages: List[Dict[str, str]]) -> str:
        """GPTモデルで最終応答を生成"""
        try:
            resp = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=messages,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print("❌ generate() error:", e)
            return "応答生成中にエラーが発生しました。"

    # ---------- 統合処理 ----------
    def answer_with_rag(self, user_query: str) -> Tuple[str, Dict[str, Any]]:
        """RAG統合処理（検索 → フィルタ → 応答生成）"""
        faqs = self.search_faqs(user_query, k=self.top_k)
        print("📊 faqs type:", type(faqs))
        print("📊 faqs content:", faqs)
        if faqs:
            print("🧩 keys of first item:", faqs[0].keys())
        print("🎯 min_score =", self.min_score)

        # 安全キャスト（Decimal対策）
        def safe_score(f):
            try:
                return float(f.get("score", 0) or 0)
            except Exception:
                return 0.0

        faqs = [f for f in faqs if safe_score(f) >= self.min_score]
        print("✅ Filtered FAQs:", faqs)

        # RAGプロンプト生成
        messages = self.build_prompt(user_query, faqs)
        # GPT応答生成
        reply = self.generate(messages)

        meta = {
            "used_faqs": [{"id": f["id"], "question": f["question"], "score": safe_score(f)} for f in faqs]
        }
        return reply, meta
