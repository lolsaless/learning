# -*- coding: utf-8 -*-
"""[파일 형식] 워드(docx) 읽기 → 문단·표 블록(칸 합치기 gridSpan·vMerge 포함). 표준 라이브러리만."""
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocxError(Exception):
    pass


def _ptext(p):
    out = []
    for el in p.iter():
        if el.tag == W + "t":
            out.append(el.text or "")
        elif el.tag == W + "tab":
            out.append("\t")
        elif el.tag in (W + "br", W + "cr"):
            out.append("\n")
    return "".join(out)


def _cell_text(tc):
    return "\n".join(_ptext(p) for p in tc.iter(W + "p"))


def _table(tbl):
    cells = []
    vopen = {}          # 열 → 위로 합쳐지는 칸
    for r, tr in enumerate(tbl.findall(W + "tr")):
        c = 0
        for tc in tr.findall(W + "tc"):
            pr = tc.find(W + "tcPr")
            cs, vm = 1, None
            if pr is not None:
                gs = pr.find(W + "gridSpan")
                if gs is not None:
                    cs = int(gs.get(W + "val", "1"))
                v = pr.find(W + "vMerge")
                if v is not None:
                    vm = v.get(W + "val", "continue")
            if vm == "continue" and c in vopen:
                vopen[c]["rs"] += 1
            else:
                cell = {"r": r, "c": c, "rs": 1, "cs": cs, "text": _cell_text(tc)}
                cells.append(cell)
                if vm == "restart":
                    vopen[c] = cell
                else:
                    vopen.pop(c, None)
            c += cs
    if not cells:
        return None
    return {"type": "table", "cells": cells, "nrow": max(x["r"] + x["rs"] for x in cells),
            "ncol": max(x["c"] + x["cs"] for x in cells)}


def read_docx(path):
    try:
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        raise DocxError(f"docx 파일을 열 수 없습니다: {e}")
    body = root.find(W + "body")
    blocks = []
    for el in body:
        if el.tag == W + "p":
            t = _ptext(el)
            if t.strip():
                blocks.append({"type": "p", "text": t})
        elif el.tag == W + "tbl":
            b = _table(el)
            if b:
                blocks.append(b)
        elif el.tag == W + "sdt":
            for p in el.iter(W + "p"):
                t = _ptext(p)
                if t.strip():
                    blocks.append({"type": "p", "text": t})
    return {"blocks": blocks, "warnings": []}
