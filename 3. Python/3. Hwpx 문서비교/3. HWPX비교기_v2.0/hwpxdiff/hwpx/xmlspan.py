"""위치 기억 XML 읽기 (v2.0) — 요소마다 원본 파일 속 바이트 위치(시작, 끝)를 함께 기록한다.

왜 필요한가: 병합·고치기에서 **원본 XML 을 다시 쓰지 않고 바뀐 부분만 바이트째 갈아 끼우기** 위해서.
(ElementTree 로 읽고 다시 저장하면 hp:/hh: 접두어가 ns0: 등으로 바뀌어 한글이 못 열 수 있다)

    root, spans = parse_with_spans(xml_bytes)
    s, e = spans[id(element)]        # xml_bytes[s:e] == 그 요소의 원문 그대로

만들어지는 요소는 표준 xml.etree.ElementTree.Element 이고, 태그·속성 이름은 원문 그대로('hp:p').
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
import xml.parsers.expat
from typing import Dict, List, Tuple

Spans = Dict[int, Tuple[int, int]]


def _tag_end(data: bytes, start: int) -> int:
    """data[start] == '<' 인 태그의 닫는 '>' 다음 위치 (따옴표 안의 '>' 는 건너뜀)."""
    i, quote = start + 1, 0
    n = len(data)
    while i < n:
        c = data[i]
        if quote:
            if c == quote:
                quote = 0
        elif c in (0x22, 0x27):          # " '
            quote = c
        elif c == 0x3E:                  # >
            return i + 1
        i += 1
    raise ValueError("XML 태그가 닫히지 않았습니다")


def parse_with_spans(data: bytes) -> Tuple[ET.Element, Spans]:
    p = xml.parsers.expat.ParserCreate()
    p.buffer_text = True
    stack: List[ET.Element] = []
    spans: Spans = {}
    starts: List[int] = []
    root_holder: List[ET.Element] = []

    def start(name, attrs):
        el = ET.Element(name, attrs)
        if stack:
            stack[-1].append(el)
        else:
            root_holder.append(el)
        stack.append(el)
        starts.append(p.CurrentByteIndex)

    def end(name):
        el = stack.pop()
        s = starts.pop()
        te = _tag_end(data, s)
        if data[te - 2:te] == b"/>":     # <a/> 처럼 스스로 닫힌 요소 (expat 은 이때 다음 토큰 위치를 알려 줌)
            e = te
        else:
            e = _tag_end(data, p.CurrentByteIndex)
        spans[id(el)] = (s, e)

    def chars(text):
        if not stack:
            return
        cur = stack[-1]
        if len(cur):
            last = cur[-1]
            last.tail = (last.tail or "") + text
        else:
            cur.text = (cur.text or "") + text

    p.StartElementHandler = start
    p.EndElementHandler = end
    p.CharacterDataHandler = chars
    p.Parse(data, True)
    return root_holder[0], spans
