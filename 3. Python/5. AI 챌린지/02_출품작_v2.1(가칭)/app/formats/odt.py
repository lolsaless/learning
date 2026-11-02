# -*- coding: utf-8 -*-
"""[ODT 파일] 오픈문서 텍스트(.odt) 쓰기·읽기(표준 라이브러리만).

전자문서시스템에서 공문을 내려받으면 ODT 로 오는 경우가 많아, 시연용 가상 공문을 ODT 로도 만든다.

쓰기:  OdtBuilder().title(…).heading(…).body(…).table(rows).save(경로)
읽기:  read_odt(경로) → {"paras": [글자…], "tables": [[[칸 글자…]…]…]}
"""
import re
import html
import zipfile
from xml.sax.saxutils import escape

MIMETYPE = "application/vnd.oasis.opendocument.text"

_NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
       'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
       'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
       'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
       'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
       'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
       'xmlns:dc="http://purl.org/dc/elements/1.1/" office:version="1.2"')

_STYLES = """
<style:style style:name="P_title" style:family="paragraph"><style:paragraph-properties fo:text-align="center" fo:margin-bottom="0.3cm"/><style:text-properties fo:font-size="17pt" fo:font-weight="bold" style:font-name="맑은 고딕"/></style:style>
<style:style style:name="P_head" style:family="paragraph"><style:paragraph-properties fo:margin-top="0.25cm"/><style:text-properties fo:font-size="11pt" fo:font-weight="bold"/></style:style>
<style:style style:name="P_body" style:family="paragraph"><style:paragraph-properties fo:text-align="justify"/><style:text-properties fo:font-size="10.5pt"/></style:style>
<style:style style:name="P_note" style:family="paragraph"><style:text-properties fo:font-size="9pt" fo:color="#444444"/></style:style>
<style:style style:name="P_center" style:family="paragraph"><style:paragraph-properties fo:text-align="center"/><style:text-properties fo:font-size="14pt" fo:font-weight="bold"/></style:style>
<style:style style:name="P_cell" style:family="paragraph"><style:paragraph-properties fo:text-align="center"/><style:text-properties fo:font-size="9.5pt"/></style:style>
<style:style style:name="T1" style:family="table"><style:table-properties style:width="16cm" table:align="center"/></style:style>
<style:style style:name="TC" style:family="table-cell"><style:table-cell-properties fo:border="0.5pt solid #000000" fo:padding="0.08cm"/></style:style>
<style:style style:name="TH" style:family="table-cell"><style:table-cell-properties fo:border="0.5pt solid #000000" fo:padding="0.08cm" fo:background-color="#E3E7F1"/></style:style>
"""


class OdtBuilder:
    def __init__(self, title_meta=""):
        self.meta_title = title_meta
        self.parts = []

    def _p(self, style, text):
        self.parts.append(f'<text:p text:style-name="{style}">{escape(text)}</text:p>')
        return self

    def title(self, text):
        return self._p("P_title", text)

    def center(self, text):
        return self._p("P_center", text)

    def heading(self, text):
        return self._p("P_head", text)

    def body(self, text):
        return self._p("P_body", text)

    def note(self, text):
        return self._p("P_note", text)

    def blank(self):
        return self._p("P_body", "")

    def table(self, rows, header_rows=1):
        """rows: [[글자, …], …] (칸 합치기 없음)"""
        ncol = max(len(r) for r in rows)
        out = ['<table:table table:name="표%d" table:style-name="T1">' % (len(self.parts) + 1),
               f'<table:table-column table:number-columns-repeated="{ncol}"/>']
        for ri, row in enumerate(rows):
            out.append("<table:table-row>")
            for c in list(row) + [""] * (ncol - len(row)):
                txt = c.get("t", "") if isinstance(c, dict) else str(c)
                st = "TH" if ri < header_rows else "TC"
                out.append(f'<table:table-cell table:style-name="{st}" office:value-type="string">'
                           f'<text:p text:style-name="P_cell">{escape(txt)}</text:p></table:table-cell>')
            out.append("</table:table-row>")
        out.append("</table:table>")
        self.parts.append("".join(out))
        return self

    def save(self, path):
        content = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {_NS}>'
                   f'<office:automatic-styles>{_STYLES}</office:automatic-styles>'
                   f'<office:body><office:text>{"".join(self.parts)}</office:text></office:body></office:document-content>')
        meta = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-meta {_NS}><office:meta>'
                f'<dc:title>{escape(self.meta_title)}</dc:title><meta:generator>시연자료(가상)</meta:generator>'
                '</office:meta></office:document-meta>')
        styles = f'<?xml version="1.0" encoding="UTF-8"?><office:document-styles {_NS}><office:styles/></office:document-styles>'
        manifest = ('<?xml version="1.0" encoding="UTF-8"?>'
                    '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
                    f'<manifest:file-entry manifest:full-path="/" manifest:media-type="{MIMETYPE}"/>'
                    '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                    '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>'
                    '<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>'
                    '</manifest:manifest>')
        with zipfile.ZipFile(path, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE, compress_type=zipfile.ZIP_STORED)
            z.writestr("META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("styles.xml", styles, compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("meta.xml", meta, compress_type=zipfile.ZIP_DEFLATED)
        return path


def _txt(x):
    x = re.sub(r"<text:s[^>]*/>", " ", x)
    x = re.sub(r"<text:tab/>", "\t", x)
    x = re.sub(r"<text:line-break/>", "\n", x)
    return html.unescape(re.sub(r"<[^>]+>", "", x)).strip()


def read_odt(path):
    """ODT 본문 문단과 표 글자를 읽는다(서식은 읽지 않음)."""
    x = zipfile.ZipFile(path).read("content.xml").decode("utf-8")
    tables = []
    for tb in re.findall(r"<table:table .*?</table:table>", x, flags=re.S):
        rows = []
        for tr in re.findall(r"<table:table-row.*?</table:table-row>", tb, flags=re.S):
            rows.append([_txt(c) for c in re.findall(r"<table:table-cell.*?</table:table-cell>", tr, flags=re.S)])
        tables.append(rows)
    body = re.sub(r"<table:table .*?</table:table>", "", x, flags=re.S)
    paras = [_txt(p) for p in re.findall(r"<text:(?:p|h)[^>]*>(.*?)</text:(?:p|h)>", body, flags=re.S)]
    return {"paras": [p for p in paras if p], "tables": tables}
