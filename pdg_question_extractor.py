# pdg_question_extractor.py

import re

from supabase_client import supabase

QUESTION_PATTERNS = [
    r"なぜ.*",
    r"どのように.*",
    r"どうすれば.*",
    r"もし.*なら.*",
    r"何が.*",
    r"どんな.*",
    r"どこで.*",
    r"誰が.*",
    r"いつ.*",
    r"どうして.*",
    r"どちら.*",
    r"どうなる.*",
    r"何故.*",
]

def is_question(text):
    for pattern in QUESTION_PATTERNS:
        if re.search(pattern, text):
            return True
    return False

def extract_and_update_questions():
    print("PDG抽出処理開始")

    # データ取得
    records = supabase.table("haruhi_chat_logs").select("id, message, is_question").execute().data

    updated_count = 0

    for record in records:
        message_id = record["id"]
        message_content = record["message"]

        if message_content and is_question(message_content):
            if not record.get("is_question"):
                supabase.table("haruhi_chat_logs").update({
                    "is_question": True
                }).eq("id", message_id).execute()
                updated_count += 1

    print(f"抽出完了: {updated_count}件の問い文を更新")

if __name__ == "__main__":
    extract_and_update_questions()
