import pdfplumber
import csv
import re
from pathlib import Path

# =========================
# 設定（人が触るのはここだけ）
# =========================

PDF_PATH = "input/junior_high_guidelines_main.pdf"
OUTPUT_CSV = "output/junior_high_science_main.csv"

START_PRINTED_PAGE = 78
END_PRINTED_PAGE = 98

SCHOOL_STAGE = "junior_high"
SUBJECT = "SCIENCE"

def normalize_for_structure(line: str, subject: str) -> str:
    """
    構造判定専用の正規化
    算数のみ：文頭インデントを無視
    """
    if subject == "SCIENCE":
        return line.lstrip()
    return line

# =========================
# 印字ページ番号抽出
# =========================
def is_ruby_like(text: str) -> bool:
    t = text.strip()
    if len(t) <= 6:
        return True
    if re.fullmatch(r"[ぁ-んー]+", t):
        return True
    return False

def extract_printed_page_number(page):
    h = page.height
    cropped = page.within_bbox((0, h * 0.8, page.width, h))
    for w in cropped.extract_words(use_text_flow=True):
        t = w["text"].strip()
        if t.isdigit() and len(t) <= 3:
            return int(t)
    return None

# =========================
# 対象ページ抽出
# =========================

def extract_target_pages(pdf_path, start, end):
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        # 印字ページ番号 → 物理ページindex の対応表
        printed_to_index = {}
        printed_nums = []

        for i, page in enumerate(pdf.pages):
            num = extract_printed_page_number(page)
            if num is not None:
                printed_to_index[num] = i
                printed_nums.append(num)

        if not printed_nums:
            raise RuntimeError("印字ページ番号が1つも検出できませんでした。")

        printed_nums.sort()
        first_printed = printed_nums[0]
        first_index = printed_to_index[first_printed]

        # 指定された印字ページ範囲を順に処理
        for printed_p in range(start, end + 1):
            if printed_p in printed_to_index:
                page = pdf.pages[printed_to_index[printed_p]]
            else:
                # ★ フォールバック：連続性仮定で物理indexを補完
                fallback_index = first_index + (printed_p - first_printed)
                if fallback_index < 0 or fallback_index >= len(pdf.pages):
                    continue
                page = pdf.pages[fallback_index]

            text = page.extract_text()

            # ★ 教科冒頭ページ対策：extract_text が失敗した場合のみフォールバック
            if not text:
               words = page.extract_words(use_text_flow=True)
               if not words:
                  continue
               text = "\n".join(w["text"] for w in words)

            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if is_ruby_like(line):
                    continue
                lines.append((printed_p, line))

    return lines


# =========================
# 構造化（最終確定版）
# =========================

def structure_lines(lines):
    records = []

    chapter = grade = item = sub_item = detail = None
    section_title = None

    buffer = []
    buffer_page = None

    def flush():
        if buffer:
            records.append({
                "school_stage": SCHOOL_STAGE,
                "subject": SUBJECT,
                "chapter": chapter,
                "grade": grade,          # None 可
                "section": section_title,
                "item": item,
                "sub_item": sub_item,
                "detail": detail,
                "text": "\n".join(buffer),
                "source_page": buffer_page
            })

    for page, line in lines:
        check_line = normalize_for_structure(line, SUBJECT)

        # ---- 章（第○章 単独）----
        m = re.match(r"^第([0-9０-９]+)章\s*$", check_line)
        if m:
            flush()
            chapter = m.group(1)
            grade = item = sub_item = detail = None
            buffer = []
            buffer_page = None
            continue

        # ---- 節（第○ ＋ 見出し）----
        m = re.match(r"^第([0-9０-９]+)[　\s]+(.+)$", check_line)
        if m:
            flush()
            grade = m.group(1)
            section_title = m.group(2).strip()  # ← 追加ポイント
            item = sub_item = detail = None
            buffer = []
            buffer_page = None
            continue

        # --- 学年ラベル（〔第○学年〕） ---
        m = re.match(r"^[〔\[]第([0-9０-９]+)学年[〕\]]$", line)
        if m:
            flush()
            grade = f"第{m.group(1)}学年"
            section_title = None
            item = sub_item = detail = None
            buffer = []
            buffer_page = page
            continue

        # ---- section（理科・算数：A/B/C/D ＋ 見出し）----
        m = re.match(r"^([A-DＡ-Ｄ])[　\s]+(.+)$", check_line)
        if m:
            flush()
            grade = m.group(1)
            section_title = m.group(2).strip()
            # chapter は維持
            item = sub_item = detail = None
            buffer = []
            buffer_page = None
            continue
     
        # ---- item（〔思考力，判断力，表現力等〕など）----
        if SUBJECT == "SCIENCE":
           m = re.match(r"^[〔［\[](.+)[〕］\]]$", check_line)
           if m:
               flush()
               item = m.group(1)  # 中身を item に
               sub_item = detail = None
               buffer = [line]
               buffer_page = page
               continue

        # ---- item（1 2 3）----
        m = re.match(r"^([0-9０-９]+)[　\s]", check_line)
        if m:
            flush()
            item = m.group(1)
            sub_item = detail = None
            buffer = [line]
            buffer_page = page
            continue

        # ---- sub_item（⑴ ⑵ …）----
        m = re.match(r"^([⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽])", check_line)
        if m:
            flush()
            sub_item = m.group(1)
            detail = None
            buffer = [line]
            buffer_page = page
            continue

        # ---- detail（ア イ ウ… ※空白必須）----
        m = re.match(r"^([ア-ン])[　\s]+", check_line)
        if m:
            flush()
            detail = m.group(1)
            buffer = [line]
            buffer_page = page
            continue

        # ---- 通常本文（改行・ページ跨ぎ対応）----
        if buffer:
            buffer.append(line)

    flush()
    return records

# =========================
# CSV 出力
# =========================

def save_csv(records, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "school_stage", "subject", "chapter",
        "grade", "section",
        "item", "sub_item", "detail",
        "text", "source_page"
    ]

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            w.writerow(r)

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
