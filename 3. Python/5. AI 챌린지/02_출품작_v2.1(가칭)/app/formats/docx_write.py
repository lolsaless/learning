# -*- coding: utf-8 -*-
"""[파일 형식] 간단한 워드(docx) 쓰기(시연자료용): 제목·문단·표. 표준 라이브러리만.

    DocxWriter("제목").title(…).para(…).table(rows).save(경로)
"""
import zipfile
from xml.sax.saxutils import escape

CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="xml" ContentType="application/xml"/>'
      '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
      '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
      '</Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '</Relationships>')
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _run(text, bold=False, size=None):
    rpr = "<w:rPr><w:rFonts w:ascii=\"Malgun Gothic\" w:eastAsia=\"맑은 고딕\" w:hAnsi=\"Malgun Gothic\"/>" + \
          ("<w:b/>" if bold else "") + (f'<w:sz w:val="{int(size * 2)}"/>' if size else "") + "</w:rPr>"
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


class DocxWriter:
    def __init__(self, title=""):
        self.meta_title = title
        self.body = []

    def _p(self, text, bold=False, size=None, center=False):
        ppr = '<w:pPr><w:jc w:val="center"/></w:pPr>' if center else ""
        self.body.append(f"<w:p>{ppr}{_run(text, bold, size)}</w:p>")
        return self

    def title(self, s):
        return self._p(s, True, 16, True)

    def heading(self, s):
        return self._p(s, True, 12)

    def para(self, s):
        return self._p(s)

    def note(self, s):
        return self._p(s, size=9)

    def blank(self):
        self.body.append("<w:p/>")
        return self

    def table(self, rows):
        ncol = max(len(r) for r in rows)
        b = '<w:tblBorders>' + "".join(f'<w:{k} w:val="single" w:sz="4" w:color="000000"/>'
                                         for k in ("top", "left", "bottom", "right", "insideH", "insideV")) + '</w:tblBorders>'
        out = [f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>{b}</w:tblPr><w:tblGrid>' +
               "".join('<w:gridCol w:w="1800"/>' for _ in range(ncol)) + "</w:tblGrid>"]
        for ri, r in enumerate(rows):
            out.append("<w:tr>")
            for c in list(r) + [""] * (ncol - len(r)):
                t = c.get("t", "") if isinstance(c, dict) else str(c)
                shade = '<w:shd w:val="clear" w:fill="E3E7F1"/>' if ri == 0 else ""
                out.append(f'<w:tc><w:tcPr>{shade}</w:tcPr><w:p><w:pPr><w:jc w:val="center"/></w:pPr>{_run(t, ri == 0)}</w:p></w:tc>')
            out.append("</w:tr>")
        out.append("</w:tbl>")
        self.body.append("".join(out))
        return self

    def save(self, path):
        doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W}><w:body>'
               + "".join(self.body) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
               '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/>'
               '</w:sectPr></w:body></w:document>')
        core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties '
                'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>' + escape(self.meta_title) +
                '</dc:title><dc:creator>시연자료(가상)</dc:creator></cp:coreProperties>')
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", CT)
            z.writestr("_rels/.rels", RELS)
            z.writestr("word/document.xml", doc)
            z.writestr("docProps/core.xml", core)
        return path
