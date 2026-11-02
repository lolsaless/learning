# -*- coding: utf-8 -*-
"""[파일 형식] 글자 파일 읽기: csv·tsv → Workbook / txt·md → 문단·표 블록. 표준 라이브러리만.

글자 인코딩은 UTF-8(BOM 포함) → CP949(한국어 윈도우) → EUC-KR 순서로 시도한다.
txt·md 안의 표: 마크다운 표(| 가 | 나 |)와 탭으로 나뉜 줄이 2줄 이상 이어지면 표로 본다.
"""
import io
import re
import csv

from app.common import numbers as N
from app.formats.xlsx.model import Cell, Sheet, Workbook

ENCODINGS = ("utf-8-sig", "cp949", "euc-kr", "utf-16")


class TextError(Exception):
    pass


def read_text_file(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def read_csv(path):
    txt = read_text_file(path)
    sample = txt[:4096]
    delim = "\t" if path.lower().endswith(".tsv") else None
    if delim is None:
        try:
            delim = csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
        except csv.Error:
            delim = ","
    wb = Workbook()
    name = re.sub(r"\.[^.]+$", "", path.replace("\\", "/").split("/")[-1])[:31] or "자료"
    sh = Sheet(name)
    wb.sheets.append(sh)
    for r, row in enumerate(csv.reader(io.StringIO(txt), delimiter=delim)):
        for c, v in enumerate(row):
            v = v.strip()
            if not v:
                continue
            tok = N.parse_cell(v)
            cell = Cell(tok["value"], "n", v) if tok and tok.get("value") is not None and not re.search(r"[가-힣A-Za-z]{2,}", v) \
                else Cell(v, "s", v)
            sh.cells[(r, c)] = cell
            sh.maxr = max(sh.maxr, r)
            sh.maxc = max(sh.maxc, c)
    return wb


def _split_md(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [x.strip() for x in s.split("|")]


def _table_from_rows(rows):
    ncol = max(len(r) for r in rows)
    cells = [{"r": r, "c": c, "rs": 1, "cs": 1, "text": v} for r, row in enumerate(rows) for c, v in enumerate(row)]
    return {"type": "table", "cells": cells, "nrow": len(rows), "ncol": ncol}


def text_blocks(txt):
    """글자 → 문단·표 블록(마크다운 표, 탭 표)."""
    lines = txt.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("|") and ln.count("|") >= 2:
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = _split_md(lines[i])
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if len(rows) >= 2:
                blocks.append(_table_from_rows(rows))
            else:
                blocks.extend({"type": "p", "text": " ".join(r)} for r in rows)
            continue
        if "\t" in ln and ln.strip():
            rows = []
            while i < len(lines) and "\t" in lines[i] and lines[i].strip():
                rows.append([x.strip() for x in lines[i].split("\t")])
                i += 1
            if len(rows) >= 2:
                blocks.append(_table_from_rows(rows))
            else:
                blocks.append({"type": "p", "text": " ".join(rows[0])})
            continue
        t = ln.strip()
        if t:
            t = re.sub(r"^#{1,6}\s*", "□ " if t.startswith("#") else "", t)
            t = re.sub(r"^[-*+]\s+", "○ ", t)
            t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
            blocks.append({"type": "p", "text": t})
        i += 1
    return blocks


def read_txt(path):
    return {"blocks": text_blocks(read_text_file(path)), "warnings": []}
