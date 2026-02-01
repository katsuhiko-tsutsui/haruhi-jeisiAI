import os
from typing import List, Dict, Any
import openai
from supabase_client import supabase

# ===============================
# OpenAI 設定
# ===============================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

EMBED_MODEL = "text-embedding-3-small"   # JEISI標準
CHAT_MODEL = "gpt-4o"                    # 教育対話向け


def _safe_float(x, default=0.0) -> float:
    try:
        return float(x or 0)
    except Exception:
        return default
# ================================
# 教科推定用キーワード
# ================================
SUBJECT_KEYWORDS = {
    "SCIENCE": [
        "理科", "電気", "光", "音", "力", "磁石",
        "植物", "動物", "化学", "物理", "生物"
    ],
    "JAPANESE": [
        "国語", "読む", "書く", "話す", "聞く",
        "文章", "言語", "表現"
    ],
    "MATH": [
        "算数", "数学", "数", "計算", "図形",
        "割合", "関数"
    ],
    "SOCIAL": [
        "社会", "地理", "歴史", "公民",
        "地域", "日本", "世界"
    ],
    "FOREIGN_LANGUAGE": [
        "外国語", "英語"
    ],
    "MORAL": [
        "道徳", "価値", "規範", "善悪"
    ],
    "GENERAL": [
        "総則", "資質", "能力", "育成",
        "見方", "考え方"
    ],
}

# ============================================================
# JEISI HARUHI – FAQゼロ・教育根拠専用RAGエンジン
# （既存コードとの完全互換版）
# ============================================================

class RagEngineHARUHI:
    """
    JEISI 教育思考支援AI『HARUHI』専用 RAG エンジン

    ★ 重要な互換ポイント
        - __init__(top_k=5, threshold=0.70)  → routes.py と整合
        - search_curriculum(query, k, threshold, school_stage=None, subject=None)
        - search_lesson_plans(query, k)
        - answer(user_query) → (reply, meta)
    """

    def __init__(self, top_k: int = 5, threshold: float = 0.70):
        self.top_k = top_k
        self.base_threshold = threshold

    def _infer_stage_subject(self, query: str):
        q = query.lower()

        # 校種推定
        if "中学校" in q or "中学" in q:
            stage = "junior_high"
        else:
            stage = "elementary"

        # 教科推定
        subject = None
        for subj, keywords in SUBJECT_KEYWORDS.items():
            if subj == "GENERAL":
                continue
            for kw in keywords:
                if kw in q:
                    subject = subj
                    break
            if subject is not None:
                break

        # ★ 教科が取れなければ None を返す（問い返し用）
        return stage, subject


    # -------------------------------
    # クエリ長に応じた動的 threshold
    # -------------------------------
    def _auto_threshold(self, query: str) -> float:
        qlen = len(query)
        if qlen <= 10:
            return 0.50
        elif qlen <= 25:
            return 0.55
        else:
            return 0.60

    # ================================
    # 指導要領検索（RPC利用）
    # ================================
    def search_curriculum(
        self,
        query: str,
        k: int = 5,
        threshold: float = None,
        school_stage: str = None,
        subject: str = None,
    ) -> List[Dict[str, Any]]:
        """
        改修方針：
            - subject は正規化（大文字）
            - subject 指定でヒットしなければ自動的に subject 無しで再検索
            - 「返らない」状態を作らない
        """

        try:
            if threshold is None:
                threshold = self.base_threshold

            # ---------------------------------
            # ① クエリ埋め込み
            # ---------------------------------
            qvec = client.embeddings.create(
                model=EMBED_MODEL,
                input=query
            ).data[0].embedding

            # subject 正規化（None安全）
            subject_norm = subject.upper() if isinstance(subject, str) else None

            # ---------------------------------
            # ② まずは subject 指定ありで検索
            # ---------------------------------
            params = {
                "query_embedding": qvec,
                "match_threshold": threshold,
                "match_count": k,
            }
            if school_stage:
                params["p_school_stage"] = school_stage
            if subject_norm:
                params["p_subject"] = subject_norm

            print("[DEBUG] curriculum search params:", params)

            resp = supabase.rpc("match_curriculum_entries", params).execute()
            rows = resp.data or []

            # ---------------------------------
            # ③ ヒットしなければ subject 無しで再検索
            # ---------------------------------
            if not rows and subject_norm:
                print("[DEBUG] retry curriculum search without subject")

                params_fallback = {
                    "query_embedding": qvec,
                    "match_threshold": threshold,
                    "match_count": k,
                }
                if school_stage:
                    params_fallback["p_school_stage"] = school_stage

                resp = supabase.rpc(
                    "match_curriculum_entries",
                    params_fallback
                ).execute()
                rows = resp.data or []

            # ---------------------------------
            # ④ 整形して返却
            # ---------------------------------
            out = []
            for r in rows:
                out.append(
                    {
                        "id": r.get("id"),
                        "school_stage": r.get("school_stage"),
                        "subject": r.get("subject"),
                        "chapter": r.get("chapter"),
                        "section": r.get("section"),
                        "subsection": r.get("subsection"),
                        "category": r.get("category"),
                        "content": r.get("content"),
                        "source_page": r.get("source_page"),
                        "doc_ref": r.get("doc_ref"),
                        "similarity": round(_safe_float(r.get("similarity")), 3),
                    }
                )

            return out

        except Exception as e:
            print("[ERROR] search_curriculum:", e)
            return []

    # ================================
    # 指導案検索（RPC利用）
    # ================================
    def search_lesson_plans(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        既存コード互換：
            - query: ユーザーの問い
            - k:    上位何件返すか

        Supabase 側：
            match_lesson_plans(query_embedding, match_count)
        """

        try:
            qvec = client.embeddings.create(
                model=EMBED_MODEL,
                input=query
            ).data[0].embedding

            resp = supabase.rpc(
                "match_lesson_plans",
                {"query_embedding": qvec, "match_count": k},
            ).execute()

            rows = resp.data or []

            out = []
            for r in rows:
                out.append(
                    {
                        "id": r.get("id"),
                        "title": r.get("title"),
                        "content": r.get("content"),
                        "goal": r.get("goal"),
                        "subject": r.get("subject"),
                        "school_type": r.get("school_type"),
                        "similarity": round(_safe_float(r.get("similarity")), 3),
                    }
                )
            return out

        except Exception as e:
            print("[ERROR] search_lesson_plans:", e)
            return []

    # ================================
    # プロンプト構築（HARUHI専用）
    # ================================
    def _build_prompt(
        self,
        user_query: str,
        curriculum: List[Dict[str, Any]],
        lessons: List[Dict[str, Any]],
    ):
        # 学習指導要領ブロック
        cur_lines = []
        for i, c in enumerate(curriculum[: self.top_k], 1):
            loc = " / ".join(
                [x for x in [c.get("chapter"), c.get("section"), c.get("subsection")] if x]
            )
            src = f"p.{c['source_page']}" if c.get("source_page") else (c.get("doc_ref") or "")
            cur_lines.append(
                f"[CUR#{i}] {c.get('school_stage','')} {c.get('subject','')} {loc}\n"
                f"• {c.get('content')}\n"
                f"（{src}｜similarity={c.get('similarity')}）"
            )
        cur_block = "\n\n".join(cur_lines) if cur_lines else "（該当なし）"

        # 指導案ブロック
        les_lines = []
        for i, l in enumerate(lessons[: self.top_k], 1):
            les_lines.append(
                f"[PLAN#{i}] {l.get('title','')}\n"
                f"• {l.get('content')}\n"
                f"（similarity={l.get('similarity')}）"
            )
        les_block = "\n\n".join(les_lines) if les_lines else "（該当なし）"

        system = (
            "あなたはJEISIの教育思考支援AI『HARUHI』です。\n"
            "HARUHIの役割は、問いに対して唯一の正解を断定することではなく、\n"
            "学習指導要領や指導案に基づいて、\n"
            "『どのような考え方・基準・観点で捉えるとよいか』を整理して示すことです。\n\n"

            "以下に示される学習指導要領や指導案の記述は、\n"
            "問いに対して【直接的な答え】でなくても構いません。\n"
            "抽象的・原理的・方針レベルの記述であっても、\n"
            "それが教育的な基準や判断の拠り所となる場合は、\n"
            "『参考となる教育的根拠』として積極的に活用してください。\n\n"

            "回答では、\n"
            "・学習指導要領が示している考え方や重視点\n"
            "・授業設計や教材研究で意識すべき観点\n"
            "・問いを考える際の軸や視点\n"
            "を整理して述べてください。\n\n"

            "本文中では、参照した根拠に [CUR#] または [PLAN#] のラベルを付してください。\n\n"

            "ただし、学習指導要領・指導案の両方が明確に（該当なし）の場合に限り、\n"
            "一般的な知識やWeb情報で補うことはせず、\n"
            "次の一文のみをそのまま返してください。\n"
            "『現時点で、HARUHIが参照しているJEISIのデータベース\n"
            "（学習指導要領・指導案）には、この問いに直接対応する記述が\n"
            "まだ登録されていません。』\n"
        )

        rag_context = (
            "=== 教育根拠 RAG コンテキスト ===\n"
            "[学習指導要領]\n" + cur_block + "\n\n"
            "[指導案]\n" + les_block + "\n"
            "================================="
        )

        user = f"{rag_context}\n\n質問：\n{user_query}"

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    # ================================
    # GPT 応答生成
    # ================================
    def _generate(self, messages) -> str:
        try:
            resp = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=messages,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print("[ERROR] HARUHI generate:", e)
            return "応答生成中にエラーが発生しました。"

    # ================================
    # 統合処理：HARUHI回答
    # ================================
    def answer(self, user_query: str): 
        print("=== ANSWER() ENTER ===")
        # ① 校種・教科推定（None防御）
        result = self._infer_stage_subject(user_query)
        if result is None:
            raise RuntimeError("_infer_stage_subject returned None")

        stage, subject = result

        print("[DEBUG] infer_stage_subject:", stage, subject)

        # ---------------------------------
        # ② 教科が取れない場合：問い返し
        # ---------------------------------
        if subject is None:
            print("RETURN: subject_none")
            msg = (
                "今の問いは、とても大切な観点を含んでいます。\n\n"
                "ただ、どの教科の立場から考えるかによって、"
                "『見方・考え方』や重視点が変わります。\n\n"
                "どの教科について考えたいか、教えてもらえますか？\n"
                "（例：小学校理科／社会／算数／外国語／道徳 など）"
            )
            meta = {
            "curriculum": [],
            "lesson_plans": [],
            "subject": None,
            "stage": stage,
            }
            return msg, meta

        # ---------------------------------
        # ③ 動的 threshold
        # ---------------------------------
        dyn_th = self._auto_threshold(user_query)

        if subject in ["SCIENCE", "MATH"]:
            dyn_th = max(dyn_th, 0.55)
        elif subject in ["JAPANESE", "SOCIAL", "FOREIGN_LANGUAGE", "MORAL"]:
            dyn_th = max(dyn_th, 0.40)
        elif subject == "GENERAL":
            dyn_th = max(dyn_th, 0.35)

        print("[DEBUG] threshold:", dyn_th)

        # ---------------------------------
        # ④ 学習指導要領RAG
        # ---------------------------------
        curriculum = self.search_curriculum(
            query=user_query,
            k=self.top_k,
            threshold=dyn_th,
            school_stage=stage,
            subject=subject,
        )

        print("[DEBUG] Curriculum RAG results:", curriculum)

        lessons = []  # 指導案RAGは現時点では停止

        # ---------------------------------
        # ⑤ 根拠が取れなかった場合
        # ---------------------------------
        #if not curriculum:
        #    print("RETURN: no_curriculum")
        #    msg = (
        #        "現時点で、HARUHIが参照しているJEISIのデータベース"
        #        "（学習指導要領・指導案）には、この問いに直接対応する記述が"
        #        "まだ登録されていません。"
        #    )
        #    return msg, {
        #        "curriculum": [],
        #        "lesson_plans": [],
        #        "subject": subject,
        #        "stage": stage,
        #    }

        # ---------------------------------
        # ⑥ プロンプト構築
        # ---------------------------------
        messages = self._build_prompt(user_query, curriculum, lessons)
        if messages is None:
            raise RuntimeError("_build_prompt returned None")

        # ---------------------------------
        # ⑦ GPT 応答生成
        # ---------------------------------
        reply = self._generate(messages)
        if reply is None:
            raise RuntimeError("_generate returned None")

        print("RETURN: normal")

        return reply, {
            "curriculum": curriculum,
            "lesson_plans": lessons,
            "subject": subject,
            "stage": stage,
        }

