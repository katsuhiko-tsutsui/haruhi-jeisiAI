# pdg_lineage_v2.py
"""
PDG v2 - 系譜推論エンジン（A案：類似度検索 + GPT最終判定）
HARUHI StandAlone（2025）仕様対応
"""

import os
from openai import OpenAI
from dotenv import load_dotenv
from supabase_client import supabase

from pdg_question_vectorizer_v2 import generate_question_vector
from pdg_question_detector_v2 import is_question

# === 環境変数 ===
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === 類似度閾値 ===
SIMILARITY_THRESHOLD = 0.80


# --------------------------------------
# GPT 最終判定（親子関係が妥当か確認）
# --------------------------------------
GPT_CHECK_PROMPT = """
あなたは「問いの系譜」を見極める教育AIです。

以下の２つの問いについて、
新しい問いが既存の問いの「発展・深化・派生」に当たるかどうかを判定してください。

### 既存の問い（候補）
{parent_question}

### 新しい問い
{new_question}

### 判定基準
- 論点・概念・文脈が受け継がれている場合 → YES
- 表面的な単語一致やテーマが異なる場合 → NO
- 無関係・異分野 → NO

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
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "あなたは教育文脈の系譜判定AIです。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0
    )

    result = response.choices[0].message.content.strip()
    return result == "YES"


# --------------------------------------
# PDG v2 main：parent_id 推論 + 保存処理
# --------------------------------------
def determine_parent_id(message_text: str):
    """
    1) 問い判定
    2) ベクトル生成
    3) RPC により類似問い検索
    4) GPT による最終確認（A案）
    """

    # ① 問いでなければ PDG 対象外
    if not is_question(message_text):
        return None, 0.0, None

    # ② ベクトル生成
    q_vec = generate_question_vector(message_text)

    # ③ Supabase RPC で類似問い取得
    response = supabase.rpc(
        "match_questions_v2",
        {
            "query_embedding": q_vec,
            "match_count": 5
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


# --------------------------------------
# 保存処理と連携するための外部IF
# --------------------------------------
def process_pdg_for_message(message_text: str):
    """
    HARUHI の保存処理から利用する外部IF。
    呼び出すと parent_id 判定結果が返る。
    """
    parent_id, similarity, parent_text = determine_parent_id(message_text)

    return {
        "parent_id": parent_id,
        "similarity": similarity,
        "parent_text": parent_text
    }


if __name__ == "__main__":
    # 動作確認
    test = "ICT活用は学習指導要領のどこに位置づく？"
    result = process_pdg_for_message(test)
    print(result)
