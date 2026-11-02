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
