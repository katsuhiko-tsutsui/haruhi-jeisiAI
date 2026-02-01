# pdg_lineage_classifier.py

import os
from dotenv import load_dotenv
from supabase_client import supabase
import openai

# 環境変数読み込み
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai_api_key)

# GPT系譜判定プロンプト
PROMPT_TEMPLATE = """
あなたは「問いの系譜形成AI」です。
以下の新しい問い文と既存問い群を読み、次の手順で判定してください：

1. 新しい問い文が、既存問い群の中のどの問いの「派生・発展・関連深化」に当たるかを考えてください。
2. 最も関連性が高く「親問い」とみなせるものがある場合は、その問いのIDを返答してください。
3. 該当する親問いが存在しない場合は、「新規系譜」と判定してください。

### 出力形式：
- 親問いIDがある場合：親ID: [対象ID]
- 新規系譜の場合：新規系譜

新しい問い文：
{new_question}

既存問い群：
{existing_questions}
"""

def format_existing_questions(records):
    formatted = []
    for record in records:
        formatted.append(f"- ID: {record['id']}, 問い文: {record['message']}")
    return "\n".join(formatted)

def ask_gpt(new_question, existing_questions_formatted):
    prompt = PROMPT_TEMPLATE.format(
        new_question=new_question,
        existing_questions=existing_questions_formatted
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "あなたは系譜判定専門AIです。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0
    )

    result = response.choices[0].message.content.strip()
    return result

def classify_lineage():
    print("系譜判定処理開始")

    # ① 未系譜の新規問いを取得
    new_records = supabase.table("haruhi_chat_logs")\
        .select("id, message")\
        .eq("is_question", True)\
        .filter("parent_question_id", "is", "null")\
        .execute().data

    # ② 既存親候補の問いを取得
    existing_records = supabase.table("haruhi_chat_logs")\
        .select("id, message")\
        .eq("is_question", True)\
        .filter("parent_question_id", "not.is", "null")\
        .execute().data

    existing_questions_formatted = format_existing_questions(existing_records)

    for record in new_records:
        message_id = record["id"]
        message_content = record["message"]

        print(f"\n▶ 新規問い対象: {message_content}")

        if not existing_records:
            print("⚠ 既存親候補が存在しない → 新規系譜として処理")
            continue

        result = ask_gpt(message_content, existing_questions_formatted)
        print(f"→ GPT判定結果: {result}")

        if result.startswith("親ID:"):
            parent_id = result.replace("親ID:", "").strip()
            supabase.table("haruhi_chat_logs").update({
                "parent_question_id": parent_id
            }).eq("id", message_id).execute()
            print(f"✅ 系譜リンク付与: {parent_id}")
        elif result == "新規系譜":
            print("✅ 新規系譜として登録 (親ID付与なし)")
        else:
            print("⚠ GPT返答解析エラー：手動確認推奨")

    print("\n系譜判定処理 完了")

if __name__ == "__main__":
    classify_lineage()
