# -*- coding: utf-8 -*-
"""[가상자료 ⑫] 원본을 여러 형식으로 저장: xlsx · ods · csv · pdf · docx.

같은 시트 목록(sources.build_source 결과)을 형식만 바꿔 쓴다. 실제 업무 폴더처럼
'엑셀로 받은 자료, CSV 로 내려받은 자료, PDF 로 받은 자료'가 섞인 상황을 만들기 위해서다.
돌려주는 것: (만든 경로, 칸 위치 바꾸기 함수) — 정답표의 '출처'를 그 형식의 주소로 바꾼다(문서형은 None).
"""
import os
import re
from decimal import Decimal, ROUND_HALF_UP
import csv

from app.formats.xlsx import write_xlsx
from app.formats.ods_write import write_ods
from app.formats.pdf_write import PdfWriter
from app.formats.docx_write import DocxWriter

SHEET_FORMATS = ("xlsx", "ods", "csv")
DOC_FORMATS = ("pdf", "docx")


def _val(cell):
    return cell.get("v", "") if isinstance(cell, dict) else cell


def _half_up(v, d):
    """엑셀·한국 문서처럼 사사오입(파이썬 기본 반올림은 짝수 쪽으로 반올림해 .5에서 다름)."""
    return float(Decimal(repr(float(v))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def _shown(cell):
    """인쇄된 문서(PDF·워드)에 보이는 글자: 표시 형식대로."""
    v = _val(cell)
    fmt = cell.get("fmt") if isinstance(cell, dict) else None
    if isinstance(v, bool) or v is None:
        return ""
    if isinstance(v, (int, float)):
        if fmt:
            m = re.search(r"\.(0+)", fmt)
            d = len(m.group(1)) if m else 0
            if fmt.endswith("%"):
                return f"{_half_up(v * 100, d):.{d}f}%"
            return f"{_half_up(v, d):,.{d}f}" if "," in fmt else f"{_half_up(v, d):.{d}f}"
        return f"{v:,}" if isinstance(v, int) else f"{v:g}"
    return str(v)


def choose(rng, t, mix):
    if not mix:
        return "xlsx"
    if t.monthly:                       # 시트가 많은 원본은 CSV 로 쓰지 않는다(시트 하나만 담김)
        return rng.choice(["xlsx", "xlsx", "ods", "pdf"])
    return rng.choice(["xlsx", "xlsx", "ods", "csv", "pdf", "docx"])


def write_source(path_xlsx, sheets, fmt, main_sheet):
    stem = os.path.splitext(path_xlsx)[0]
    if fmt == "xlsx":
        write_xlsx(path_xlsx, sheets)
        return path_xlsx, lambda ref: ref
    if fmt == "ods":
        p = stem + ".ods"
        write_ods(p, sheets)
        return p, lambda ref: ref
    if fmt == "csv":
        p = stem + ".csv"
        sh = next(s for s in sheets if s["name"] == main_sheet)
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            for row in sh["rows"]:
                w.writerow([_val(c) if not isinstance(_val(c), float) else repr(_val(c)) for c in row])
        name = os.path.basename(stem)[:31]
        return p, lambda ref: f"{name}!{ref.split('!', 1)[1]}" if ref else ref
    builder = PdfWriter(os.path.basename(stem)) if fmt == "pdf" else DocxWriter(os.path.basename(stem))
    for sh in sheets:
        builder.heading(f"■ {sh['name']}")
        rows = [[_shown(c) for c in r] for r in sh["rows"]]
        title = [r for r in rows[:2] if len([x for x in r if x]) <= 1]
        for r in title:
            if any(r):
                builder.para(" ".join(x for x in r if x))
        body = rows[len(title):]
        if body:
            ncol = max(len(r) for r in body)
            builder.table([r + [""] * (ncol - len(r)) for r in body])
    p = stem + "." + fmt
    builder.save(p)
    return p, lambda ref: None
