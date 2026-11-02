"""글자모양(charPr) 해석 — header.xml 의 번호(charPrIDRef)를 실제 속성으로 바꾼다.

왜 필요한가: 파일마다 charPr 번호가 다르다(수정하면 새 번호가 생김).
번호끼리 비교하면 안 되고, 번호가 가리키는 '글꼴·크기·색·굵게…'로 비교해야 한다.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, Tuple

from .. import config
from .package import local

StyleProps = Dict[str, Any]


def parse_char_styles(header: ET.Element) -> Dict[str, StyleProps]:
    """header.xml → {charPr id(str): 속성 dict}."""
    fonts: Dict[str, str] = {}
    for face in header.iter():
        if local(face.tag) == "fontface" and face.get("lang") == "HANGUL":
            for f in face:
                if local(f.tag) == "font":
                    fonts[f.get("id", "")] = f.get("face", "")
            break

    out: Dict[str, StyleProps] = {}
    for cp in header.iter():
        if local(cp.tag) != "charPr":
            continue
        props: StyleProps = {
            "font": "", "size": round(int(cp.get("height", "1000") or 1000) / 100, 1),
            "color": (cp.get("textColor") or "#000000").upper(),
            "shade": (cp.get("shadeColor") or "none").upper(),
            "bold": False, "italic": False, "underline": "NONE", "strike": "NONE",
            "ratio": 100, "spacing": 0,
        }
        for ch in cp:
            name = local(ch.tag)
            if name == "fontRef":
                props["font"] = fonts.get(ch.get("hangul", ""), ch.get("hangul", ""))
            elif name == "bold":
                props["bold"] = True
            elif name == "italic":
                props["italic"] = True
            elif name == "underline":
                props["underline"] = ch.get("type", "NONE")
            elif name == "strikeout":
                shape = ch.get("shape", "NONE")
                props["strike"] = "NONE" if shape in ("NONE", "3D") else shape
            elif name == "ratio":
                props["ratio"] = int(ch.get("hangul", "100") or 100)
            elif name == "spacing":
                props["spacing"] = int(ch.get("hangul", "0") or 0)
        out[cp.get("id", "")] = props
    return out


def style_key(props: StyleProps) -> str:
    """속성 dict → 비교용 문자열 키 (파일이 달라도 같은 서식이면 같은 키)."""
    return "|".join(f"{k}={props.get(k)}" for k in config.STYLE_LABELS)


def color_label(c: str) -> str:
    c = (c or "").upper()
    if c in ("NONE", ""):
        return "없음"
    name = config.COLOR_NAMES.get(c)
    return f"{name}({c})" if name else c


def _fmt(attr: str, v: Any) -> str:
    if attr in ("color", "shade"):
        return color_label(v)
    if isinstance(v, bool):
        return "예" if v else "아니오"
    if attr in ("underline", "strike"):
        return "없음" if v == "NONE" else str(v)
    return str(v)


def describe_delta(a: StyleProps, b: StyleProps) -> Tuple[str, ...]:
    """두 서식의 차이를 사람이 읽는 문장으로. 예) ('글자색: 검정(#000000) → 빨강(#FF0000)',)."""
    out = []
    for attr, label in config.STYLE_LABELS.items():
        if a.get(attr) != b.get(attr):
            out.append(f"{label}: {_fmt(attr, a.get(attr))} → {_fmt(attr, b.get(attr))}")
    return tuple(out)


def describe(props: StyleProps) -> str:
    """서식 한 줄 요약. 예) '경기천년바탕 12pt 빨강(#FF0000) 굵게'."""
    parts = [props.get("font", ""), f"{props.get('size')}pt", color_label(props.get("color", ""))]
    if props.get("bold"):
        parts.append("굵게")
    if props.get("italic"):
        parts.append("기울임")
    if props.get("underline", "NONE") != "NONE":
        parts.append("밑줄")
    if props.get("strike", "NONE") != "NONE":
        parts.append("취소선")
    return " ".join(p for p in parts if p)


# ════════════════════════════════════════════════════════════════
# v1.1 문서 모양 재현용: 문단모양(paraPr)·테두리/배경(borderFill)·용지(pagePr)
# 단위: HWPUNIT (1/7200 인치). 화면 px = HWPUNIT / 75
# ════════════════════════════════════════════════════════════════
def _margin_parts(pp: ET.Element):
    """paraPr 안의 margin·lineSpacing. hp:switch 가 있으면 hp:case(새 단위)를 우선 쓴다
    (hp:default 는 옛 프로그램용으로 여백 값이 2배로 적혀 있음)."""
    margin = spacing = None
    for ch in pp:
        name = local(ch.tag)
        if name == "switch":
            branch = next((c for c in ch if local(c.tag) == "case"), None)
            if branch is None:
                branch = next((c for c in ch if local(c.tag) == "default"), None)
            if branch is not None:
                for c in branch:
                    if local(c.tag) == "margin":
                        margin = c
                    elif local(c.tag) == "lineSpacing":
                        spacing = c
        elif name == "margin" and margin is None:
            margin = ch
        elif name == "lineSpacing" and spacing is None:
            spacing = ch
    return margin, spacing


def _int(v, default=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def parse_para_styles(header: ET.Element) -> Dict[str, StyleProps]:
    """header.xml → {paraPr id: {align, left, right, indent, prev, next, line_type, line}}."""
    out: Dict[str, StyleProps] = {}
    for pp in header.iter():
        if local(pp.tag) != "paraPr":
            continue
        props: StyleProps = {"align": "JUSTIFY", "left": 0, "right": 0, "indent": 0,
                             "prev": 0, "next": 0, "line_type": "PERCENT", "line": 160}
        for ch in pp:
            if local(ch.tag) == "align":
                props["align"] = ch.get("horizontal", "JUSTIFY")
        margin, spacing = _margin_parts(pp)
        if margin is not None:
            for c in margin:
                key = {"intent": "indent", "left": "left", "right": "right",
                       "prev": "prev", "next": "next"}.get(local(c.tag))
                if key:
                    props[key] = _int(c.get("value"))
        if spacing is not None:
            props["line_type"] = spacing.get("type", "PERCENT")
            props["line"] = _int(spacing.get("value"), 160)
        out[pp.get("id", "")] = props
    return out


def parse_border_fills(header: ET.Element) -> Dict[str, StyleProps]:
    """header.xml → {borderFill id: {left/right/top/bottom: (종류, 굵기mm, 색), fill: 배경색|None}}."""
    out: Dict[str, StyleProps] = {}
    for bf in header.iter():
        if local(bf.tag) != "borderFill":
            continue
        props: StyleProps = {"fill": None}
        for ch in bf:
            name = local(ch.tag)
            if name in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
                try:
                    width = float((ch.get("width") or "0.1").split()[0])
                except ValueError:
                    width = 0.1
                props[name[:-6]] = (ch.get("type", "NONE"), width, ch.get("color", "#000000"))
            elif name == "fillBrush":
                for b in ch.iter():
                    if local(b.tag) == "winBrush":
                        face = (b.get("faceColor") or "none")
                        props["fill"] = None if face.lower() == "none" else face
        out[bf.get("id", "")] = props
    return out
