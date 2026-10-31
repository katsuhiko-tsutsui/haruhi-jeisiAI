# pdg_lineage_v2.py
"""
PDG v2 - 系譜推論エンジン（A案：類似度検索 + GPT最終判定）
HARUHI StandAlone（2025）仕様対応
"""

import os
from openai import OpenAI
from dotenv import load_dotenv
from supabase_client import supabase

# === 環境変数 ===
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === 類似度閾値 ===
SIMILARITY_THRESHOLD = 0.80


# --------------------------------------
# GPT 最終判定（親子関係が妥当か確認）
# --------------------------------------
GPT_CHECK_PROMPT = """
あなたは「問いの系譜」を判定する教育AIです。

以下の2つの問いについて、
新しい問いが、既存の問いの内容・論点・文脈を受け継いで生じた
系譜的に関連する問いであるかどうかを判定してください。

### 既存の問い（候補）
{parent_question}

### 新しい問い
{new_question}

### 判定基準
- 論点・概念・文脈が受け継がれている場合 → YES
- 既存の問いを具体化・派生・再焦点化・再構成した問いである場合 → YES
- 表面的な単語一致だけで、文脈上のつながりがない場合 → NO
- 無関係、または異なる論点に移っている場合 → NO

### 出力形式（必ずどちらか）：
YES
NO
"""


def check_parent_with_gpt(parent_question: str, new_question: str) -> bool:
    """
    GPT による最終的な親子関係確認
    """
    prompt = GPT_CHECK_PROMPT.format(
        parent_question=parent_question,
        new_question=new_question
    )

    response = client.chat.completions.create(
        model="gpt-6.1-sol",
        messages=[
            {"role": "system", "content": "あなたは問い同士の系譜的関係を判定するAIです。"},
            {"role": "user", "content": prompt},
        ],
    )

    result = response.choices[0].message.content.strip()

    print(f"[PDG lineage GPT raw result] {repr(result)}", flush=True)
    
    return result == "YES"


# --------------------------------------
# PDG v2 main：parent_id 推論 + 保存処理
# --------------------------------------
def determine_parent_id(
    message_text: str,
    user_id: str,
    q_vec
):
    """
    1) 生成済みの問いベクトルを受け取る
    2) RPC により類似問いを検索する
    3) GPT により親子関係を最終確認する
    """

    # ③ Supabase RPC で類似問い取得
    response = supabase.rpc(
        "match_questions_v2",
        {
            "query_embedding": q_vec,
            "match_count": 5,
            "p_user_id": user_id
        }
    ).execute()

    matches = response.data or []
    if not matches:
        return None, 0.0, None

    # 最上位候補
    top = matches[0]
    similarity = float(top["similarity"])
    parent_question_id = top["id"]
    parent_question_text = top["message"]

    # ④ 類似度が低い場合は親なし（新規系譜）
    if similarity < SIMILARITY_THRESHOLD:
        return None, similarity, None

    # ⑤ GPT による最終チェック
    is_valid = check_parent_with_gpt(
        parent_question=parent_question_text,
        new_question=message_text
    )

    if not is_valid:
        return None, similarity, None

    # ⑥ 親ID確定
    return parent_question_id, similarity, parent_question_text
