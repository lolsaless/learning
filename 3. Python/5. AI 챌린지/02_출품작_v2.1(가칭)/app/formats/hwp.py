# -*- coding: utf-8 -*-
"""[파일 형식] 구형 한글(hwp, HWP 5.0 바이너리) 읽기 — 본문 문단과 표(칸 합치기 포함). 표준 라이브러리만.

    read_hwp(경로) → {"blocks": [{"type": "p", "text"} | {"type": "table", "cells": [...], "nrow", "ncol"}],
                      "warnings": [...]}

구조(공개된 HWP 5.0 문서 형식 기준)
  OLE 묶음 → FileHeader(압축·암호·배포용 표시) → BodyText/Section0..N(압축된 레코드 줄)
  레코드 = 머리 4바이트(태그 10비트·깊이 10비트·크기 12비트) + 내용. 깊이(level)로 부모·자식을 안다.
  문단 = PARA_HEADER(66) 아래 PARA_TEXT(67, UTF-16).  표 = CTRL_HEADER(71, 'tbl ') 아래
  TABLE(77, 행·열 수) + 칸마다 LIST_HEADER(72, 열·행 주소·합치기) 와 그 칸의 문단들.
읽기 전용이다. hwp 를 고치거나 저장하지 않는다(편집은 hwpx 에서).
"""
import zlib
import struct

from app.formats.ole import OleFile, OleError

TAG_PARA_HEADER, TAG_PARA_TEXT, TAG_CTRL_HEADER, TAG_LIST_HEADER, TAG_TABLE = 66, 67, 71, 72, 77
EXTENDED = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}       # 8글자 길이 확장 제어 문자
INLINE = {4, 5, 6, 7, 8, 9, 19, 20}                                # 8글자 길이 인라인 제어 문자
SKIP_CTRLS = {b"head", b"foot", b"pghd", b"pgnp", b"nwno", b"atno", b"secd", b"cold", b"%tdt", b"bokm", b"%hlk"}


class HwpError(Exception):
    pass


def _records(data):
    out, i, n = [], 0, len(data)
    while i + 4 <= n:
        h = struct.unpack_from("<I", data, i)[0]
        tag, level, size = h & 0x3FF, (h >> 10) & 0x3FF, (h >> 20) & 0xFFF
        i += 4
        if size == 0xFFF:
            if i + 4 > n:
                break
            size = struct.unpack_from("<I", data, i)[0]
            i += 4
        out.append((tag, level, data[i:i + size]))
        i += size
    return out


def para_text(payload):
    """PARA_TEXT 내용(UTF-16LE)을 글자로. 제어 문자는 건너뛰고 탭·줄바꿈만 남긴다."""
    n = len(payload) // 2
    units = struct.unpack_from(f"<{n}H", payload, 0)
    out, i = [], 0
    while i < n:
        u = units[i]
        if u < 32:
            if u in EXTENDED or u in INLINE:
                if u == 9:
                    out.append("\t")
                i += 8
                continue
            if u == 10:
                out.append("\n")
            elif u == 13:
                break
            elif u in (24, 30, 31):
                out.append("-" if u == 24 else " ")
            i += 1
            continue
        out.append(chr(u))
        i += 1
    return "".join(out)


def _tree(recs):
    """레코드 줄을 깊이에 따라 나무로: [ {tag, payload, kids:[…]} ]"""
    root = {"tag": -1, "level": -1, "payload": b"", "kids": []}
    stack = [root]
    for tag, level, payload in recs:
        node = {"tag": tag, "level": level, "payload": payload, "kids": []}
        while stack and stack[-1]["level"] >= level:
            stack.pop()
        (stack[-1] if stack else root)["kids"].append(node)
        stack.append(node)
    return root["kids"]


class _Builder:
    def __init__(self):
        self.blocks = []
        self.warnings = []
        self.last_caption = ""

    def paragraph(self, node, out_blocks, depth=0):
        """문단 하나: 글자 → 문단 블록, 안의 표 컨트롤 → 표 블록."""
        text = ""
        tables = []
        for k in node["kids"]:
            if k["tag"] == TAG_PARA_TEXT:
                text += para_text(k["payload"])
            elif k["tag"] == TAG_CTRL_HEADER and len(k["payload"]) >= 4:
                cid = k["payload"][:4][::-1]
                if cid == b"tbl ":
                    tables.append(k)
                elif cid not in SKIP_CTRLS:
                    # 글상자·각주 등: 안의 문단 글자만 본문으로 이어 붙인다
                    for kk in k["kids"]:
                        if kk["tag"] == TAG_PARA_HEADER and depth < 4:
                            self.paragraph(kk, out_blocks, depth + 1)
        if text.strip():
            out_blocks.append({"type": "p", "text": text.strip("\n")})
        for t in tables:
            tb = self.table(t, depth)
            if tb and tb.get("caption"):
                out_blocks.append({"type": "p", "text": tb["caption"]})
            if tb:
                out_blocks.append(tb)

    def cell_text(self, paras, depth):
        parts = []
        for p in paras:
            sub = []
            self.paragraph(p, sub, depth + 1)
            for b in sub:
                if b["type"] == "p":
                    parts.append(b["text"])
                else:
                    self.warnings.append("표 안의 표는 글자만 읽음")
                    parts.extend(c["text"] for c in b["cells"] if c["text"])
        return "\n".join(parts)

    def table(self, ctrl, depth):
        nrow = ncol = 0
        cells = []
        cur = None
        seen_table = False
        captions = []
        for k in ctrl["kids"]:
            if k["tag"] == TAG_TABLE and len(k["payload"]) >= 8:
                nrow, ncol = struct.unpack_from("<HH", k["payload"], 4)
                seen_table = True
            elif k["tag"] == TAG_LIST_HEADER and not seen_table:
                # 표 레코드보다 앞에 오는 목록 = 캡션
                captions.extend(x for x in k["kids"] if x["tag"] == TAG_PARA_HEADER)
                cur = None
            elif k["tag"] == TAG_PARA_HEADER and not seen_table:
                captions.append(k)
            elif k["tag"] == TAG_LIST_HEADER and len(k["payload"]) >= 16:
                col, row, cs, rs = struct.unpack_from("<HHHH", k["payload"], 8)
                cur = {"r": row, "c": col, "rs": max(1, rs), "cs": max(1, cs), "paras": []}
                cells.append(cur)
                cur["paras"].extend(x for x in k["kids"] if x["tag"] == TAG_PARA_HEADER)
            elif k["tag"] == TAG_PARA_HEADER and cur is not None:
                cur["paras"].append(k)
        self.last_caption = self.cell_text(captions, depth) if captions else ""
        if not cells:
            return None
        out = [{"r": c["r"], "c": c["c"], "rs": c["rs"], "cs": c["cs"], "text": self.cell_text(c["paras"], depth)}
               for c in cells]
        if nrow and ncol:      # 주소가 표 크기를 넘는 칸(손상)은 버린다
            out = [c for c in out if c["r"] < nrow and c["c"] < ncol]
            for c in out:
                c["rs"] = min(c["rs"], nrow - c["r"])
                c["cs"] = min(c["cs"], ncol - c["c"])
        if not out:
            return None
        nrow = max(nrow, max(c["r"] + c["rs"] for c in out))
        ncol = max(ncol, max(c["c"] + c["cs"] for c in out))
        return {"type": "table", "cells": out, "nrow": nrow, "ncol": ncol, "caption": self.last_caption}


def read_hwp(path):
    try:
        f = OleFile(path)
    except OleError as e:
        raise HwpError(f"hwp 파일을 열 수 없습니다: {e}")
    if not f.exists("FileHeader"):
        raise HwpError("hwp 머리 정보(FileHeader)가 없습니다")
    fh = f.read("FileHeader")
    if not fh.startswith(b"HWP Document File"):
        raise HwpError("HWP 5.0 문서가 아닙니다(HWP 3.0 등 더 오래된 형식은 한글에서 hwpx 로 저장해 주세요)")
    props = struct.unpack_from("<I", fh, 36)[0]
    compressed, password, distribute = props & 1, props & 2, props & 4
    if password:
        raise HwpError("암호가 걸린 hwp 입니다. 한글에서 암호를 풀고 다시 저장해 주세요")
    if distribute:
        raise HwpError("배포용(읽기 전용) hwp 입니다. 본문이 암호화되어 읽을 수 없습니다")
    secs = sorted((s for s in f.streams() if s.startswith("BodyText/Section")),
                  key=lambda s: int("".join(ch for ch in s if ch.isdigit()) or 0))
    if not secs:
        raise HwpError("본문(BodyText)이 없습니다")
    b = _Builder()
    for s in secs:
        raw = f.read(s)
        if compressed:
            try:
                raw = zlib.decompress(raw, -15)
            except zlib.error as e:
                b.warnings.append(f"{s} 압축 풀기 실패: {e}")
                continue
        for node in _tree(_records(raw)):
            if node["tag"] == TAG_PARA_HEADER:
                b.paragraph(node, b.blocks)
    return {"blocks": b.blocks, "warnings": sorted(set(b.warnings))}
