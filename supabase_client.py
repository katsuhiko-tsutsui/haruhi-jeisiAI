from supabase import create_client, Client
import os
from dotenv import load_dotenv

# .env を読み込む（Flask起動前でも確実に反映）
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("⚠️ SUPABASE_URL または SUPABASE_KEY が読み込めていません。 .env の場所と内容を確認してください。")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
