# pdg_question_classifier.py

import os
import re
from dotenv import load_dotenv

from supabase_client import supabase

# OpenAI新API準拠
import openai

# .env読み込み
load_dotenv()

# APIキー読込
openai_api_key = os.getenv("OPENAI_API_KEY")

# 新APIクライアント生成
client = openai.OpenAI(api_key=openai_api_key)

# GPTプロンプトテンプレート
PROMPT_TEMPLATE = """
あなたは対話履歴の問いを分類するAIです。
以下の「問い文」を読み、最も適切なラベルを一つ選んでください。

### ラベル一覧：
- 教育設計問い：授業構造・教材設計に関する問い
- 誠育成問い：学習者の省察・成長支援に関する問い
- 神祇秩序問い：秩序・鎮護・精神的構造に関する問い
- 哲学探求問い：存在論・人文・哲学的思索に関する問い
- 技術設計問い：AIシステムや技術的実装に関する問い

問い文:
{question}

出力は以下の形式にしてください：
ラベル: [ラベル名]
"""

def classify_question(question_text):
    """GPT新APIで分類ラベルを取得"""
    prompt = PROMPT_TEMPLATE.format(question=question_text)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "あなたは分類専門AIです。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0
    )

    result = response.choices[0].message.content
    label = result.replace("ラベル: ", "").strip()
    return label

def classify_and_update():
    print("PDG分類処理開始")

    # is_question=True かつ question_category=None の未分類対象を取得
    records = supabase.table("haruhi_chat_logs")\
        .select("id, message, question_category")\
        .eq("is_question", True)\
        .is_("question_category", None)\
        .execute().data

    updated_count = 0

    for record in records:
        message_id = record["id"]
        message_content = record["message"]

        print(f"分類対象問い文: {message_content}")

        label = classify_question(message_content)

        supabase.table("haruhi_chat_logs").update({
            "question_category": label
        }).eq("id", message_id).execute()

        print(f"→ 分類結果: {label}")
        updated_count += 1

    print(f"分類完了: {updated_count}件の問い文にラベル付与")

if __name__ == "__main__":
    classify_and_update()
