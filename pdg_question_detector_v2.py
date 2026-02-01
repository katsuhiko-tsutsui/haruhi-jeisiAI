# pdg_question_detector_v2.py
"""
PDG v2 - 問い判定モジュール
OpenAI API v1 準拠
HARUHI StandAlone（2025）対応版
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

# .env 読み込み
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DETECT_PROMPT = """
あなたは「問い判定AI」です。
以下のユーザー発話が「問い（質問）」か「問いではない（依頼・感想・命令）」か判定し、
必ず次のどちらかで返してください：

- QUESTION
- NOT_QUESTION

【判定ルール】
- 「〜は何ですか？」「どうすれば〜？」「なぜ〜？」など → QUESTION
- 命令・依頼（例：〜して、作って、生成して） → NOT_QUESTION
- 感想・雑談・単なる発話 → NOT_QUESTION
- 文末が「？」でなくても、意味が問いなら QUESTION とする

対象発話：
"{text}"
"""

def is_question(text: str) -> bool:
    """
    GPTを用いてテキストが問いかどうか判定する
    """
    if not text:
        return False

    prompt = DETECT_PROMPT.format(text=text)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "あなたは精密な問い判定AIです。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0
    )

    result = response.choices[0].message.content.strip()
    return result == "QUESTION"


if __name__ == "__main__":
    # テスト
    tests = [
        "学習指導要領の構造を教えてください。",
        "こんにちは。",
        "PDFをExcelに変換して。",
        "なぜ月は自転するのですか",
        "生成AIって結局どうなる？"
    ]

    for t in tests:
        print(f"{t} → {is_question(t)}")
