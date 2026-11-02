# -*- coding: utf-8 -*-
"""[PDF ③] 글꼴: 글자 코드 → 글자(ToUnicode 대응표, 한국어 UCS-2 인코딩, WinAnsi)와 글자 폭."""
import re

from app.formats.pdf.lexer import Name

# 숫자·기호 글리프 이름(Differences 용, 자주 쓰는 것만)
AGL = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
       "eight": "8", "nine": "9", "period": ".", "comma": ",", "percent": "%", "space": " ", "hyphen": "-",
       "minus": "-", "parenleft": "(", "parenright": ")", "slash": "/", "colon": ":", "plus": "+"}


def _hex(b):
    return int(b, 16)


def parse_cmap(data):
    """ToUnicode CMap → ({코드: 글자}, 코드 바이트 수 집합)."""
    t = data.decode("latin-1", "ignore")
    m, lens = {}, set()
    for blk in re.findall(r"begincodespacerange(.*?)endcodespacerange", t, flags=re.S):
        for lo, _ in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            lens.add(len(lo) // 2)

    def u(hx):
        try:
            return bytes.fromhex(hx).decode("utf-16-be", "replace")
        except ValueError:
            return ""
    for blk in re.findall(r"beginbfchar(.*?)endbfchar", t, flags=re.S):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", blk):
            m[_hex(src)] = u(dst)
            lens.add(len(src) // 2)
    for blk in re.findall(r"beginbfrange(.*?)endbfrange", t, flags=re.S):
        for lo, hi, rest in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]+>)", blk):
            a, b = _hex(lo), _hex(hi)
            lens.add(len(lo) // 2)
            if rest.startswith("["):
                for k, dst in enumerate(re.findall(r"<([0-9A-Fa-f]+)>", rest)):
                    m[a + k] = u(dst)
            else:
                base = bytes.fromhex(rest[1:-1])
                for k in range(min(b - a + 1, 65536)):
                    v = int.from_bytes(base, "big") + k
                    m[a + k] = u(v.to_bytes(len(base), "big").hex())
    return m, lens or {1}


class Font:
    def __init__(self, doc, fd):
        fd = doc.get(fd) or {}
        self.subtype = str(fd.get("Subtype", ""))
        self.type0 = self.subtype == "Type0"
        enc = doc.get(fd.get("Encoding"))
        self.enc_name = str(enc) if isinstance(enc, Name) else ""
        self.ucs2 = self.type0 and bool(re.search(r"UCS2|UTF16", self.enc_name))
        self.map, self.lens = {}, {2} if self.type0 else {1}
        tu = fd.get("ToUnicode")
        if tu is not None:
            try:
                self.map, self.lens = parse_cmap(doc.stream_of(tu))
            except Exception:
                self.map = {}
        self.diff = {}
        if isinstance(enc, dict):
            code = 0
            for x in doc.get(enc.get("Differences")) or []:
                if isinstance(x, int):
                    code = x
                elif isinstance(x, Name):
                    if str(x) in AGL:
                        self.diff[code] = AGL[str(x)]
                    elif len(str(x)) == 1:
                        self.diff[code] = str(x)
                    code += 1
        # 폭(1/1000 글자 크기 단위)
        self.widths, self.dw = {}, 1000 if self.type0 else 500
        if self.type0:
            desc = doc.get((doc.get(fd.get("DescendantFonts")) or [None])[0]) or {}
            self.dw = int(doc.get(desc.get("DW", 1000)) or 1000)
            w = doc.get(desc.get("W")) or []
            i = 0
            while i < len(w):
                a = doc.get(w[i])
                b = doc.get(w[i + 1]) if i + 1 < len(w) else None
                if isinstance(b, list):
                    for k, x in enumerate(b):
                        self.widths[a + k] = float(doc.get(x) or 0)
                    i += 2
                elif i + 2 < len(w):
                    for k in range(int(a), int(b) + 1):
                        self.widths[k] = float(doc.get(w[i + 2]) or 0)
                    i += 3
                else:
                    break
        else:
            fc = int(doc.get(fd.get("FirstChar", 0)) or 0)
            for k, x in enumerate(doc.get(fd.get("Widths")) or []):
                self.widths[fc + k] = float(doc.get(x) or 0)

    def codes(self, s):
        """바이트열 → 글자 코드 목록."""
        if self.ucs2 and not self.map:
            return [int.from_bytes(s[i:i + 2], "big") for i in range(0, len(s) - 1, 2)]
        n = 2 if (self.type0 and 2 in self.lens) or self.lens == {2} else 1
        if n == 1:
            return list(s)
        return [int.from_bytes(s[i:i + 2], "big") for i in range(0, len(s) - 1, 2)]

    def char(self, code):
        if code in self.map:
            return self.map[code]
        if self.ucs2:
            return chr(code) if code < 0x110000 else ""
        if code in self.diff:
            return self.diff[code]
        if self.type0:
            return ""                         # 대응표 없는 CID 글꼴: 글자를 알 수 없음
        return bytes([code]).decode("cp1252", "replace") if code < 256 else ""

    def width(self, code):
        return self.widths.get(code, self.dw)
