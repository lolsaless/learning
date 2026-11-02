"""문서 모양 재현 — Document.layout(배치 트리)을 HTML 로 그리고, 바뀐 곳(mark)을 표시한다.

재현하는 것: 용지 너비·여백, 문단 정렬·왼쪽/오른쪽 여백·들여쓰기/내어쓰기·문단 위아래 간격·줄간격,
            글꼴·크기·글자색·굵게·기울임·밑줄·취소선·음영·자간, 표(열·행 합침, 칸 너비·높이, 테두리, 배경색),
            머리말·꼬리말·각주·글상자(이름표를 붙여 제자리에), 쪽 구분(추정)
재현하지 않는 것: 그림 자체, 글자 겹침·장평, 다단, 쪽 단위 배치(긴 문서는 한 장으로 이어서 그림)

단위: HWPUNIT(1/7200 인치) → 화면 px = HWPUNIT / 75
글꼴이 컴퓨터에 없으면 비슷한 글꼴(바탕 계열 → serif, 그 밖 → sans-serif)로 대신 보인다.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

from ..hwpx.model import Block, Document
from .marks import Mark

PX = 75.0
DEFAULT_PAGE = {"width": 59528, "height": 84188, "left": 5669, "right": 5669, "top": 4251, "bottom": 4251}
ALIGN = {"LEFT": "left", "RIGHT": "right", "CENTER": "center", "JUSTIFY": "justify",
         "DISTRIBUTE": "justify", "DISTRIBUTE_SPACE": "justify"}
VALIGN = {"TOP": "top", "CENTER": "middle", "BOTTOM": "bottom"}
BORDER = {"SOLID": "solid", "DASH": "dashed", "LONG_DASH": "dashed", "DASH_DOT": "dashed",
          "DASH_DOT_DOT": "dashed", "DOT": "dotted", "CIRCLE": "dotted", "DOUBLE_SLIM": "double",
          "SLIM_THICK": "double", "THICK_SLIM": "double", "SLIM_THICK_SLIM": "double"}
SERIF_HINTS = ("바탕", "명조", "Batang", "Myeongjo", "궁서", "Times", "Serif")
# 글꼴 이름에 굵기가 들어 있는 경우 (예: '경기천년제목 Bold') — 그 글꼴이 없는 컴퓨터에서도 굵기는 살린다
WEIGHT_HINTS = (("ExtraBold", 800), ("Heavy", 800), ("Black", 800), ("Bold", 700), ("굵은", 700),
                ("SemiBold", 600), ("Medium", 500), ("Light", 300), ("Thin", 200))
# 자간: 한글 글꼴보다 브라우저 대체 글꼴이 넓어서, 좁은 자간을 그대로 쓰면 글자가 겹친다 → 하한을 둔다
MIN_LETTER_SPACING_EM = -0.04


def px(v: float) -> float:
    return round((v or 0) / PX, 1)


def _e(s: str) -> str:
    return html.escape(s, quote=False)


def _a(s: str) -> str:
    return html.escape(str(s), quote=True)


class DocRenderer:
    """side: 'a' | 'b' — 표시할 문서가 비교의 어느 쪽인지. inline_ghost: 지운 글자를 끼워 보여 줄지(merged)."""

    def __init__(self, doc: Document, marks: Optional[Dict[int, Mark]] = None,
                 ghosts: Optional[Dict[int, List[Dict[str, Any]]]] = None,
                 tail: Optional[List[Dict[str, Any]]] = None, side: str = "b", inline_ghost: bool = False):
        self.doc = doc
        self.marks = marks or {}
        self.ghosts = ghosts or {}
        self.tail = tail or []
        self.side = side
        self.inline_ghost = inline_ghost
        self.order: List[int] = []           # 화면에 나온 변경 번호 순서 (이동 버튼용)
        self._char_css: Dict[str, str] = {}
        self._para_css: Dict[str, str] = {}

    # ── 전체 ───────────────────────────────────────
    def render(self) -> str:
        ps = {**DEFAULT_PAGE, **(self.doc.page_setup or {})}
        body_w = ps["width"] - ps["left"] - ps["right"]
        out = [f'<div class="dv-sheet" style="width:{px(body_w)}px;'
               f'padding:{px(ps["top"])}px {px(ps["right"])}px {px(ps["bottom"])}px {px(ps["left"])}px">']
        page = None
        for node in self.doc.layout:
            pg = node.get("pg")
            if page is not None and pg and pg != page:
                out.append(f'<div class="dv-pb"><span>약 {pg}쪽 (추정)</span></div>')
            page = pg or page
            out.append(self._node(node))
        for g in self.tail:
            out.append(self._ghost(g))
        out.append("</div>")
        return "".join(out)

    def _node(self, n: Dict[str, Any]) -> str:
        t = n.get("t")
        if t == "p":
            return self._para(n)
        if t == "tbl":
            return self._table(n)
        if t == "sub":
            inner = "".join(self._para(p) for p in n["paras"])
            return (f'<div class="dv-sub dv-sub-{_a(n["kind"])}"><span class="dv-sublabel">{_e(n["label"])}</span>'
                    f'{inner}</div>')
        return ""

    # ── 표시 공통 ───────────────────────────────────
    def _open(self, base: str, bi: Optional[int]) -> str:
        """요소 여는 속성: class(표시 포함) + 변경 번호·설명. 예) class="dv-p dv-m dv-modified" data-cid="3" ..."""
        m = self.marks.get(bi) if bi is not None else None
        bi_attr = f' data-bi="{bi}"' if bi is not None else ""      # (v2.0) 고치기·위치 찾기용 블록 순번
        if not m:
            return f'class="{base}"{bi_attr}'
        if m["cid"] not in self.order:
            self.order.append(m["cid"])
        tip = f'#{m["cid"]} {m["label"]}: {m["summary"]}'
        return (f'class="{base} dv-m dv-{m["type"]}" data-cid="{m["cid"]}" data-type="{m["type"]}" '
                f'title="{_a(tip)}"{bi_attr}')

    def _ghosts_before(self, bi: Optional[int]) -> str:
        if bi is None:
            return ""
        return "".join(self._ghost(g) for g in self.ghosts.get(bi, []))

    def _ghost(self, g: Dict[str, Any]) -> str:
        if g["cid"] not in self.order:
            self.order.append(g["cid"])
        text = _e(g["text"]).replace("\n", "<br>")
        if g.get("kind") == "added":            # (v2.0) 병합 화면: 끼워 넣을 예정인 글
            label = g.get("label", "추가 예정")
            return (f'<div class="dv-ghost dv-ghost-add" data-cid="{g["cid"]}" data-type="added" '
                    f'title="{_a("#" + str(g["cid"]) + " " + label + ": " + g["location"])}">'
                    f'<span class="dv-badge">{_e(label)} · {_e(g["location"])}</span><span>{text}</span></div>')
        return (f'<div class="dv-ghost" data-cid="{g["cid"]}" data-type="deleted" '
                f'title="{_a("#" + str(g["cid"]) + " 삭제: " + g["location"])}">'
                f'<span class="dv-badge">삭제 · {_e(g["location"])}</span><del>{text}</del></div>')

    # ── 문단 ───────────────────────────────────────
    def _para(self, n: Dict[str, Any]) -> str:
        bi = n.get("b")
        content = self._block_html(bi) if bi is not None else " "
        attr = self._open("dv-p" + ("" if bi is not None else " dv-empty"), bi)
        items = "".join(self._node(c) for c in n.get("items", []))
        return f'{self._ghosts_before(bi)}<p {attr} style="{self._pcss(n.get("ps", ""))}">{content}</p>{items}'

    def _pcss(self, ps_id: str) -> str:
        if ps_id in self._para_css:
            return self._para_css[ps_id]
        p = self.doc.para_styles.get(ps_id, {})
        css = [f"text-align:{ALIGN.get(p.get('align', 'JUSTIFY'), 'justify')}"]
        left, indent = p.get("left", 0), p.get("indent", 0)
        if indent < 0:      # 내어쓰기: 첫 줄은 왼쪽, 다음 줄부터 들여씀
            css += [f"padding-left:{px(left - indent)}px", f"text-indent:{px(indent)}px"]
        else:
            css += [f"padding-left:{px(left)}px", f"text-indent:{px(indent)}px"]
        if p.get("right"):
            css.append(f"padding-right:{px(p['right'])}px")
        if p.get("prev"):
            css.append(f"margin-top:{px(p['prev'])}px")
        if p.get("next"):
            css.append(f"margin-bottom:{px(p['next'])}px")
        if p.get("line_type", "PERCENT") == "PERCENT":
            css.append(f"line-height:{max(1.0, p.get('line', 160) / 100):.2f}")
        elif p.get("line"):
            css.append(f"line-height:{max(12, px(p['line']))}px")
        self._para_css[ps_id] = ";".join(css)
        return self._para_css[ps_id]

    # ── 글자 ───────────────────────────────────────
    def _ccss(self, key: str) -> str:
        if key in self._char_css:
            return self._char_css[key]
        p = self.doc.styles.get(key, {})
        font = (p.get("font") or "").replace('"', "").replace("'", "")
        generic = "serif" if any(h in font for h in SERIF_HINTS) else "sans-serif"
        css = [f"font-family:'{font}',{generic}" if font else f"font-family:{generic}"]
        if p.get("size"):
            css.append(f"font-size:{p['size']}pt")
        if p.get("color") and p["color"] != "#000000":
            css.append(f"color:{p['color']}")
        weight = next((w for hint, w in WEIGHT_HINTS if hint in font), 0)
        if p.get("bold"):
            weight = max(weight, 700)
        if weight:
            css.append(f"font-weight:{weight}")
        if p.get("italic"):
            css.append("font-style:italic")
        deco = [d for d, on in (("underline", p.get("underline", "NONE") != "NONE"),
                                ("line-through", p.get("strike", "NONE") != "NONE")) if on]
        if deco:
            css.append("text-decoration:" + " ".join(deco))
        if p.get("shade") and p["shade"] not in ("NONE", "#FFFFFF"):
            css.append(f"background:{p['shade']}")
        if p.get("spacing"):
            css.append(f"letter-spacing:{max(MIN_LETTER_SPACING_EM, p['spacing'] / 100):.2f}em")
        self._char_css[key] = ";".join(css)
        return self._char_css[key]

    def _spans(self, text: str, styles: List[str], cls: str = "", fmt: Optional[List[bool]] = None) -> str:
        """같은 서식 글자끼리 묶어 <span>. cls: dv-ins/dv-del 등 덧붙일 표시."""
        out, i = [], 0
        while i < len(text):
            j = i + 1
            while j < len(text) and styles[j] == styles[i] and (fmt is None or fmt[j] == fmt[i]):
                j += 1
            c = " ".join(x for x in (cls, "dv-fmtc" if fmt and fmt[i] else "") if x)
            ca = f' class="{c}"' if c else ""
            out.append(f'<span{ca} style="{self._ccss(styles[i])}">{_e(text[i:j])}</span>')
            i = j
        return "".join(out)

    def _block_html(self, bi: int) -> str:
        blk: Block = self.doc.blocks[bi]
        text, styles = blk.text, blk.char_styles()
        m = self.marks.get(bi)
        fmt = [False] * len(text)
        for s, e in (m or {}).get("fmt", []):
            for k in range(max(0, s), min(len(text), e)):
                fmt[k] = True
        segs = (m or {}).get("segs")
        if segs and self._consumed(segs) == len(text):
            out, pos = [], 0
            for seg in segs:
                op = seg["op"]
                if op == "equal":
                    t = seg["text"] if self.side == "b" else seg.get("a", seg["text"])
                    out.append(self._spans(text[pos:pos + len(t)], styles[pos:pos + len(t)], "", fmt[pos:pos + len(t)]))
                    pos += len(t)
                elif (op == "insert" and self.side == "b") or (op == "delete" and self.side == "a"):
                    n = len(seg["text"])
                    out.append(self._spans(text[pos:pos + n], styles[pos:pos + n],
                                           "dv-ins" if op == "insert" else "dv-del"))
                    pos += n
                elif self.inline_ghost and op == "delete":
                    near = styles[min(pos, len(styles) - 1)] if styles else ""
                    out.append(f'<del class="dv-gdel" style="{self._ccss(near)}">{_e(seg["text"])}</del>')
            return "".join(out)
        whole = {"added": "dv-ins", "deleted": "dv-del"}.get((m or {}).get("type"), "")
        return self._spans(text, styles, whole, fmt) if text else " "

    def _consumed(self, segs) -> int:
        n = 0
        for s in segs:
            if s["op"] == "equal":
                n += len(s["text"] if self.side == "b" else s.get("a", s["text"]))
            elif (s["op"] == "insert" and self.side == "b") or (s["op"] == "delete" and self.side == "a"):
                n += len(s["text"])
        return n

    # ── 표 ─────────────────────────────────────────
    def _border(self, spec) -> str:
        if not spec or spec[0] == "NONE":
            return "none"
        kind, width, color = spec
        style = BORDER.get(kind, "solid")
        w = max(1, round(width * 3.78)) if style != "double" else max(3, round(width * 3.78))
        return f"{w}px {style} {color}"

    def _table(self, n: Dict[str, Any]) -> str:
        align = {"CENTER": "margin:6px auto", "RIGHT": "margin:6px 0 6px auto"}.get(n.get("align"), "margin:6px 0")
        rows = []
        for row in n["rows"]:
            cells = []
            for c in row:
                bf = self.doc.border_fills.get(c.get("bf", ""), {})
                css = [f"width:{px(c['w'])}px", f"height:{px(c['h'])}px",
                       f"vertical-align:{VALIGN.get(c.get('va'), 'middle')}"]
                for side in ("left", "right", "top", "bottom"):
                    css.append(f"border-{side}:{self._border(bf.get(side))}")
                if bf.get("fill"):
                    css.append(f"background:{bf['fill']}")
                bi = c.get("b")
                span = (f' colspan="{c["cs"]}"' if c.get("cs", 1) > 1 else "") + \
                       (f' rowspan="{c["rs"]}"' if c.get("rs", 1) > 1 else "")
                content = self._block_html(bi) if bi is not None else " "
                inner = (f'{self._ghosts_before(bi)}<div class="dv-p" style="{self._pcss(c.get("ps", ""))}">'
                         f'{content}</div>' + "".join(self._node(x) for x in c.get("items", [])))
                cells.append(f'<td {self._open("dv-td", bi)}{span} style="{";".join(css)}">{inner}</td>')
            rows.append("<tr>" + "".join(cells) + "</tr>")
        return (f'<table class="dv-tbl" data-table="{n.get("no", "")}" style="width:{px(n.get("w", 0))}px;{align}">'
                f'{"".join(rows)}</table>')
