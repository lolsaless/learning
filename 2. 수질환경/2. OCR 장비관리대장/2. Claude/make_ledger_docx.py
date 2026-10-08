# -*- coding: utf-8 -*-
"""
마스터 엑셀(equipment.xlsx) -> '시험장비관리대장' 양식 Word 문서(.docx)

원본 HWP 양식(가로 A4, 앞면 + 뒷면)과 같은 표 격자·글꼴 크기로 장비마다 2쪽을 만든다.
한글(HWP)에서 .docx 를 열어 .hwp/.hwpx 로 다시 저장할 수 있다.

  python make_ledger_docx.py equipment.xlsx                       -> ledger.docx (전체, 엑셀과 같은 폴더)
  python make_ledger_docx.py equipment.xlsx --only 04-장비-05,04-장비-43
  python make_ledger_docx.py equipment.xlsx --per-file             -> ledger_docx/ 폴더에 장비별 파일
  python make_ledger_docx.py equipment.xlsx --font "맑은 고딕"       (경기천년바탕이 없는 PC)

필요 라이브러리: python-docx, pandas, openpyxl, Pillow   (pip install python-docx)
로고(logo.png)는 엑셀과 같은 폴더에 있으면 제목 왼쪽에 들어간다(equipment_extract.py 가 저장).
"""
import argparse
import os
import sys

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT as VA, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH as AL, WD_BREAK, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt
from PIL import Image

import ledger_common as lc
from ledger_common import (COMP_MIN_ROWS, COMP_ROW, HIST_COLS, HIST_PER_PAGE, HIST_ROWS, MAIN_COLS, MAIN_ROWS,
                           TITLE_TEXT, dot_date, load_master, maker_text, price_text, tel_text)

FONT = lc.FONT_NAME


# ───────────── 서식 도우미 ─────────────
def _font(run, size, bold=False):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)


def _para(p, align=AL.CENTER):
    pf = p.paragraph_format
    pf.space_before = pf.space_after = Pt(0)
    pf.line_spacing = 1.0
    p.alignment = align


def put(cell, text, size=10, bold=False, align=AL.CENTER, valign=VA.CENTER):
    """셀 내용을 text 로 교체 (\\n 은 줄바꿈)"""
    cell.vertical_alignment = valign
    p = cell.paragraphs[0]
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    _para(p, align)
    lines = str(text or "").split("\n")
    for i, line in enumerate(lines):
        run = p.add_run(line)
        _font(run, size, bold)
        if i < len(lines) - 1:
            run.add_break()


def merged(t, r1, c1, r2, c2, widths):
    """(r1,c1)~(r2,c2) 병합 후 폭 지정. 병합 셀 반환"""
    a = t.cell(r1, c1)
    cell = a.merge(t.cell(r2, c2)) if (r1, c1) != (r2, c2) else a
    cell.width = Mm(sum(widths[c1:c2 + 1]))
    return cell


def new_table(doc, nrows, widths, heights, borders=True):
    t = doc.add_table(rows=nrows, cols=len(widths))
    if borders:
        t.style = "Table Grid"
    t.autofit = False
    tblPr = t._tbl.tblPr
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblPr.append(lay)
    mar = OxmlElement("w:tblCellMar")                  # 셀 안쪽 여백(mm→twip)
    for side, v in (("top", 15), ("left", 60), ("bottom", 15), ("right", 60)):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:w"), str(v))
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    tblPr.append(mar)
    for i, w in enumerate(widths):
        t.columns[i].width = Mm(w)
        for c in t.columns[i].cells:
            c.width = Mm(w)
    for i, h in enumerate(heights):
        t.rows[i].height = Mm(h)
        t.rows[i].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    return t


def header_line(doc, r):
    p = doc.add_paragraph()
    _para(p, AL.LEFT)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.tab_stops.add_tab_stop(Mm(sum(MAIN_COLS)), WD_TAB_ALIGNMENT.RIGHT)
    run = p.add_run(f"물품명 : {r['name'] or ''}\t관리번호 ({r['mgmt']})")
    _font(run, 12, True)


def caption(doc, text):
    p = doc.add_paragraph()
    _para(p, AL.LEFT)
    p.paragraph_format.space_before = Pt(2)
    _font(p.add_run(text), 10, True)


def page_break(doc):
    p = doc.add_paragraph()
    _para(p, AL.LEFT)
    r = p.add_run()
    _font(r, 1)
    r.add_break(WD_BREAK.PAGE)
    p.paragraph_format.line_spacing = Pt(1)


# ───────────── 앞면 ─────────────
def add_photos(cell, paths, avail_h):
    """사진 칸: 1장=크게, 2장=나란히, 3~4장=2×2"""
    paths = paths[:4]
    n = len(paths)
    if n == 0:
        return
    box_w = 130 if n == 1 else 58   # 2장이 한 줄에 들어가도록 칸 폭(약 134mm)의 절반 미만
    box_h = avail_h if n <= 2 else avail_h / 2 - 2
    p = cell.paragraphs[0]
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    _para(p, AL.CENTER)
    for i, path in enumerate(paths):
        if n > 2 and i == 2:                                   # 3~4장이면 둘째 줄로
            p = cell.add_paragraph()
            _para(p, AL.CENTER)
        with Image.open(path) as im:
            w, h = im.size
        scale = min(box_w / w, box_h / h)
        run = p.add_run()
        run.add_picture(path, width=Mm(w * scale), height=Mm(h * scale))
        if i % 2 == 0 and i + 1 < n:
            p.add_run("  ")


def fit_size(perf, box_h=MAIN_ROWS[5] - 2 + 4, box_w=119.0):
    """성능 칸(높이 약 48mm)에 글이 들어가는 가장 큰 글자 크기(pt). 넘치면 표가 커져 다음 쪽으로 밀리므로 줄인다."""
    if not perf:
        return 10
    for size in (10, 9, 8, 7, 6.5):
        per_line = box_w / (size * 0.3528 * 0.62)            # 한 줄에 들어가는 글자 수(한글·영문 혼합 근사)
        lines = sum(max(1, -(-len(l) // int(per_line))) for l in perf.splitlines()) + 1   # +1: 제목줄
        if lines * size * 1.2 * 0.3528 <= box_h:
            return size
    return 6.5


def front_page(doc, r, logo):
    # 제목 표 (로고 + 제목)
    tt = new_table(doc, 1, [24.7, 230.3], [21], borders=False)
    lc_, tc = tt.cell(0, 0), tt.cell(0, 1)
    lc_.vertical_alignment = VA.CENTER
    if logo:
        _para(lc_.paragraphs[0], AL.LEFT)
        lc_.paragraphs[0].add_run().add_picture(logo, height=Mm(19))
    put(tc, TITLE_TEXT, 24, True)
    header_line(doc, r)

    n = max(COMP_MIN_ROWS, len(r["comps"]))
    # 구성내역이 5행을 넘으면 행 높이를 줄여 표 전체 높이를 기본(5행)과 같게 유지 -> 한 쪽에 들어감
    crow = COMP_ROW if n <= COMP_MIN_ROWS else max(5.5, COMP_ROW * (2 + COMP_MIN_ROWS) / (2 + n))
    heights = MAIN_ROWS + [crow] * (2 + n)                      # 행 0~5, 구성 제목, 머리글, 구성 n행
    W = MAIN_COLS
    t = new_table(doc, len(heights), W, heights)
    m = lambda *a: merged(t, *a, W)

    put(m(0, 0, 1, 1), "형식 및\n규격", 11, True)
    put(m(0, 2, 1, 2), "제 작 회 사\n(제 조 국)", 11, True)
    put(m(0, 3, 1, 3), "도 입\n년 월 일", 11, True)
    put(m(0, 4, 1, 6), "도입가격 (원)", 11, True)
    put(m(0, 7, 0, 9), "도 입 처", 11, True)
    put(m(0, 10, 1, 10), "용도 및 특기사항", 11, True)
    put(m(1, 7, 1, 7), "회 사 명", 11, True)
    put(m(1, 8, 1, 8), "주 소", 11, True)
    put(m(1, 9, 1, 9), "전 화 번 호", 11, True)

    put(m(2, 0, 4, 1), r["spec"])
    put(m(2, 2, 4, 2), maker_text(r))
    put(m(2, 3, 4, 3), dot_date(r["date"]))
    put(m(2, 4, 2, 6), price_text(r))
    put(m(2, 7, 4, 7), r["vendor"])
    put(m(2, 8, 4, 8), r["addr"])
    put(m(2, 9, 4, 9), tel_text(r))
    put(m(2, 10, 4, 10), r["use"])
    put(m(3, 4, 3, 6), "입고시 상태")
    put(m(4, 4, 4, 5), ("■" if r["cond"] == "신품" else "□") + " 신품")
    put(m(4, 6, 4, 6), ("■" if r["cond"] == "중고품" else "□") + "중고품")

    # 주요 성능 및 특징 (긴 글은 글자 크기를 줄여 한 쪽에 맞춘다)
    perf = r["perf"] or ""
    psize = fit_size(perf)
    pc = m(5, 0, 5, 6)
    put(pc, "주요 성능 및 특징", 10, True, AL.LEFT, VA.TOP)
    if perf:
        for l in perf.split("\n"):
            p = pc.add_paragraph()
            _para(p, AL.LEFT)
            _font(p.add_run(l), psize)

    put(m(6, 0, 6, 6), "장비구성내역", 10, True)
    put(m(7, 0, 7, 0), "연 번", 10, True)
    put(m(7, 1, 7, 3), "장비명", 10, True)
    put(m(7, 4, 7, 4), "수 량", 10)
    put(m(7, 5, 7, 6), "단위", 10)
    for i in range(n):
        c = r["comps"][i] if i < len(r["comps"]) else {}
        row = 8 + i
        put(m(row, 0, row, 0), str(i + 1))
        put(m(row, 1, row, 3), c.get("name"))
        put(m(row, 4, row, 4), c.get("qty"))
        put(m(row, 5, row, 6), c.get("unit"))

    photo_h = MAIN_ROWS[5] + crow * (2 + n) - 7   # 줄 간격 여유를 두어 쪽 넘김 방지
    pcell = m(5, 7, 7 + n, 10)
    pcell.vertical_alignment = VA.CENTER
    add_photos(pcell, r["photos"], photo_h)
    caption(doc, "(앞면)")


# ───────────── 뒷면 ─────────────
def back_pages(doc, r):
    hist = r["hist"]
    pages = max(1, -(-len(hist) // HIST_PER_PAGE))
    W, half = HIST_COLS, HIST_PER_PAGE // 2
    for pg in range(pages):
        if pg:
            page_break(doc)
        header_line(doc, r)
        t = new_table(doc, 3 + half, W, HIST_ROWS[:3] + [HIST_ROWS[3]] * half)
        m = lambda *a: merged(t, *a, W)
        put(m(0, 0, 0, 7), "수리 또는 부품 교체 이력", 11, True)
        for c0 in (0, 4):
            put(m(1, c0, 2, c0), "일 자", 11, True)
            put(m(1, c0 + 1, 2, c0 + 1), "내 용", 11, True)
            put(m(1, c0 + 2, 1, c0 + 3), "결 재", 11, True)
            put(m(2, c0 + 2, 2, c0 + 2), "담당자", 10)
            put(m(2, c0 + 3, 2, c0 + 3), "팀장", 10)
        part = hist[pg * HIST_PER_PAGE:(pg + 1) * HIST_PER_PAGE]
        for i in range(half):                                   # 왼쪽 9칸 먼저, 그다음 오른쪽 9칸
            for c0, item in ((0, part[i] if i < len(part) else None),
                             (4, part[i + half] if i + half < len(part) else None)):
                put(t.cell(3 + i, c0), item and item["date"], 10)
                put(t.cell(3 + i, c0 + 1), item and item["content"], 9, False, AL.LEFT, VA.TOP)
                put(t.cell(3 + i, c0 + 2), "")
                put(t.cell(3 + i, c0 + 3), "")
        caption(doc, "(뒷면)")


# ───────────── 문서 조립 ─────────────
def make_doc(recs, logo):
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Mm(297), Mm(210)
    sec.left_margin = sec.right_margin = Mm(20)
    sec.top_margin, sec.bottom_margin = Mm(8), Mm(5)
    sec.header_distance = sec.footer_distance = Mm(0)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = FONT, Pt(10)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    for i, r in enumerate(recs):
        if i:
            page_break(doc)
        front_page(doc, r, logo)
        page_break(doc)
        back_pages(doc, r)
    return doc


def build(excel_path, out_docx=None, only=None, per_file=False):
    recs, logo = load_master(excel_path)
    if only:
        want = {x.strip() for x in only}
        recs = [r for r in recs if r["mgmt"] in want]
        if not recs:
            sys.exit("--only 에 해당하는 관리번호가 없습니다.")
    base = os.path.dirname(os.path.abspath(excel_path))
    if per_file:
        out_dir = out_docx or os.path.join(base, "ledger_docx")
        os.makedirs(out_dir, exist_ok=True)
        for r in recs:
            fn = os.path.join(out_dir, f"시험장비관리대장_{lc_safe(r['mgmt'])}.docx")
            make_doc([r], logo).save(fn)
        print(f"장비별 Word 양식 {len(recs)}개 생성: {out_dir}")
        return out_dir
    out_docx = out_docx or os.path.join(base, "ledger.docx")
    make_doc(recs, logo).save(out_docx)
    print(f"Word 양식 생성: {out_docx} (장비 {len(recs)}건, {len(recs) * 2}쪽 안팎)")
    return out_docx


def lc_safe(s):
    import re
    return re.sub(r'[\\/:*?"<>|~\s]+', "_", s)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("excel")
    ap.add_argument("--out", default=None, help="출력 파일(또는 --per-file 일 때 폴더)")
    ap.add_argument("--only", default=None, help="관리번호를 쉼표로 (예: 04-장비-05,04-장비-43)")
    ap.add_argument("--per-file", action="store_true", help="장비별로 파일 하나씩 생성")
    ap.add_argument("--font", default=None, help="글꼴 이름 (기본: 경기천년바탕 Regular)")
    a = ap.parse_args()
    if not os.path.exists(a.excel):
        sys.exit(f"엑셀 파일을 찾을 수 없습니다: {a.excel}")
    if a.font:
        FONT = a.font
    build(a.excel, a.out, a.only.split(",") if a.only else None, a.per_file)
