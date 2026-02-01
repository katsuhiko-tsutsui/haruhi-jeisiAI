# embed_curriculum_entries.py
# =========================================
# curriculum_entries 用 Embedding 生成（最終版）
# - embedding が NULL の行のみ対象
# - 小学校／中学校／全教科共通
# =========================================
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from supabase import create_client
import os
import time


# ===== 環境変数 =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ===== 初期化 =====
client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===== 設定 =====
TABLE_NAME = "curriculum_entries"
TEXT_COLUMN = "content"
EMBEDDING_COLUMN = "embedding"

EMBEDDING_MODEL = "text-embedding-3-small"
SLEEP_SEC = 0.3   # レート制限対策（安全寄り）

# ===== メイン処理 =====
def generate_embeddings():
    print("=== Embedding generation started ===")

    response = (
        supabase
        .table(TABLE_NAME)
        .select(f"id,{TEXT_COLUMN}")
        .is_(EMBEDDING_COLUMN, "null")
        .execute()
    )

    records = response.data

    if not records:
        print("No records to embed.")
        return

    total = len(records)
    print(f"Target records: {total}")

    for idx, record in enumerate(records, start=1):
        record_id = record["id"]
        text = record.get(TEXT_COLUMN)

        if not text or not text.strip():
            print(f"[SKIP] {idx}/{total} id={record_id} (empty content)")
            continue

        try:
            embedding = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            ).data[0].embedding

            supabase.table(TABLE_NAME).update(
                {EMBEDDING_COLUMN: embedding}
            ).eq("id", record_id).execute()

            print(f"[OK] {idx}/{total} id={record_id}")
            time.sleep(SLEEP_SEC)

        except Exception as e:
            print(f"[ERROR] {idx}/{total} id={record_id} : {e}")
            time.sleep(1)

    print("=== Embedding generation finished ===")

# ===== 実行 =====
if __name__ == "__main__":
    generate_embeddings()
