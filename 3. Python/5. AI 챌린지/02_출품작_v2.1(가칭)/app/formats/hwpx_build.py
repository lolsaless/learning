# -*- coding: utf-8 -*-
"""새 hwpx 문서 만들기(시연 자료 생성용).

한글(Hancom Office)이 실제로 저장한 문서의 머리 정보(header.xml: 글꼴·문단·테두리 모양)를 틀로 쓰고,
본문(section0.xml)만 새로 만든다. 사용하는 모양 번호는 틀 문서에 있는 번호다.
"""
import os
import zlib
import struct
import zipfile
import datetime
from xml.sax.saxutils import escape

TPL = os.path.join(os.path.dirname(__file__), "hwpx_template")

# 틀 문서(header.xml)에 있는 모양 번호
CP = {"title": 99, "head": 74, "body": 75, "note": 83, "th": 84, "td": 85, "blank": 87, "tblrun": 82}
PP = {"title": 76, "head": 86, "body": 79, "note": 83, "th": 72, "td": 73, "tdl": 74, "blank": 76, "tbl": 83}
BF = {"th": 19, "td": 14, "tbl": 14, "total": 19}
TEXT_WIDTH = 47624     # 표 전체 너비(HWPUNIT)
ROW_H = 1765


def _t(s):
    return escape(s or "")


def _png(w=8, h=8):
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * w for _ in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class HwpxBuilder:
    def __init__(self, title_meta=""):
        self.title_meta = title_meta
        self.parts = []
        self.plain = []
        self._tbl_id = 1395921000
        self._z = 0
        self._first_title = None

    # ── 문단 ──
    def _p(self, text, pp, cp):
        self.plain.append(text)
        if text:
            return (f'<hp:p id="2147483648" paraPrIDRef="{pp}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                    f'<hp:run charPrIDRef="{cp}"><hp:t>{_t(text)}</hp:t></hp:run></hp:p>')
        return (f'<hp:p id="2147483648" paraPrIDRef="{pp}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                f'<hp:run charPrIDRef="{cp}"/></hp:p>')

    def title(self, text):
        if self._first_title is None and not self.parts:
            self._first_title = text
            self.plain.append(text)
        else:
            self.parts.append(self._p(text, PP["title"], CP["title"]))

    def blank(self):
        self.parts.append(self._p("", PP["blank"], CP["blank"]))

    def heading(self, text):
        self.parts.append(self._p(text, PP["head"], CP["head"]))

    def body(self, text):
        self.parts.append(self._p(" ○ " + text, PP["body"], CP["body"]))

    def text(self, text):
        self.parts.append(self._p(text, PP["body"], CP["body"]))

    def note(self, text):
        self.parts.append(self._p(text, PP["note"], CP["note"]))

    # ── 표 ──
    def table(self, rows, widths=None, header_rows=1, label_cols=1, left_cols=()):
        """rows: [[칸, ...]], 칸 = 글자 | {"t": 글자, "cs": 열합치기, "rs": 행합치기} | None(합쳐져 가려진 칸)"""
        nrow = len(rows)
        ncol = max(sum((c.get("cs", 1) if isinstance(c, dict) else 1) for c in r if c is not None) for r in rows)
        # 가려진 칸까지 포함한 열 수 계산
        ncol = max(ncol, max(len(r) for r in rows))
        if not widths:
            widths = [1] * ncol
        tot = sum(widths)
        cw = [int(TEXT_WIDTH * w / tot) for w in widths]
        cw[-1] += TEXT_WIDTH - sum(cw)
        self._tbl_id += 1
        self._z += 1
        h = ROW_H * nrow
        out = [f'<hp:p id="2147483648" paraPrIDRef="{PP["tbl"]}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
               f'<hp:run charPrIDRef="{CP["tblrun"]}">'
               f'<hp:tbl id="{self._tbl_id}" zOrder="{self._z}" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" rowCnt="{nrow}" colCnt="{ncol}" cellSpacing="0" borderFillIDRef="{BF["tbl"]}" noAdjust="0">'
               f'<hp:sz width="{TEXT_WIDTH}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
               '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
               '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
               '<hp:inMargin left="510" right="510" top="141" bottom="141"/>']
        for ri, row in enumerate(rows):
            out.append("<hp:tr>")
            ci = 0
            for cell in row:
                if cell is None:
                    ci += 1
                    continue
                spec = cell if isinstance(cell, dict) else {"t": cell}
                text = spec.get("t", "")
                cs, rs = spec.get("cs", 1), spec.get("rs", 1)
                is_head = ri < header_rows
                is_label = ci < label_cols
                is_total = spec.get("total", False)
                bf = BF["th"] if (is_head or is_total) else BF["td"]
                cp = CP["th"] if (is_head or is_total or (is_label and spec.get("bold"))) else CP["td"]
                pp = PP["th"] if is_head else (PP["tdl"] if ci in left_cols else PP["td"])
                w = sum(cw[ci:ci + cs])
                para = (f'<hp:p id="2147483648" paraPrIDRef="{pp}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                        + (f'<hp:run charPrIDRef="{cp}"><hp:t>{_t(text)}</hp:t></hp:run>' if text else f'<hp:run charPrIDRef="{cp}"/>')
                        + '</hp:p>')
                out.append(f'<hp:tc name="" header="{1 if is_head else 0}" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="{bf}">'
                           '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                           f'{para}</hp:subList>'
                           f'<hp:cellAddr colAddr="{ci}" rowAddr="{ri}"/><hp:cellSpan colSpan="{cs}" rowSpan="{rs}"/>'
                           f'<hp:cellSz width="{w}" height="{ROW_H * rs}"/><hp:cellMargin left="510" right="510" top="141" bottom="141"/></hp:tc>')
                self.plain.append(text)
                ci += cs
            out.append("</hp:tr>")
        out.append("</hp:tbl><hp:t/></hp:run></hp:p>")
        self.parts.append("".join(out))

    # ── 저장 ──
    def section_xml(self):
        head = open(os.path.join(TPL, "section_head.xml"), encoding="utf-8").read()
        head = head.replace('paraPrIDRef="64"', f'paraPrIDRef="{PP["title"]}"', 1)
        title = self._first_title or ""
        first = (head
                 + '<hp:run charPrIDRef="98"><hp:ctrl><hp:pageNum pos="BOTTOM_CENTER" formatType="DIGIT" sideChar="-"/></hp:ctrl></hp:run>'
                 + f'<hp:run charPrIDRef="{CP["title"]}"><hp:t>{_t(title)}</hp:t></hp:run></hp:p>')
        return first + "".join(self.parts) + "</hs:sec>"

    def save(self, path):
        def tpl(name):
            with open(os.path.join(TPL, name.replace("/", "__")), "rb") as f:
                return f.read()
        now = datetime.datetime.now()
        hpf = tpl("Contents/content.hpf").decode("utf-8")
        import re
        title = self.title_meta or (self._first_title or "")
        hpf = re.sub(r"<opf:title>.*?</opf:title>", f"<opf:title>{_t(title)}</opf:title>", hpf)
        hpf = re.sub(r'(name="creator" content="text">)[^<]*', r"\g<1>시연자료(가상)", hpf)
        hpf = re.sub(r'(name="lastsaveby" content="text">)[^<]*', r"\g<1>시연자료(가상)", hpf)
        stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        hpf = re.sub(r'(name="CreatedDate" content="text">)[^<]*', r"\g<1>" + stamp, hpf)
        hpf = re.sub(r'(name="ModifiedDate" content="text">)[^<]*', r"\g<1>" + stamp, hpf)
        hpf = re.sub(r'(name="date" content="text">)[^<]*', r"\g<1>" + now.strftime("%Y년 %m월 %d일"), hpf)
        prv = "\r\n".join(t for t in self.plain if t)[:1000]
        settings = tpl("settings.xml").decode("utf-8")
        settings = re.sub(r'<ha:CaretPosition [^>]*/>', '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/>', settings)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with zipfile.ZipFile(path, "w") as z:
            def put(name, data, store=False):
                zi = zipfile.ZipInfo(name, date_time=now.timetuple()[:6])
                zi.compress_type = zipfile.ZIP_STORED if store else zipfile.ZIP_DEFLATED
                z.writestr(zi, data)
            put("mimetype", tpl("mimetype"), True)
            put("version.xml", tpl("version.xml"), True)
            put("Contents/header.xml", tpl("Contents/header.xml"))
            put("Contents/section0.xml", self.section_xml().encode("utf-8"))
            put("Preview/PrvText.txt", prv.encode("utf-8"))
            put("settings.xml", settings.encode("utf-8"))
            put("Preview/PrvImage.png", _png(), True)
            put("META-INF/container.rdf", tpl("META-INF/container.rdf"))
            put("Contents/content.hpf", hpf.encode("utf-8"))
            put("META-INF/container.xml", tpl("META-INF/container.xml"))
            put("META-INF/manifest.xml", tpl("META-INF/manifest.xml"))
        return path
