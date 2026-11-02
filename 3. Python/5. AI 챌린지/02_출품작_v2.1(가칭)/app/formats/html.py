# -*- coding: utf-8 -*-
"""[파일 형식] HTML 읽기 → 문단·표 블록(rowspan·colspan 포함), 또는 표를 시트로 바꾼 Workbook.

통계·전자문서 시스템이 'xls' 이름으로 내보내는 HTML 표 파일도 이것으로 읽는다(xls.py 가 넘겨 줌).
"""
import re
from html.parser import HTMLParser

from app.common import numbers as N
from app.formats.text import read_text_file
from app.formats.xlsx.model import Cell, Sheet, Workbook

BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "tr", "title"}


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.buf = []
        self.stack = []          # 진행 중인 표들
        self.skip = 0

    def flush(self):
        t = re.sub(r"[ \t ]+", " ", "".join(self.buf)).strip()
        self.buf = []
        if t and not self.stack:
            self.blocks.append({"type": "p", "text": t})
        return t

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "table":
            self.flush()
            self.stack.append({"rows": [], "row": None, "cell": None})
        elif self.stack and tag == "tr":
            self.stack[-1]["row"] = []
            self.stack[-1]["rows"].append(self.stack[-1]["row"])
        elif self.stack and tag in ("td", "th"):
            t = self.stack[-1]
            if t["row"] is None:
                t["row"] = []
                t["rows"].append(t["row"])
            t["cell"] = {"text": [], "rs": int(a.get("rowspan") or 1), "cs": int(a.get("colspan") or 1)}
            t["row"].append(t["cell"])
        elif tag == "br":
            self.buf.append("\n")
        elif tag in BLOCK_TAGS and not self.stack:
            self.flush()

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag == "table" and self.stack:
            t = self.stack.pop()
            b = _grid(t["rows"])
            if self.stack:          # 표 안의 표: 글자만 바깥 칸에
                if self.stack[-1]["cell"] is not None and b:
                    self.stack[-1]["cell"]["text"].append(" ".join(c["text"] for c in b["cells"]))
            elif b:
                self.blocks.append(b)
        elif tag in BLOCK_TAGS and not self.stack:
            self.flush()

    def handle_data(self, data):
        if self.skip:
            return
        if self.stack and self.stack[-1]["cell"] is not None:
            self.stack[-1]["cell"]["text"].append(data)
        elif not self.stack:
            self.buf.append(data)


def _grid(rows):
    cells, taken = [], set()
    for r, row in enumerate(rows):
        c = 0
        for cell in row:
            while (r, c) in taken:
                c += 1
            txt = re.sub(r"\s+", " ", "".join(cell["text"])).strip()
            cells.append({"r": r, "c": c, "rs": cell["rs"], "cs": cell["cs"], "text": txt})
            for rr in range(r, r + cell["rs"]):
                for cc in range(c, c + cell["cs"]):
                    taken.add((rr, cc))
            c += cell["cs"]
    if not cells:
        return None
    return {"type": "table", "cells": cells, "nrow": max(x["r"] + x["rs"] for x in cells),
            "ncol": max(x["c"] + x["cs"] for x in cells)}


def read_html(path):
    p = _P()
    p.feed(read_text_file(path))
    p.close()
    p.flush()
    return {"blocks": p.blocks, "warnings": []}


def read_html_book(path):
    """HTML 안의 표를 시트 하나씩으로(엑셀처럼 A1 주소로 출처를 남길 수 있게)."""
    d = read_html(path)
    wb = Workbook()
    for b in d["blocks"]:
        if b["type"] != "table":
            continue
        sh = Sheet(f"표{len(wb.sheets) + 1}")
        wb.sheets.append(sh)
        for c in b["cells"]:
            v = c["text"]
            if not v:
                continue
            tok = N.parse_cell(v)
            cell = Cell(tok["value"], "n", v) if tok and tok.get("value") is not None and not re.search(r"[가-힣A-Za-z]{2,}", v) \
                else Cell(v, "s", v)
            sh.cells[(c["r"], c["c"])] = cell
            sh.maxr = max(sh.maxr, c["r"])
            sh.maxc = max(sh.maxc, c["c"])
    if not wb.sheets:
        wb.warnings.append("HTML 안에 표가 없습니다")
    return wb
