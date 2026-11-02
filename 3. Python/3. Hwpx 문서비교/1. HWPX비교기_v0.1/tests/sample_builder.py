"""시험용 HWPX 만들기 — 실제 업무 문서 없이도 시험할 수 있도록 최소 구조의 HWPX 를 코드로 생성한다.

    make_hwpx(paragraphs, table=None, modified="2026-01-01T00:00:00Z") -> bytes
    paragraphs : [str | [(글자, 글자모양번호), ...]]   글자모양 0=검정, 1=빨강, 2=검정 굵게
    table      : [[셀 글자, ...], ...]  (행 목록)
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

HEADER = f"""<?xml version="1.0" encoding="UTF-8"?>
<hh:head {NS}><hh:refList>
<hh:fontfaces><hh:fontface lang="HANGUL"><hh:font id="0" face="함초롬바탕"/></hh:fontface></hh:fontfaces>
<hh:charProperties>
<hh:charPr id="0" height="1000" textColor="#000000" shadeColor="none"><hh:fontRef hangul="0"/></hh:charPr>
<hh:charPr id="1" height="1000" textColor="#FF0000" shadeColor="none"><hh:fontRef hangul="0"/></hh:charPr>
<hh:charPr id="2" height="1000" textColor="#000000" shadeColor="none"><hh:fontRef hangul="0"/><hh:bold/></hh:charPr>
</hh:charProperties></hh:refList></hh:head>"""

Para = Union[str, Sequence[Tuple[str, int]]]


def _runs(p: Para) -> str:
    runs = [(p, 0)] if isinstance(p, str) else p
    return "".join(f'<hp:run charPrIDRef="{cp}"><hp:t>{escape(t)}</hp:t></hp:run>' for t, cp in runs)


def _para(p: Para, vpos: int = 0) -> str:
    return (f'<hp:p paraPrIDRef="0">{_runs(p)}'
            f'<hp:linesegarray><hp:lineseg vertpos="{vpos}"/></hp:linesegarray></hp:p>')


def _table(rows: List[List[str]]) -> str:
    trs = []
    for r, row in enumerate(rows):
        tcs = "".join(
            f'<hp:tc><hp:subList>{_para(cell)}</hp:subList><hp:cellAddr colAddr="{c}" rowAddr="{r}"/></hp:tc>'
            for c, cell in enumerate(row))
        trs.append(f"<hp:tr>{tcs}</hp:tr>")
    return f'<hp:p><hp:run charPrIDRef="0"><hp:tbl>{"".join(trs)}</hp:tbl></hp:run></hp:p>'


def make_hwpx(paragraphs: List[Para], table: Optional[List[List[str]]] = None,
              modified: str = "2026-01-01T00:00:00Z", author: str = "tester") -> bytes:
    body = "".join(_para(p, 1000 * i) for i, p in enumerate(paragraphs))
    if table:
        body += _table(table)
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
        z.writestr("Contents/header.xml", HEADER)
        z.writestr("Contents/section0.xml", section)
    return buf.getvalue()
