import re
import csv
import pdfplumber

# =========================
# 設定値（理科）
# =========================

PDF_PATH = "input/elementary_guidelines_main.pdf"
START_PRINTED_PAGE = 156
END_PRINTED_PAGE = 164
OUTPUT_CSV = "output/elementary_foreign_language_main.csv"

SCHOOL_STAGE = "elementary"
SUBJECT = "foreign_language"

# =========================
# 正規表現定義
# =========================

# 章レベル（※理科では「第○ 目標」「第○ 各学年の目標及び内容」など）
RE_CHAPTER = re.compile(r"^第([0-9０-９]+)[ 　]*(.+)$")

# 学年（〔第○学年〕）
RE_GRADE = re.compile(r"^[〔\[]第([0-9０-９]+)学年[〕\]]$")

# セクション（1 目標 / 2 内容 / 3 内容の取扱い）
RE_SECTION = re.compile(r"^([0-9０-９]+)[ 　]*(.+)$")

# item（A / B / 1 / 2）
RE_ITEM = re.compile(r"^([A-ZＡ-Ｚ0-9０-９])[ 　]*(.+)?$")

# sub_item（(1)）
RE_SUB_ITEM = re.compile(r"^[（(]([0-9０-９]+)[）)]")

# detail（ア / イ / ウ）
RE_DETAIL = re.compile(r"^([アイウエオカキクケコサシスセソタチツテト])[ 　]*(.+)?$")

# =========================
# PDF抽出（ページ番号指定）
# =========================

def extract_target_pages(pdf_path, start_page, end_page):
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.splitlines()

            printed_page = None
            for l in reversed(lines):
                l = l.strip()
                if l.isdigit():
                    printed_page = int(l)
                    break

            if printed_page is None:
                continue

            if start_page <= printed_page <= end_page:
                for line in lines:
                    line = line.strip()
                    if line:
                        results.append((line, printed_page))

    return results

# =========================
# 構造化処理（理科用）
# =========================

def structure_lines(lines):
    records = []

    chapter = None
    grade = None
    section = None
    item = None
    sub_item = None
    detail = None

    buffer = []
    buffer_page = None

    def flush():
        nonlocal buffer
        if buffer:
            records.append({
                "school_stage": SCHOOL_STAGE,
                "subject": SUBJECT,
                "chapter": chapter,
                "grade": grade,
                "section": section,
                "item": item,
                "sub_item": sub_item,
                "detail": detail,
                "text": " ".join(buffer),
                "source_page": buffer_page
            })
            buffer = []

    for line, page in lines:

        # 学年
        m = RE_GRADE.match(line)
        if m:
            flush()
            grade = m.group(1)
            section = item = sub_item = detail = None
            buffer_page = page
            continue

        # 章（第○ 目標 等）
        m = RE_CHAPTER.match(line)
        if m:
            flush()
            chapter = f"第{m.group(1)} {m.group(2)}"
            section = item = sub_item = detail = None
            buffer_page = page
            continue

        # セクション（1 目標 / 2 内容 / 3 内容の取扱い）
        m = RE_SECTION.match(line)
        if m and chapter:
            flush()
            section = f"{m.group(1)} {m.group(2)}"
            item = sub_item = detail = None
            buffer_page = page
            continue

        # item
        m = RE_ITEM.match(line)
        if m and section:
            flush()
            item = m.group(1)
            sub_item = detail = None
            buffer_page = page
            if m.group(2):
                buffer.append(m.group(2))
            continue

        # sub_item
        m = RE_SUB_ITEM.match(line)
        if m:
            flush()
            sub_item = m.group(1)
            detail = None
            buffer_page = page
            buffer.append(line)
            continue

        # detail
        m = RE_DETAIL.match(line)
        if m:
            flush()
            detail = m.group(1)
            buffer_page = page
            if m.group(2):
                buffer.append(m.group(2))
            continue

        # 通常テキスト
        buffer.append(line)
        if buffer_page is None:
            buffer_page = page

    flush()
    return records

# =========================
# CSV保存
# =========================

def save_csv(records, path):
    if not records:
        print("警告：出力レコードがありません")
        return

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "school_stage",
                "subject",
                "chapter",
                "grade",
                "section",
                "item",
                "sub_item",
                "detail",
                "text",
                "source_page"
            ]
        )
        writer.writeheader()
        writer.writerows(records)

# =========================
# 実行
# =========================

if __name__ == "__main__":
    lines = extract_target_pages(
        PDF_PATH,
        START_PRINTED_PAGE,
        END_PRINTED_PAGE
    )
    records = structure_lines(lines)
    save_csv(records, OUTPUT_CSV)
    print(f"完了：{len(records)} 件を出力しました")
