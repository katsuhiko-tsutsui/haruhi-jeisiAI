import os
from supabase import create_client
from tabulate import tabulate

# ----------------------------------------
# Supabase 接続（直書き版）
# ----------------------------------------
SUPABASE_URL = "https://wsyyeqpnwoznwfmzydvl.supabase.co"   # ←代表の値に置換
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndzeXllcXBud296bndmbXp5ZHZsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg1MjMzODMsImV4cCI6MjA2NDA5OTM4M30.b214yzmrZ2aTFK1CWlCb5wrZroUg2GBG9E_8E3D4hDE"                      # ←anon keyでOK

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------------------
# 抽出するキーワード（熱領域）
# ----------------------------------------
KEYWORDS = ["熱", "温まり", "温め", "温度", "エネルギー", "金属", "水", "伝わり"]

def main():
    print("\n=== JEISI 小学校理科：熱領域（ものの温まり方）スキャン ===\n")

    # 小学校 × 理科 をまず抽出
    response = (
        supabase.table("curriculum_entries")
        .select("chapter, section, subsection, content, source_page")
        .eq("school_stage", "小学校")
        .eq("subject", "理科")
        .execute()
    )

    rows = response.data or []
    print(f"小学校理科エントリ数：{len(rows)} 件\n")

    # 熱領域フィルタ
    heat_rows = [
        r for r in rows
        if any(k in (r.get("content") or "") for k in KEYWORDS)
    ]

    print(f"熱領域の該当行：{len(heat_rows)} 件\n")

    if not heat_rows:
        print("→ 熱領域（ものの温まり方）が Supabase に存在しません。")
        print("→ 構造化がその章を読み取れていない可能性が濃厚です。")
        return

    # 表形式で概要表示
    table = []
    for r in heat_rows:
        table.append(
            [
                r.get("chapter"),
                r.get("section"),
                r.get("subsection"),
                r.get("source_page"),
                (r.get("content") or "")[:80] + "…",
            ]
        )

    print(tabulate(
        table,
        headers=["Chapter", "Section", "SubSec", "Page", "Content(80字)"],
        tablefmt="grid",
    ))

    print("\n=== スキャン完了 ===\n")


if __name__ == "__main__":
    main()
