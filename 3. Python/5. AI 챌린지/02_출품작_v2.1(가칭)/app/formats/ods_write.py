# -*- coding: utf-8 -*-
"""[파일 형식] 간단한 오픈문서 스프레드시트(ods) 쓰기(시연자료용). write_xlsx 와 같은 시트 목록을 받는다.

    write_ods(경로, [{"name": 시트, "rows": [[값 | {"v": 값, "fmt": "0.0"}…]…]}, …])
"""
import re
from decimal import Decimal, ROUND_HALF_UP
import zipfile
from xml.sax.saxutils import escape

MIMETYPE = "application/vnd.oasis.opendocument.spreadsheet"
NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2"')


def _half_up(v, d):
    """엑셀·한국 문서처럼 사사오입(파이썬 기본 반올림은 짝수 쪽으로 반올림해 .5에서 다름)."""
    return float(Decimal(repr(float(v))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def _shown(v, fmt):
    if not fmt:
        return f"{v:,}" if isinstance(v, int) else (f"{v}" if isinstance(v, float) else str(v))
    if fmt.endswith("%"):
        d = len(re.search(r"0\.?(0*)", fmt).group(1))
        return f"{_half_up(v * 100, d):.{d}f}%"
    m = re.search(r"\.(0+)", fmt)
    d = len(m.group(1)) if m else 0
    return f"{_half_up(v, d):,.{d}f}" if "," in fmt else f"{_half_up(v, d):.{d}f}"


def write_ods(path, sheets):
    body = []
    for sh in sheets:
        body.append(f'<table:table table:name="{escape(sh["name"])}">')
        for row in sh["rows"]:
            body.append("<table:table-row>")
            for c in row:
                spec = c if isinstance(c, dict) else {"v": c}
                v, fmt = spec.get("v", ""), spec.get("fmt")
                if isinstance(v, bool) or v is None or v == "":
                    body.append(f'<table:table-cell><text:p>{escape(str(v or ""))}</text:p></table:table-cell>' if v else "<table:table-cell/>")
                elif isinstance(v, (int, float)):
                    vt = "percentage" if fmt and fmt.endswith("%") else "float"
                    body.append(f'<table:table-cell office:value-type="{vt}" office:value="{v!r}">'
                                f'<text:p>{escape(_shown(v, fmt))}</text:p></table:table-cell>')
                else:
                    body.append(f'<table:table-cell office:value-type="string"><text:p>{escape(str(v))}</text:p></table:table-cell>')
            body.append("</table:table-row>")
        body.append("</table:table>")
    content = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {NS}><office:body><office:spreadsheet>'
               + "".join(body) + "</office:spreadsheet></office:body></office:document-content>")
    manifest = ('<?xml version="1.0" encoding="UTF-8"?><manifest:manifest '
                'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
                f'<manifest:file-entry manifest:full-path="/" manifest:media-type="{MIMETYPE}"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE, compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
    return path
