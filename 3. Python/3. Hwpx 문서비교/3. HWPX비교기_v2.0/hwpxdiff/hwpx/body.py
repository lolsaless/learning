"""본문 XML(section*.xml) → Block 목록 + 배치 트리(layout).

본문 구조 요약 (hp = paragraph 네임스페이스)
    hs:sec
     └ hp:p (문단, paraPrIDRef = 문단모양)
         └ hp:run charPrIDRef="글자모양 번호"
             ├ hp:t          글자 (자식으로 hp:tab, hp:lineBreak, hp:fwSpace 등이 섞임)
             ├ hp:secPr      구역 설정 (용지 크기·여백: hp:pagePr)
             ├ hp:tbl        표 → hp:tr → hp:tc(hp:cellAddr, hp:cellSpan, hp:cellSz, hp:subList → hp:p ...)
             ├ hp:pic 등     그림·도형 (글상자는 hp:drawText → hp:subList)
             └ hp:ctrl       머리말·꼬리말·각주·미주 (→ hp:subList)

Block 은 비교 단위, layout 은 문서 모양 재현(render/)용. 둘은 같은 순서로 한 번에 만든다.
새 개체 종류(예: 차트 안 글자)를 읽게 하려면 SHAPES / CTRL_SUB / _collect() 를 고친다.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from .. import config
from .model import Block, Run
from .package import local
from .styles import StyleProps, style_key

# hp:t 안의 특수 문자 요소 → 대신 넣을 글자
TEXT_CHILD = {"tab": "\t", "lineBreak": "\n", "fwSpace": " ", "nbSpace": " ", "hyphen": "-"}

# 그림·도형 요소 → 본문에 남길 표시 (추가/삭제를 알아챌 수 있게)
SHAPES = {"pic": "그림", "rect": "사각형", "ellipse": "타원", "line": "선", "arc": "호",
          "polygon": "다각형", "curve": "곡선", "connectLine": "연결선", "container": "묶음 개체",
          "textart": "글맵시", "equation": "수식", "ole": "OLE 개체", "video": "동영상",
          "chart": "차트"}

# hp:ctrl 안에서 글자를 담는 요소 → (Block.kind, 위치 이름)
CTRL_SUB = {"header": ("header", "머리말"), "footer": ("footer", "꼬리말"),
            "footNote": ("note", "각주"), "endNote": ("note", "미주")}

Pending = Tuple[str, str, ET.Element]   # (kind, 위치 이름, 요소)
Node = Dict[str, Any]


def _child(el: ET.Element, name: str) -> Optional[ET.Element]:
    for c in el:
        if local(c.tag) == name:
            return c
    return None


def _children(el: ET.Element, name: str) -> List[ET.Element]:
    return [c for c in el if local(c.tag) == name]


def _int(v, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def text_of(t: ET.Element) -> str:
    parts = [t.text or ""]
    for c in t:
        parts.append(TEXT_CHILD.get(local(c.tag), ""))
        parts.append(c.tail or "")
    return "".join(parts)


class BodyParser:
    def __init__(self, char_styles: Dict[str, StyleProps]):
        self.keymap = {cid: style_key(p) for cid, p in char_styles.items()}
        self.style_table = {style_key(p): p for p in char_styles.values()}
        self.default_key = next(iter(self.keymap.values()), "")
        self.blocks: List[Block] = []
        self.layout: List[Node] = []
        self.page_setup: Dict[str, int] = {}
        self.stats: Counter = Counter()
        self.table_no = 0
        self.para_no = 0
        self.page = 1
        self.last_vpos = -1
        self.context = ""
        self.spans: Dict[int, Tuple[int, int]] = {}   # (v2.0) id(요소) → 바이트 위치
        self.sidx = 0

    def _sp(self, el: ET.Element) -> Optional[List[int]]:
        s = self.spans.get(id(el))
        return [self.sidx, s[0], s[1]] if s else None

    # ── 진입점 ──────────────────────────────────────
    def parse_section(self, root: ET.Element, sidx: int, spans: Optional[Dict[int, Tuple[int, int]]] = None) -> None:
        self.spans = spans or {}
        self.sidx = sidx
        self.stats["sections"] += 1
        if sidx > 0:                       # 새 구역은 새 쪽에서 시작
            self.page += 1
            self.last_vpos = -1
        for i, p in enumerate(_children(root, "p")):
            self._top_paragraph(p, f"s{sidx}/p{i}")

    # ── 쪽 번호 추정 (줄 배치 vertpos 가 줄어들면 새 쪽) ──────────
    def _advance_page(self, p: ET.Element) -> int:
        if p.get("pageBreak") == "1" and self.last_vpos >= 0:
            self.page += 1
            self.last_vpos = -1
        first_page = None
        arr = _child(p, "linesegarray")
        for seg in (arr if arr is not None else []):
            v = _int(seg.get("vertpos"), -1)
            if v < 0:
                continue
            if self.last_vpos >= 0 and v < self.last_vpos:
                self.page += 1
            if first_page is None:
                first_page = self.page
            self.last_vpos = v
        return first_page or self.page

    # ── 용지 설정 (첫 구역의 hp:secPr/hp:pagePr) ─────────────────
    def _page(self, sec: ET.Element) -> None:
        if self.page_setup:
            return
        pp = _child(sec, "pagePr")
        if pp is None:
            return
        m = _child(pp, "margin")
        g = (lambda k, d: _int(m.get(k), d)) if m is not None else (lambda k, d: d)
        self.page_setup = {"width": _int(pp.get("width"), 59528), "height": _int(pp.get("height"), 84188),
                           "left": g("left", 5669), "right": g("right", 5669), "top": g("top", 4251),
                           "bottom": g("bottom", 4251), "header": g("header", 0), "footer": g("footer", 0)}

    # ── 문단 하나의 글자·하위개체 모으기 ─────────────────────
    def _collect(self, p: ET.Element) -> Tuple[List[Run], List[Pending]]:
        runs: List[Run] = []
        pending: List[Pending] = []
        for run in _children(p, "run"):
            key = self.keymap.get(run.get("charPrIDRef", ""), self.default_key)
            for ch in run:
                name = local(ch.tag)
                if name == "t":
                    txt = text_of(ch)
                    if txt:
                        runs.append(Run(txt, key))
                elif name == "secPr":
                    self._page(ch)
                elif name == "tbl":
                    pending.append(("table", "", ch))
                elif name in SHAPES:
                    self.stats["objects"] += 1
                    if name == "equation":
                        script = _child(ch, "script")
                        runs.append(Run(f"[수식: {(script.text or '').strip() if script is not None else ''}]", key))
                    elif name == "pic":
                        runs.append(Run("[그림]", key))
                    for dt in ch.iter():
                        if local(dt.tag) == "drawText":
                            sub = _child(dt, "subList")
                            if sub is not None:
                                pending.append(("shape", "글상자", sub))
                elif name == "ctrl":
                    for c in ch:
                        if local(c.tag) in CTRL_SUB:
                            kind, label = CTRL_SUB[local(c.tag)]
                            sub = _child(c, "subList")
                            if sub is not None:
                                pending.append((kind, label, sub))
        return runs, pending

    def _add(self, **kw) -> int:
        runs: List[Run] = kw.pop("runs")
        text = "".join(r.text for r in runs)
        self.stats["chars"] += len(text)
        self.blocks.append(Block(index=len(self.blocks), text=text, runs=runs, **kw))
        return len(self.blocks) - 1

    # ── 본문 문단 ───────────────────────────────────
    def _top_paragraph(self, p: ET.Element, path: str) -> None:
        page = self._advance_page(p)
        runs, pending = self._collect(p)
        text = "".join(r.text for r in runs).strip()
        node: Node = {"t": "p", "b": None, "ps": p.get("paraPrIDRef", ""), "pg": page, "items": [],
                      "sp": self._sp(p)}
        if text:
            self.para_no += 1
            self.stats["paragraphs"] += 1
            if text.startswith(config.HEADING_MARKERS) and len(text) <= config.HEADING_MAX_LEN:
                self.context = text
            node["b"] = self._add(kind="para", path=path, location=f"본문 {self.para_no}번째 문단",
                                  context=self.context, page=page, runs=runs, span=node["sp"])
        for kind, label, el in pending:
            node["items"].append(self._pending(kind, label, el, path, "", page))
        self.layout.append(node)

    def _pending(self, kind: str, label: str, el: ET.Element, path: str, parent: str, page: int) -> Node:
        if kind == "table":
            return self._table(el, path, parent, page)
        loc = f"{parent} › {label}" if parent else label
        return self._sub_paragraphs(el, kind, label, loc, f"{path}/{kind}", page)

    def _sub_paragraphs(self, sub: ET.Element, kind: str, label: str, loc: str, path: str, page: int) -> Node:
        node: Node = {"t": "sub", "kind": kind, "label": label, "paras": []}
        for k, p in enumerate(_children(sub, "p")):
            runs, pending = self._collect(p)
            pn: Node = {"t": "p", "b": None, "ps": p.get("paraPrIDRef", ""), "pg": page, "items": [],
                        "sp": self._sp(p)}
            if "".join(r.text for r in runs).strip():
                pn["b"] = self._add(kind=kind, path=f"{path}/p{k}", location=loc, context=self.context,
                                    page=page, runs=runs, span=pn["sp"])
            for pk, plabel, el in pending:
                pn["items"].append(self._pending(pk, plabel, el, f"{path}/p{k}", loc, page))
            node["paras"].append(pn)
        return node

    # ── 표 ─────────────────────────────────────────
    def _table(self, tbl: ET.Element, path: str, parent: str, page: int) -> Node:
        self.table_no += 1
        tno = self.table_no
        self.stats["tables"] += 1
        sz, pos = _child(tbl, "sz"), _child(tbl, "pos")
        node: Node = {"t": "tbl", "no": tno, "w": _int(sz.get("width")) if sz is not None else 0,
                      "align": pos.get("horzAlign", "LEFT") if pos is not None else "LEFT",
                      "bf": tbl.get("borderFillIDRef", ""), "rows": []}
        for tr in _children(tbl, "tr"):
            row_nodes: List[Node] = []
            for tc in _children(tr, "tc"):
                addr, span, csz = _child(tc, "cellAddr"), _child(tc, "cellSpan"), _child(tc, "cellSz")
                row = _int(addr.get("rowAddr")) + 1 if addr is not None else 0
                col = _int(addr.get("colAddr")) + 1 if addr is not None else 0
                self.stats["cells"] += 1
                loc = f"표 {tno} · {row}행 {col}열"
                if parent:
                    loc = f"{parent} › {loc}"
                cpath = f"{path}/t{tno}/r{row}c{col}"
                sub = _child(tc, "subList")
                paras = _children(sub, "p") if sub is not None else []
                cell: Node = {"b": None, "cs": _int(span.get("colSpan"), 1) if span is not None else 1,
                              "rs": _int(span.get("rowSpan"), 1) if span is not None else 1,
                              "w": _int(csz.get("width")) if csz is not None else 0,
                              "h": _int(csz.get("height")) if csz is not None else 0,
                              "bf": tc.get("borderFillIDRef", ""),
                              "ps": paras[0].get("paraPrIDRef", "") if paras else "",
                              "va": sub.get("vertAlign", "CENTER") if sub is not None else "CENTER",
                              "items": [], "r": row, "c": col, "sp": None}
                if paras and self.spans:
                    a, b = self._sp(paras[0]), self._sp(paras[-1])
                    if a and b:
                        cell["sp"] = [self.sidx, a[1], b[2]]
                runs: List[Run] = []
                pending: List[Pending] = []
                for p in paras:
                    r, pd = self._collect(p)
                    if r and runs:                      # 셀 안 문단 사이는 줄바꿈
                        runs.append(Run("\n", runs[-1].style))
                    runs.extend(r)
                    pending.extend(pd)
                if "".join(r.text for r in runs).strip():
                    cell["b"] = self._add(kind="cell", path=cpath, location=loc, context=self.context,
                                          page=page, runs=runs, table=tno, row=row, col=col, span=cell["sp"])
                for pk, label, el in pending:
                    cell["items"].append(self._pending(pk, label, el, cpath, loc, page))
                row_nodes.append(cell)
            node["rows"].append(row_nodes)
        return node
