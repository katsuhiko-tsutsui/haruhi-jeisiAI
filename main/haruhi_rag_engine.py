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
CHAT_MODEL  = "gpt-4o"                   # 教育対話向け


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

# ================================
# 出典生成用マッピング
# ================================
STAGE_LABEL = {
    "elementary": "小学校",
    "junior_high": "中学校",
    "小学校": "小学校",
    "中学校": "中学校",
    "高等学校": "高等学校",
}

STAGE_YEAR = {
    "小学校":   "平成29年告示",
    "中学校":   "平成29年告示",
    "高等学校": "平成30年告示",
}

SUBJECT_LABEL = {
    "SCIENCE":                     "理科",
    "MATH":                        "算数・数学",
    "JAPANESE":                    "国語",
    "SOCIAL":                      "社会",
    "FOREIGN_LANGUAGE":            "外国語",
    "FOREIGN_LANGUAGE_ACTIBITIES": "外国語活動",
    "MORAL":                       "道徳",
    "MORAL_EDUCATIONS":            "道徳",
    "GENERAL":                     "総則",
    "ARTS_AND_CRAFTS":             "図画工作",
    "MUSIC":                       "音楽",
    "HOME_ECONOMICS":              "家庭",
    "PHYSICAL_EDUCATION":          "体育・保健体育",
    "INTEGRATED_STUDIES":          "総合的な学習の時間",
    "SPECIAL_ACTIVITIES":          "特別活動",
    "LIFE_STUDIES":                "生活",
    "理科": "理科",
}


def _build_citation(row: Dict[str, Any]) -> str:
    """
    school_stage・subject・source_page から出典文字列を生成する。
    例：「小学校学習指導要領〔平成29年告示〕「理科」p.109」
    """
    stage_raw   = row.get("school_stage", "")
    subject_raw = row.get("subject", "")
    page        = row.get("source_page")

    stage   = STAGE_LABEL.get(stage_raw, stage_raw)
    year    = STAGE_YEAR.get(stage, "")
    subject = SUBJECT_LABEL.get(subject_raw, subject_raw)

    if stage and year and subject:
        citation = f"{stage}学習指導要領〔{year}〕「{subject}」"
    elif stage and subject:
        citation = f"{stage}学習指導要領「{subject}」"
    elif stage:
        citation = f"{stage}学習指導要領"
    else:
        citation = "学習指導要領"

    if page:
        citation += f" p.{page}"

    return citation


# ============================================================
# JEISI HARUHI – ハイブリッド回答モード対応RAGエンジン
# ver.2.1  2026-03-24  出典表示対応
# ============================================================

class RagEngineHARUHI:
    """
    JEISI 教育思考支援AI『HARUHI』専用 RAG エンジン

    ★ ハイブリッド回答モード
        - RAGヒットあり → 【根拠あり回答】出典付きで学習指導要領を根拠に回答
        - RAGヒットなし → 【AI一般回答】データベース未登録の旨を明示した上でLLM回答

    ★ 出典表示例
        [CUR#1]（出典：小学校学習指導要領〔平成29年告示〕「理科」p.109）

    ★ 互換ポイント（routes.py との整合を維持）
        - __init__(top_k=5, threshold=0.70)
        - answer(user_query) → (reply, meta)
        - meta に reply_mode ("RAG" | "LLM" | "ASK") を追加
    """

    def __init__(self, top_k: int = 5, threshold: float = 0.70):
        self.top_k = top_k
        self.base_threshold = threshold

    # ================================
    # 校種・教科推定
    # ================================
    def _infer_stage_subject(self, query: str):
        q = query.lower()

        if "中学校" in q or "中学" in q:
            stage = "junior_high"
        else:
            stage = "elementary"

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

        return stage, subject

    # --------------------------------
    # クエリ長に応じた動的 threshold
    # --------------------------------
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
        try:
            if threshold is None:
                threshold = self.base_threshold

            qvec = client.embeddings.create(
                model=EMBED_MODEL,
                input=query
            ).data[0].embedding

            subject_norm = subject.upper() if isinstance(subject, str) else None

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
                    "match_curriculum_entries", params_fallback
                ).execute()
                rows = resp.data or []

            out = []
            for r in rows:
                out.append({
                    "id":           r.get("id"),
                    "school_stage": r.get("school_stage"),
                    "subject":      r.get("subject"),
                    "chapter":      r.get("chapter"),
                    "section":      r.get("section"),
                    "subsection":   r.get("subsection"),
                    "category":     r.get("category"),
                    "content":      r.get("content"),
                    "source_page":  r.get("source_page"),
                    "doc_ref":      r.get("doc_ref"),
                    "similarity":   round(_safe_float(r.get("similarity")), 3),
                    "citation":     _build_citation(r),   # ★ 出典文字列
                })
            return out

        except Exception as e:
            print("[ERROR] search_curriculum:", e)
            return []

    # ================================
    # 指導案検索（RPC利用）
    # ================================
    def search_lesson_plans(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
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
                out.append({
                    "id":          r.get("id"),
                    "title":       r.get("title"),
                    "content":     r.get("content"),
                    "goal":        r.get("goal"),
                    "subject":     r.get("subject"),
                    "school_type": r.get("school_type"),
                    "similarity":  round(_safe_float(r.get("similarity")), 3),
                })
            return out

        except Exception as e:
            print("[ERROR] search_lesson_plans:", e)
            return []

    # ================================
    # プロンプト構築（ハイブリッド・出典表示対応）
    # ================================
    def _build_prompt(
        self,
        user_query: str,
        curriculum: List[Dict[str, Any]],
        lessons: List[Dict[str, Any]],
        context_messages: List[Dict[str, str]] = None,  # ★ PDG+直近履歴
    ):
        has_rag = bool(curriculum) or bool(lessons)

        # ---------- RAGコンテキストブロック（出典付き） ----------
        cur_lines = []
        for i, c in enumerate(curriculum[: self.top_k], 1):
            loc = " / ".join(
                [x for x in [c.get("chapter"), c.get("section"), c.get("subsection")] if x]
            )
            citation = c.get("citation", "")
            cur_lines.append(
                f"[CUR#{i}] {loc}\n"
                f"• {c.get('content')}\n"
                f"（出典：{citation}｜similarity={c.get('similarity')}）"
            )
        cur_block = "\n\n".join(cur_lines) if cur_lines else "（該当なし）"

        les_lines = []
        for i, l in enumerate(lessons[: self.top_k], 1):
            les_lines.append(
                f"[PLAN#{i}] {l.get('title','')}\n"
                f"• {l.get('content')}\n"
                f"（similarity={l.get('similarity')}）"
            )
        les_block = "\n\n".join(les_lines) if les_lines else "（該当なし）"

        # ---------- システムプロンプト（ハイブリッド分岐） ----------
        if has_rag:
            system = (
                "あなたはJEISIの教育思考支援AI『HARUHI』です。\n"
                "HARUHIの役割は、問いに対して唯一の正解を断定することではなく、\n"
                "学習指導要領や指導案に基づいて、\n"
                "『どのような考え方・基準・観点で捉えるとよいか』を整理して示すことです。\n\n"

                "以下に示される学習指導要領の記述を根拠として回答してください。\n"
                "記述が問いへの直接的な答えでなくても構いません。\n"
                "抽象的・原理的・方針レベルの記述であっても、\n"
                "教育的な基準や判断の拠り所となる場合は積極的に活用してください。\n\n"

                "【回答の形式】\n"
                "1. 冒頭に必ず【根拠あり回答】と明記する\n"
                "2. 本文中で根拠を引用する際は [CUR#番号] のラベルを付ける\n"
                "3. 回答末尾に「■ 参照出典」として、本文中で引用した [CUR#番号] の\n"
                "   出典情報を RAGコンテキストの「出典：」フィールドからそのまま転記する\n\n"

                "回答では以下の観点を整理して述べてください。\n"
                "・学習指導要領が示している考え方や重視点\n"
                "・授業設計や教材研究で意識すべき観点\n"
                "・問いを考える際の軸や視点\n"
            )
        else:
            system = (
                "あなたはJEISIの教育思考支援AI『HARUHI』です。\n\n"

                "【重要】今回の問いに対して、HARUHIが参照するJEISIデータベース"
                "（学習指導要領・指導案）に該当する記述が見つかりませんでした。\n\n"

                "回答の冒頭に必ず以下の但し書きをそのまま記載してください。\n"
                "---\n"
                "⚠【AI一般回答】\n"
                "現時点でJEISIのデータベース（学習指導要領・指導案）には、\n"
                "この問いに直接対応する記述が登録されていません。\n"
                "以下はAIによる一般的な回答です。教育的判断の参考としてご活用ください。\n"
                "---\n\n"

                "但し書きの後に、教育的な観点から誠実に回答してください。\n"
                "回答は教員や教育関係者が実務で参考にできる内容を心がけてください。\n"
            )

        rag_context = (
            "=== 教育根拠 RAG コンテキスト ===\n"
            "[学習指導要領]\n" + cur_block + "\n\n"
            "[指導案]\n" + les_block + "\n"
            "================================="
        )

        user = f"{rag_context}\n\n質問：\n{user_query}"

        # ---------- メッセージ構築（PDG+直近履歴を注入） ----------
        messages = [{"role": "system", "content": system}]

        if context_messages:
            # コンテキスト履歴をsystem直後に挿入
            messages.append({
                "role": "system",
                "content": (
                    "=== 会話コンテキスト（PDG問いの系譜 + 直近の対話） ===\n"
                    "以下は現在の問いに至るまでの思考の流れです。\n"
                    "これを踏まえて、問いの意図と文脈を理解した上で回答してください。\n"
                )
            })
            messages.extend(context_messages)

        messages.append({"role": "user", "content": user})
        return messages

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
    def answer(self, user_query: str, context_messages: List[Dict[str, str]] = None):
        print("=== ANSWER() ENTER ===")

        # ① 校種・教科推定
        result = self._infer_stage_subject(user_query)
        if result is None:
            raise RuntimeError("_infer_stage_subject returned None")

        stage, subject = result
        print("[DEBUG] infer_stage_subject:", stage, subject)

        # ② 教科が取れない場合：問い返し
        if subject is None:
            print("RETURN: subject_none")
            msg = (
                "今の問いは、とても大切な観点を含んでいます。\n\n"
                "ただ、どの教科の立場から考えるかによって、"
                "『見方・考え方』や重視点が変わります。\n\n"
                "どの教科について考えたいか、教えてもらえますか？\n"
                "（例：小学校理科／社会／算数／外国語／道徳 など）"
            )
            return msg, {
                "curriculum":   [],
                "lesson_plans": [],
                "subject":      None,
                "stage":        stage,
                "reply_mode":   "ASK",
            }

        # ③ 動的 threshold（教科別調整）
        dyn_th = self._auto_threshold(user_query)

        if subject in ["SCIENCE", "MATH"]:
            dyn_th = max(dyn_th, 0.55)
        elif subject in ["JAPANESE", "SOCIAL", "FOREIGN_LANGUAGE", "MORAL"]:
            dyn_th = max(dyn_th, 0.40)
        elif subject == "GENERAL":
            dyn_th = max(dyn_th, 0.35)

        print("[DEBUG] threshold:", dyn_th)

        # ④ 学習指導要領RAG
        curriculum = self.search_curriculum(
            query=user_query,
            k=self.top_k,
            threshold=dyn_th,
            school_stage=stage,
            subject=subject,
        )
        print("[DEBUG] Curriculum RAG results:", curriculum)

        lessons = []  # 指導案RAGは現時点では停止

        # ⑤ reply_mode 判定
        reply_mode = "RAG" if (curriculum or lessons) else "LLM"
        print(f"[DEBUG] reply_mode: {reply_mode}")

        # ⑥ プロンプト構築（PDG+直近履歴を渡す）
        messages = self._build_prompt(user_query, curriculum, lessons, context_messages)
        if messages is None:
            raise RuntimeError("_build_prompt returned None")

        # ⑦ GPT 応答生成
        reply = self._generate(messages)
        if reply is None:
            raise RuntimeError("_generate returned None")

        print("RETURN: normal")

        return reply, {
            "curriculum":   curriculum,
            "lesson_plans": lessons,
            "subject":      subject,
            "stage":        stage,
            "reply_mode":   reply_mode,
        }