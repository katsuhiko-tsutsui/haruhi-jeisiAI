# pdg_question_vectorizer_v2.py
"""
PDG v2 - 問いベクトル生成モジュール
OpenAI API v1 準拠
HARUHI StandAlone（2025）完全対応版
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

# .env読み込み
load_dotenv()

# OpenAIクライアント
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 使用する埋め込みモデル
EMBED_MODEL = "text-embedding-3-small"


def generate_question_vector(text: str) -> list:
    """
    問い（テキスト）からベクトルを生成する。
    HARUHI / PDG v2 / RAG すべて共通で使用可能。

    Parameters
    ----------
    text : str
        ベクトル化したい問い文

    Returns
    -------
    list
        1536 次元の embedding ベクトル
    """
    if not text or not isinstance(text, str):
        return []

    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )

    return response.data[0].embedding


if __name__ == "__main__":
    # 動作テスト
    vec = generate_question_vector("学習指導要領の目標構造を説明してください。")
    print(f"ベクトル次元: {len(vec)}")
    print(vec[:10])  # 先頭10要素だけ表示
