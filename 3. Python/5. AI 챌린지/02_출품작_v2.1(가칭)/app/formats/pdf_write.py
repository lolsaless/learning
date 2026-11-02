# -*- coding: utf-8 -*-
"""[파일 형식] 간단한 PDF 쓰기(시연자료용): 제목·문단·표(선 포함), 한글 지원. 표준 라이브러리만.

한글은 PDF 표준 한국어 글꼴(HYGoThic-Medium, Adobe-Korea1)과 UniKS-UCS2-H 인코딩으로 적는다
(글꼴을 파일에 넣지 않으므로 파일이 작다. 보는 프로그램이 비슷한 한글 글꼴로 바꿔 보여 준다).

    w = PdfWriter("제목")
    w.title("…"); w.para("…"); w.table([["가", "1"], …]); w.save(경로)
"""
import zlib

PAGE_W, PAGE_H = 595.28, 841.89        # A4(포인트)
MARGIN = 56
LINE = 1.45


def _ucs2(s):
    return s.encode("utf-16-be", "replace").hex().upper()


def _w(s, size):
    """글자 폭 어림(한글·전각 1em, 반각 0.5em)."""
    return sum((1.0 if ord(ch) > 0x2E7F else 0.5) for ch in s) * size


class PdfWriter:
    def __init__(self, title=""):
        self.meta_title = title
        self.pages = []
        self.ops = []
        self.y = PAGE_H - MARGIN

    # ── 쪽 ──
    def _new_page(self):
        if self.ops:
            self.pages.append("\n".join(self.ops))
        self.ops = []
        self.y = PAGE_H - MARGIN

    def _need(self, h):
        if self.y - h < MARGIN:
            self._new_page()

    def _text(self, x, y, s, size):
        self.ops.append(f"BT /F1 {size:.1f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm <{_ucs2(s)}> Tj ET")

    def _wrap(self, s, size, width):
        lines, cur = [], ""
        for word in s.split(" "):
            t = (cur + " " + word).strip()
            if _w(t, size) > width and cur:
                lines.append(cur)
                cur = word
            else:
                cur = t
        if cur:
            lines.append(cur)
        out = []
        for ln in lines:                       # 띄어쓰기 없는 긴 줄도 자른다
            while _w(ln, size) > width:
                k = max(1, int(len(ln) * width / _w(ln, size)))
                out.append(ln[:k])
                ln = ln[k:]
            out.append(ln)
        return out or [""]

    # ── 내용 ──
    def title(self, s, size=16):
        self._need(size * 2)
        self._text((PAGE_W - _w(s, size)) / 2, self.y - size, s, size)
        self.y -= size * 2.2
        return self

    def heading(self, s, size=12):
        return self.para(s, size, gap=6)

    def para(self, s, size=10.5, gap=2):
        for ln in self._wrap(s, size, PAGE_W - 2 * MARGIN):
            self._need(size * LINE)
            self._text(MARGIN, self.y - size, ln, size)
            self.y -= size * LINE
        self.y -= gap
        return self

    def note(self, s):
        return self.para(s, 9)

    def blank(self):
        self.y -= 8
        return self

    def table(self, rows, size=9.5, widths=None):
        rows = [[(c.get("t", "") if isinstance(c, dict) else str(c)) for c in r] for r in rows]
        ncol = max(len(r) for r in rows)
        widths = widths or [3] + [2] * (ncol - 1)
        tot = sum(widths[:ncol])
        cw = [(PAGE_W - 2 * MARGIN) * w / tot for w in widths[:ncol]]
        rh = size * 1.9
        self._need(rh * min(3, len(rows)))          # 머리글이 쪽 끝에 혼자 남지 않게
        for ri, r in enumerate(rows):
            self._need(rh)
            x = MARGIN
            bot = self.y - rh
            for ci in range(ncol):
                s = r[ci] if ci < len(r) else ""
                self.ops.append(f"0.5 w {x:.2f} {bot:.2f} {cw[ci]:.2f} {rh:.2f} re S")
                if ri == 0:
                    self.ops.append(f"0.9 0.92 0.96 rg {x + 0.5:.2f} {bot + 0.5:.2f} {cw[ci] - 1:.2f} {rh - 1:.2f} re f 0 g")
                fs = size
                while s and _w(s, fs) > cw[ci] - 4 and fs > 5.5:     # 넘치면 글자를 줄인다(자르지 않음)
                    fs -= 0.5
                while s and _w(s, fs) > cw[ci] - 2:
                    s = s[:-1]
                tx = x + (cw[ci] - _w(s, fs)) / 2
                self._text(tx, bot + (rh - fs) / 2 + 1.5, s, fs)
                x += cw[ci]
            self.y = bot
        self.y -= 8
        return self

    # ── 저장 ──
    def save(self, path):
        self._new_page()
        if not self.pages:
            self.pages = [""]
        objs = []

        def add(s):
            objs.append(s)
            return len(objs)
        cat = add(None)
        pages = add(None)
        font = add("<< /Type /Font /Subtype /Type0 /BaseFont /HYGoThic-Medium /Encoding /UniKS-UCS2-H "
                   "/DescendantFonts [ 4 0 R ] >>")
        add("<< /Type /Font /Subtype /CIDFontType0 /BaseFont /HYGoThic-Medium "
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (Korea1) /Supplement 1 >> /FontDescriptor 5 0 R "
            "/DW 1000 /W [ 1 95 500 8094 8190 500 ] >>")
        add("<< /Type /FontDescriptor /FontName /HYGoThic-Medium /Flags 6 /FontBBox [ -6 -145 1003 880 ] "
            "/ItalicAngle 0 /Ascent 880 /Descent -120 /CapHeight 880 /StemV 93 >>")
        kids = []
        for content in self.pages:
            data = zlib.compress(content.encode("latin-1"))
            c = add(("<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data)).encode("latin-1") + data + b"\nendstream")
            kids.append(add(f"<< /Type /Page /Parent {pages} 0 R /MediaBox [ 0 0 {PAGE_W} {PAGE_H} ] "
                            f"/Resources << /Font << /F1 {font} 0 R >> >> /Contents {c} 0 R >>"))
        objs[cat - 1] = f"<< /Type /Catalog /Pages {pages} 0 R >>"
        objs[pages - 1] = f"<< /Type /Pages /Count {len(kids)} /Kids [ {' '.join(f'{k} 0 R' for k in kids)} ] >>"
        info = add(f"<< /Title <FEFF{_ucs2(self.meta_title)}> /Producer (시연자료 가상) >>".encode("latin-1", "replace"))
        out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
        offs = []
        for i, o in enumerate(objs, 1):
            offs.append(len(out))
            body = o if isinstance(o, (bytes, bytearray)) else o.encode("latin-1")
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        x = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        for o in offs:
            out += f"{o:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {len(objs) + 1} /Root {cat} 0 R /Info {info} 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
        with open(path, "wb") as f:
            f.write(out)
        return path
