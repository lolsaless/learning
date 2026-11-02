"""본문 XML(section*.xml) → Block 목록.

본문 구조 요약 (hp = paragraph 네임스페이스)
    hs:sec
     └ hp:p (문단)
         └ hp:run charPrIDRef="글자모양 번호"
             ├ hp:t          글자 (자식으로 hp:tab, hp:lineBreak, hp:fwSpace 등이 섞임)
             ├ hp:tbl        표 → hp:tr → hp:tc(hp:cellAddr, hp:subList → hp:p ...)
             ├ hp:pic 등     그림·도형 (글상자는 hp:drawText → hp:subList)
             └ hp:ctrl       머리말·꼬리말·각주·미주 (→ hp:subList)

새 개체 종류(예: 차트 안 글자)를 읽게 하려면 SHAPES / CTRL_SUB / _collect() 를 고친다.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from typing import Dict, List, Optional, Tuple

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


def _child(el: ET.Element, name: str) -> Optional[ET.Element]:
    for c in el:
        if local(c.tag) == name:
            return c
    return None


def _children(el: ET.Element, name: str) -> List[ET.Element]:
    return [c for c in el if local(c.tag) == name]


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
        self.stats: Counter = Counter()
        self.table_no = 0
        self.para_no = 0
        self.page = 1
        self.last_vpos = -1
        self.context = ""

    # ── 진입점 ──────────────────────────────────────
    def parse_section(self, root: ET.Element, sidx: int) -> None:
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
            try:
                v = int(seg.get("vertpos", "0"))
            except ValueError:
                continue
            if self.last_vpos >= 0 and v < self.last_vpos:
                self.page += 1
            if first_page is None:
                first_page = self.page
            self.last_vpos = v
        return first_page or self.page

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

    def _add(self, **kw) -> None:
        runs: List[Run] = kw.pop("runs")
        text = "".join(r.text for r in runs)
        self.stats["chars"] += len(text)
        self.blocks.append(Block(index=len(self.blocks), text=text, runs=runs, **kw))

    # ── 본문 문단 ───────────────────────────────────
    def _top_paragraph(self, p: ET.Element, path: str) -> None:
        page = self._advance_page(p)
        runs, pending = self._collect(p)
        text = "".join(r.text for r in runs).strip()
        if text:
            self.para_no += 1
            self.stats["paragraphs"] += 1
            if text.startswith(config.HEADING_MARKERS) and len(text) <= config.HEADING_MAX_LEN:
                self.context = text
            self._add(kind="para", path=path, location=f"본문 {self.para_no}번째 문단",
                      context=self.context, page=page, runs=runs)
        for kind, label, el in pending:
            self._pending(kind, label, el, path, "", page)

    def _pending(self, kind: str, label: str, el: ET.Element, path: str, parent: str, page: int) -> None:
        if kind == "table":
            self._table(el, path, parent, page)
        else:
            loc = f"{parent} › {label}" if parent else label
            self._sub_paragraphs(el, kind, loc, f"{path}/{kind}", page)

    def _sub_paragraphs(self, sub: ET.Element, kind: str, loc: str, path: str, page: int) -> None:
        for k, p in enumerate(_children(sub, "p")):
            runs, pending = self._collect(p)
            if "".join(r.text for r in runs).strip():
                self._add(kind=kind, path=f"{path}/p{k}", location=loc, context=self.context,
                          page=page, runs=runs)
            for pk, label, el in pending:
                self._pending(pk, label, el, f"{path}/p{k}", loc, page)

    # ── 표 ─────────────────────────────────────────
    def _table(self, tbl: ET.Element, path: str, parent: str, page: int) -> None:
        self.table_no += 1
        tno = self.table_no
        self.stats["tables"] += 1
        for tr in _children(tbl, "tr"):
            for tc in _children(tr, "tc"):
                addr = _child(tc, "cellAddr")
                row = int(addr.get("rowAddr", "0")) + 1 if addr is not None else 0
                col = int(addr.get("colAddr", "0")) + 1 if addr is not None else 0
                self.stats["cells"] += 1
                loc = f"표 {tno} · {row}행 {col}열"
                if parent:
                    loc = f"{parent} › {loc}"
                cpath = f"{path}/t{tno}/r{row}c{col}"
                runs: List[Run] = []
                pending: List[Pending] = []
                sub = _child(tc, "subList")
                for p in (_children(sub, "p") if sub is not None else []):
                    r, pd = self._collect(p)
                    if r and runs:                      # 셀 안 문단 사이는 줄바꿈
                        runs.append(Run("\n", runs[-1].style))
                    runs.extend(r)
                    pending.extend(pd)
                if "".join(r.text for r in runs).strip():
                    self._add(kind="cell", path=cpath, location=loc, context=self.context,
                              page=page, runs=runs, table=tno, row=row, col=col)
                for pk, label, el in pending:
                    self._pending(pk, label, el, cpath, loc, page)
