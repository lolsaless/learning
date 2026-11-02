# -*- coding: utf-8 -*-
"""[파일 형식] 오픈문서 읽기: ods(스프레드시트) → Workbook, odt(문서) → 문단·표 블록. 표준 라이브러리만.

전자문서시스템에서 내려받은 공문(odt), LibreOffice·한컴오피스에서 저장한 ods 를 읽는다.
"""
import zipfile
import xml.etree.ElementTree as ET

from app import config
from app.formats.xlsx.model import Cell, Sheet, Workbook, _num_text

NS = {"office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
      "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
      "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
T = {k: "{%s}%s" % (NS[p], k) for p, ks in {
    "table": ["table", "table-row", "table-cell", "covered-table-cell", "number-rows-repeated", "number-columns-repeated",
              "number-columns-spanned", "number-rows-spanned", "name", "table-header-rows", "table-row-group", "table-rows"],
    "text": ["p", "h", "s", "tab", "line-break", "list", "list-item", "span", "a", "c"],
    "office": ["value-type", "value", "body", "text", "spreadsheet", "date-value", "boolean-value"]}.items() for k in ks}
MAX_REPEAT = 1000           # 끝까지 이어지는 빈 행·열(수만 개 반복)을 막는다


class OdfError(Exception):
    pass


def _content(path):
    try:
        with zipfile.ZipFile(path) as z:
            return ET.fromstring(z.read("content.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        raise OdfError(f"오픈문서 파일을 열 수 없습니다: {e}")


def text_of(el):
    """text:p 안의 글자(공백 개수·탭·줄바꿈 포함)."""
    out = [el.text or ""]
    for ch in el:
        if ch.tag == T["s"]:
            out.append(" " * int(ch.get(T["c"], "1")))
        elif ch.tag == T["tab"]:
            out.append("\t")
        elif ch.tag == T["line-break"]:
            out.append("\n")
        else:
            out.append(text_of(ch))
        out.append(ch.tail or "")
    return "".join(out)


def _cell_text(cell):
    return "\n".join(text_of(p) for p in cell.iter() if p.tag in (T["p"], T["h"]))


def _rows(tbl):
    for el in tbl:
        if el.tag == T["table-row"]:
            yield el
        elif el.tag in (T["table-header-rows"], T["table-row-group"], T["table-rows"]):
            yield from _rows(el)


def read_ods(path, max_cells=None):
    max_cells = max_cells or config.MAX_CELLS_PER_SHEET
    root = _content(path)
    wb = Workbook()
    for tbl in root.iter(T["table"]):
        sh = Sheet(tbl.get(T["name"]) or f"시트{len(wb.sheets) + 1}")
        wb.sheets.append(sh)
        r = 0
        count = 0
        for row in _rows(tbl):
            rrep = min(int(row.get(T["number-rows-repeated"], "1")), MAX_REPEAT)
            line = []
            for cell in row:
                if cell.tag not in (T["table-cell"], T["covered-table-cell"]):
                    continue
                crep = min(int(cell.get(T["number-columns-repeated"], "1")), MAX_REPEAT)
                vt = cell.get(T["value-type"])
                txt = _cell_text(cell)
                c = None
                if vt in ("float", "percentage", "currency"):
                    x = float(cell.get(T["value"]))
                    c = Cell(x, "n", txt.strip() or _num_text(x))     # 화면 표시 글자를 그대로(자릿수 유지)
                elif vt == "date":
                    c = Cell(cell.get(T["date-value"]), "d", txt or cell.get(T["date-value"]))
                elif vt == "boolean":
                    c = Cell(cell.get(T["boolean-value"]) == "true", "b", txt)
                elif txt:
                    c = Cell(txt, "s", txt)
                line.extend([c] * crep)
            if any(x is not None for x in line):
                for k in range(rrep):
                    for ci, c in enumerate(line):
                        if c is not None:
                            sh.cells[(r + k, ci)] = c
                            sh.maxr = max(sh.maxr, r + k)
                            sh.maxc = max(sh.maxc, ci)
                            count += 1
            r += rrep
            if count >= max_cells:
                sh.truncated = True
                wb.warnings.append(f"시트 '{sh.name}'가 커서 앞 {max_cells:,}칸만 읽음")
                break
    if not wb.sheets:
        raise OdfError("시트가 없습니다")
    return wb


def _table_block(tbl):
    cells = []
    covered = set()
    for r, row in enumerate(_rows(tbl)):
        c = 0
        for cell in row:
            if cell.tag == T["covered-table-cell"]:
                c += int(cell.get(T["number-columns-repeated"], "1"))
                continue
            if cell.tag != T["table-cell"]:
                continue
            crep = min(int(cell.get(T["number-columns-repeated"], "1")), 64)
            for _ in range(crep):
                while (r, c) in covered:
                    c += 1
                cs = int(cell.get(T["number-columns-spanned"], "1"))
                rs = int(cell.get(T["number-rows-spanned"], "1"))
                cells.append({"r": r, "c": c, "rs": rs, "cs": cs, "text": _cell_text(cell)})
                for rr in range(r, r + rs):
                    for cc in range(c, c + cs):
                        covered.add((rr, cc))
                c += cs
    if not cells:
        return None
    return {"type": "table", "cells": cells, "nrow": max(x["r"] + x["rs"] for x in cells),
            "ncol": max(x["c"] + x["cs"] for x in cells)}


def _walk_text(el, out):
    for ch in el:
        if ch.tag in (T["p"], T["h"]):
            t = text_of(ch)
            if t.strip():
                out.append({"type": "p", "text": t})
        elif ch.tag == T["table"]:
            b = _table_block(ch)
            if b:
                out.append(b)
        else:
            _walk_text(ch, out)


def read_odt(path):
    root = _content(path)
    body = root.find(f"{T['body']}/{T['text']}")
    if body is None:
        raise OdfError("문서 본문이 없습니다")
    blocks = []
    _walk_text(body, blocks)
    return {"blocks": blocks, "warnings": []}
