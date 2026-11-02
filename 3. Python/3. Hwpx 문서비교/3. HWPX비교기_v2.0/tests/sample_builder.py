"""시험용 HWPX 만들기 — 실제 업무 문서 없이도 시험할 수 있도록 최소 구조의 HWPX 를 코드로 생성한다.

    make_hwpx(paragraphs, table=None, modified="2026-01-01T00:00:00Z") -> bytes
    paragraphs : [str | [(글자, 글자모양번호), ...]]   글자모양 0=검정, 1=빨강, 2=검정 굵게
    table      : [[셀 글자, ...], ...]  (행 목록)
    (v2.0) extra_charprs : 글자모양 목록 끝에 덧붙일 정의 [(번호, 색)] — 한글이 고칠 때 새 글자모양을 붙이는 것 흉내
           caption       : 표를 품은 문단의 자기 글자 (표 앞에 같은 문단 안 run 으로)
           para_attrs    : True 면 문단모양 목록(paraProperties)도 넣음 (textDir 기본값 시험용 extra_para_attr)
"""
from __future__ import annotations

import io
import zipfile
from typing import List, Optional, Sequence, Tuple, Union
from xml.sax.saxutils import escape

NS = ('xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
      'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
      'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
      'xmlns:opf="http://www.idpf.org/2007/opf/"')

BASE_CHARPRS = [
    '<hh:charPr id="0" height="1000" textColor="#000000" shadeColor="none"><hh:fontRef hangul="0"/></hh:charPr>',
    '<hh:charPr id="1" height="1000" textColor="#FF0000" shadeColor="none"><hh:fontRef hangul="0"/></hh:charPr>',
    '<hh:charPr id="2" height="1000" textColor="#000000" shadeColor="none"><hh:fontRef hangul="0"/><hh:bold/></hh:charPr>',
]


def header(extra_charprs=(), para_attr: str = "", fonts=("함초롬바탕",)) -> str:
    cps = BASE_CHARPRS + [f'<hh:charPr id="{i}" height="1200" textColor="{c}" shadeColor="none"><hh:fontRef hangul="{len(fonts) - 1}"/></hh:charPr>'
                          for i, c in extra_charprs]
    font_xml = "".join(f'<hh:font id="{k}" face="{f}"/>' for k, f in enumerate(fonts))
    return (f'<?xml version="1.0" encoding="UTF-8"?><hh:head {NS}><hh:refList>'
            f'<hh:fontfaces itemCnt="1"><hh:fontface lang="HANGUL" fontCnt="{len(fonts)}">{font_xml}</hh:fontface></hh:fontfaces>'
            f'<hh:charProperties itemCnt="{len(cps)}">{"".join(cps)}</hh:charProperties>'
            f'<hh:paraProperties itemCnt="1"><hh:paraPr id="0" condense="0"{para_attr}><hh:align horizontal="JUSTIFY"/></hh:paraPr></hh:paraProperties>'
            f'</hh:refList></hh:head>')


HEADER = header()

Para = Union[str, Sequence[Tuple[str, int]]]


def _runs(p: Para) -> str:
    runs = [(p, 0)] if isinstance(p, str) else p
    return "".join(f'<hp:run charPrIDRef="{cp}"><hp:t>{escape(t)}</hp:t></hp:run>' for t, cp in runs)


def _para(p: Para, vpos: int = 0) -> str:
    return (f'<hp:p paraPrIDRef="0">{_runs(p)}'
            f'<hp:linesegarray><hp:lineseg vertpos="{vpos}"/></hp:linesegarray></hp:p>')


def _table(rows: List[List[str]], caption: str = "") -> str:
    trs = []
    for r, row in enumerate(rows):
        tcs = "".join(
            f'<hp:tc><hp:subList>{_para(cell)}</hp:subList><hp:cellAddr colAddr="{c}" rowAddr="{r}"/></hp:tc>'
            for c, cell in enumerate(row))
        trs.append(f"<hp:tr>{tcs}</hp:tr>")
    cap = f'<hp:run charPrIDRef="0"><hp:t>{escape(caption)}</hp:t></hp:run>' if caption else ""
    return f'<hp:p paraPrIDRef="0">{cap}<hp:run charPrIDRef="0"><hp:tbl>{"".join(trs)}</hp:tbl></hp:run></hp:p>'


def make_hwpx(paragraphs: List[Para], table: Optional[List[List[str]]] = None,
              modified: str = "2026-01-01T00:00:00Z", author: str = "tester",
              extra_charprs=(), caption: str = "", para_attr: str = "", fonts=("함초롬바탕",),
              after_table: Optional[List[Para]] = None) -> bytes:
    body = "".join(_para(p, 1000 * i) for i, p in enumerate(paragraphs))
    if table:
        body += _table(table, caption)
    body += "".join(_para(p) for p in (after_table or []))
    section = f'<?xml version="1.0" encoding="UTF-8"?><hs:sec {NS}>{body}</hs:sec>'
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<opf:package {NS}><opf:metadata><opf:title/>
<opf:meta name="creator" content="text">{author}</opf:meta>
<opf:meta name="lastsaveby" content="text">{author}</opf:meta>
<opf:meta name="ModifiedDate" content="text">{modified}</opf:meta></opf:metadata>
<opf:manifest><opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>
<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>
<opf:spine><opf:itemref idref="header"/><opf:itemref idref="section0"/></opf:spine></opf:package>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/hwp+zip")
        z.writestr("Contents/content.hpf", content)
        z.writestr("Contents/header.xml", header(extra_charprs, para_attr, fonts))
        z.writestr("Contents/section0.xml", section)
    return buf.getvalue()
