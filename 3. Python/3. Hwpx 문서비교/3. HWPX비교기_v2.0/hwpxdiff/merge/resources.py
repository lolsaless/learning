"""모양 번호 맞추기 (v2.0) — 다른 버전에서 가져온 본문 조각의 모양 번호를 받는 문서(base) 번호로 바꾼다.

HWPX 본문은 모양을 번호로 가리킨다 (charPrIDRef=글자모양, paraPrIDRef=문단모양, borderFillIDRef=테두리/배경,
styleIDRef=스타일, tabPrIDRef=탭). 같은 모양이라도 파일마다 번호가 다르므로(수정하면 새 번호가 뒤에 붙음):
  1) 출처 문서의 그 번호 정의(XML)를 읽고, 그 안의 번호(글꼴·테두리 등)부터 base 번호로 바꾼 뒤
  2) base 에 '똑같은 정의'가 있으면 그 번호를 쓰고, 없으면 base 목록 끝에 새 번호로 덧붙인다.
→ 원본 header.xml 은 덧붙이는 것 말고는 한 바이트도 바꾸지 않는다 (깨짐 방지).

    hm = HeaderMerger(base_header_bytes)
    src = hm.source(other_header_bytes)          # 출처 문서마다 하나
    frag2 = hm.remap(fragment_bytes, src)       # 본문 조각의 번호 바꾸기
    new_id = hm.derive_charpr("12", {"textColor": "#FF0000"})   # 글자모양 변형(빨간 글자) 추가
    new_header = hm.build()
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from ..hwpx.package import local
from ..hwpx.xmlspan import parse_with_spans

# 종류 → (목록 요소 이름, 본문에서 가리키는 속성 이름)
KINDS = {
    "charPr": ("charProperties", "charPrIDRef"),
    "paraPr": ("paraProperties", "paraPrIDRef"),
    "borderFill": ("borderFills", "borderFillIDRef"),
    "tabPr": ("tabProperties", "tabPrIDRef"),
    "style": ("styles", "styleIDRef"),
}
ATTR_TO_KIND = {attr: kind for kind, (_, attr) in KINDS.items()}
FONT_LANGS = {"hangul": "HANGUL", "latin": "LATIN", "hanja": "HANJA", "japanese": "JAPANESE",
              "other": "OTHER", "symbol": "SYMBOL", "user": "USER"}
REF_RE = re.compile(rb'\b(charPrIDRef|paraPrIDRef|borderFillIDRef|styleIDRef|tabPrIDRef)="(\d+)"')
ROOT_ID_RE = re.compile(rb'^(<[\w:]+\s+(?:[^>]*?\s)?)id="\d+"')
FONTREF_RE = re.compile(rb'<hh:fontRef\b[^>]*/?>')
FONTREF_ATTR_RE = re.compile(rb'\b(hangul|latin|hanja|japanese|other|symbol|user)="(\d+)"')

# 한글 버전마다 쓰거나 안 쓰는 '기본값' 속성 — 같은 모양인지 견줄 때 없는 것으로 본다.
# (예: 한글 13 은 paraPr 에 textDir="LTR" 을 쓰고 한글 12 는 안 씀 → 안 빼면 같은 문단모양이 중복 추가됨)
IGNORABLE_DEFAULTS = {("textDir", "LTR")}


def canonical(xml: bytes):
    """정의 XML → 견주기용 값 (속성 순서·맨 앞 id·기본값 속성 무시)."""
    import xml.etree.ElementTree as _ET

    def walk(el, root=False):
        attrs = tuple(sorted((k, v) for k, v in el.attrib.items()
                             if (k, v) not in IGNORABLE_DEFAULTS and not (root and k == "id")))
        return (el.tag, attrs, (el.text or "").strip(), tuple(walk(c) for c in el))
    try:
        return walk(_ET.fromstring(_wrap_ns(xml))[0], True)
    except _ET.ParseError:
        return strip_root_id(xml)


def _wrap_ns(xml: bytes) -> bytes:
    """접두어(hh:, hc:, hp:)가 선언되지 않은 조각을 해석할 수 있게 감싼다."""
    ns = b'xmlns:hh="h" xmlns:hc="c" xmlns:hp="p" xmlns:hp10="p10" xmlns:hs="s"'
    return b"<w " + ns + b">" + xml + b"</w>"


class HeaderInfo:
    """header.xml 한 개의 목록 정보 (번호 → 정의 XML 원문)."""

    def __init__(self, data: bytes):
        self.data = data
        root, spans = parse_with_spans(data)
        self.items: Dict[str, Dict[str, bytes]] = {k: {} for k in KINDS}
        self.containers: Dict[str, Tuple[int, int, int]] = {}   # 종류 → (목록 시작, 목록 끝, 닫는 태그 시작)
        self.fonts: Dict[str, Dict[str, bytes]] = {}             # 언어 → {번호: font XML}
        self.font_containers: Dict[str, Tuple[int, int, int]] = {}
        list_to_kind = {v[0]: k for k, v in KINDS.items()}
        for el in root.iter():
            name = local(el.tag)
            if name in list_to_kind:
                kind = list_to_kind[name]
                s, e = spans[id(el)]
                self.containers[kind] = (s, e, data.rindex(b"</", s, e))
                item_tag = kind
                for ch in el:
                    if local(ch.tag) == item_tag:
                        cs, ce = spans[id(ch)]
                        self.items[kind][ch.get("id", "")] = data[cs:ce]
            elif name == "fontface":
                lang = el.get("lang", "")
                s, e = spans[id(el)]
                self.font_containers[lang] = (s, e, data.rindex(b"</", s, e))
                self.fonts[lang] = {}
                for ch in el:
                    if local(ch.tag) == "font":
                        cs, ce = spans[id(ch)]
                        self.fonts[lang][ch.get("id", "")] = data[cs:ce]

    @staticmethod
    def face_of(font_xml: bytes) -> bytes:
        m = re.search(rb'\bface="([^"]*)"', font_xml)
        return m.group(1) if m else b""


def strip_root_id(xml: bytes) -> bytes:
    return ROOT_ID_RE.sub(rb"\1", xml, count=1)


def set_root_id(xml: bytes, new_id: str) -> bytes:
    if ROOT_ID_RE.search(xml):
        return ROOT_ID_RE.sub(lambda m: m.group(1) + b'id="' + new_id.encode() + b'"', xml, count=1)
    return re.sub(rb"^(<[\w:]+)", lambda m: m.group(1) + b' id="' + new_id.encode() + b'"', xml, count=1)


class SourceMap:
    """출처 문서 1개의 번호 → base 번호 대응표 (필요할 때 계산해 기억)."""

    def __init__(self, merger: "HeaderMerger", info: HeaderInfo):
        self.m = merger
        self.info = info
        self.cache: Dict[Tuple[str, str], str] = {}
        self.font_cache: Dict[Tuple[str, str], str] = {}

    def font(self, lang: str, sid: str) -> str:
        key = (lang, sid)
        if key not in self.font_cache:
            xml = self.info.fonts.get(lang, {}).get(sid)
            self.font_cache[key] = sid if xml is None else self.m._font_id(lang, xml)
        return self.font_cache[key]

    def map(self, kind: str, sid: str) -> str:
        key = (kind, sid)
        if key in self.cache:
            return self.cache[key]
        xml = self.info.items[kind].get(sid)
        if xml is None:                     # 출처에도 없는 번호 → 그대로 둠
            self.cache[key] = sid
            return sid
        self.cache[key] = sid               # 순환 참조 대비 임시값
        body = self._remap_inner(kind, xml)
        self.cache[key] = self.m._item_id(kind, body)
        return self.cache[key]

    def _remap_inner(self, kind: str, xml: bytes) -> bytes:
        def ref(m):
            k = ATTR_TO_KIND[m.group(1).decode()]
            if k == kind:                    # 자기 종류 참조(nextStyleIDRef 등)는 그대로
                return m.group(0)
            return m.group(1) + b'="' + self.map(k, m.group(2).decode()).encode() + b'"'
        out = REF_RE.sub(ref, xml)
        if kind == "charPr":
            def fontref(m):
                return FONTREF_ATTR_RE.sub(
                    lambda a: a.group(1) + b'="' + self.font(FONT_LANGS[a.group(1).decode()], a.group(2).decode()).encode() + b'"',
                    m.group(0))
            out = FONTREF_RE.sub(fontref, out)
        return out


class HeaderMerger:
    def __init__(self, base_header: bytes):
        self.base = HeaderInfo(base_header)
        self.index: Dict[str, Dict[bytes, str]] = {
            k: {canonical(x): i for i, x in self.base.items[k].items()} for k in KINDS}
        self.next_id: Dict[str, int] = {
            k: (max([int(i) for i in self.base.items[k] if i.isdigit()] or [-1]) + 1) for k in KINDS}
        self.appends: Dict[str, List[bytes]] = {k: [] for k in KINDS}
        self.font_index = {lang: {HeaderInfo.face_of(x): i for i, x in fs.items()} for lang, fs in self.base.fonts.items()}
        self.font_next = {lang: (max([int(i) for i in fs if i.isdigit()] or [-1]) + 1) for lang, fs in self.base.fonts.items()}
        self.font_appends: Dict[str, List[bytes]] = {lang: [] for lang in self.base.fonts}
        self._sources: Dict[int, SourceMap] = {}

    @property
    def added(self) -> int:
        return sum(len(v) for v in self.appends.values()) + sum(len(v) for v in self.font_appends.values())

    def source(self, header: bytes) -> SourceMap:
        key = hash(header)
        if key not in self._sources:
            self._sources[key] = SourceMap(self, HeaderInfo(header))
        return self._sources[key]

    def _item_id(self, kind: str, body_with_any_id: bytes) -> str:
        key = canonical(body_with_any_id)
        if key in self.index[kind]:
            return self.index[kind][key]
        if kind not in self.base.containers:
            raise ValueError(f"원본 header.xml 에 {KINDS[kind][0]} 목록이 없습니다")
        nid = str(self.next_id[kind])
        self.next_id[kind] += 1
        self.appends[kind].append(set_root_id(body_with_any_id, nid))
        self.index[kind][key] = nid
        return nid

    def _font_id(self, lang: str, font_xml: bytes) -> str:
        face = HeaderInfo.face_of(font_xml)
        if face in self.font_index.get(lang, {}):
            return self.font_index[lang][face]
        if lang not in self.base.font_containers:
            return "0"
        nid = str(self.font_next[lang])
        self.font_next[lang] += 1
        self.font_appends[lang].append(set_root_id(font_xml, nid))
        self.font_index[lang][face] = nid
        return nid

    def remap(self, fragment: bytes, src: Optional[SourceMap]) -> bytes:
        """본문 조각 속 모양 번호를 base 번호로. src=None 이면 이미 base 조각이라 그대로."""
        if src is None:
            return fragment
        return REF_RE.sub(lambda m: m.group(1) + b'="' + src.map(ATTR_TO_KIND[m.group(1).decode()],
                                                                    m.group(2).decode()).encode() + b'"', fragment)

    def derive_charpr(self, base_id: str, changes: Dict[str, str]) -> str:
        """base 글자모양을 바탕으로 속성만 바꾼 글자모양 번호 (예: {'textColor': '#FF0000'} → 빨간 글자)."""
        xml = self.base.items["charPr"].get(base_id)
        if xml is None:
            for app in self.appends["charPr"]:
                m = re.search(rb'id="(\d+)"', app)
                if m and m.group(1).decode() == base_id:
                    xml = app
        if xml is None:
            return base_id
        start_end = xml.index(b">")
        start, rest = xml[:start_end], xml[start_end:]
        for attr, val in changes.items():
            pat = re.compile(rb"\b" + attr.encode() + rb'="[^"]*"')
            if pat.search(start):
                start = pat.sub(attr.encode() + b'="' + val.encode() + b'"', start, count=1)
            else:
                start += b" " + attr.encode() + b'="' + val.encode() + b'"'
        return self._item_id("charPr", start + rest)

    def build(self) -> bytes:
        """덧붙일 정의를 목록 끝(닫는 태그 앞)에 넣고 itemCnt·fontCnt 를 고친 header.xml."""
        data = self.base.data
        edits: List[Tuple[int, int, bytes]] = []        # (시작, 끝, 바꿀 바이트)
        for kind, extra in self.appends.items():
            if not extra:
                continue
            s, e, close = self.base.containers[kind]
            edits.append((close, close, b"".join(extra)))
            edits.extend(_count_edit(data, s, b"itemCnt", len(self.base.items[kind]) + len(extra)))
        for lang, extra in self.font_appends.items():
            if not extra:
                continue
            s, e, close = self.base.font_containers[lang]
            edits.append((close, close, b"".join(extra)))
            edits.extend(_count_edit(data, s, b"fontCnt", len(self.base.fonts[lang]) + len(extra)))
        out = data
        for s, e, rep in sorted(edits, key=lambda x: (x[0], x[1]), reverse=True):
            out = out[:s] + rep + out[e:]
        return out


def _count_edit(data: bytes, tag_start: int, attr: bytes, value: int):
    tag_end = data.index(b">", tag_start)
    m = re.compile(rb"\b" + attr + rb'="(\d+)"').search(data, tag_start, tag_end)
    if not m:
        return []
    return [(m.start(1), m.end(1), str(value).encode())]
