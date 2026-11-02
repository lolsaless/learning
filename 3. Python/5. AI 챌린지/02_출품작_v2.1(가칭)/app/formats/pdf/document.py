# -*- coding: utf-8 -*-
"""[PDF ②] 문서 구조: 모든 객체 찾기(객체 스트림 포함) → 압축 풀기 → 쪽 목록·쪽마다 자원·내용."""
import re
import zlib
import base64

from app.formats.pdf.lexer import parse, Ref, Name, skip_ws

OBJ = re.compile(rb"(?<![0-9])(\d{1,7})\s+(\d{1,5})\s+obj\b")


class PdfError(Exception):
    pass


def _lzw(data):
    out, table = bytearray(), [bytes([i]) for i in range(256)] + [None, None]
    bits, buf, nbits, prev = 9, 0, 0, None
    for byte in data:
        buf = (buf << 8) | byte
        nbits += 8
        while nbits >= bits:
            nbits -= bits
            code = (buf >> nbits) & ((1 << bits) - 1)
            if code == 256:
                table = table[:258]
                bits, prev = 9, None
                continue
            if code == 257:
                return bytes(out)
            if prev is None:
                entry = table[code]
            else:
                entry = table[code] if code < len(table) and table[code] is not None else prev + prev[:1]
                table.append(prev + entry[:1])
            out += entry
            prev = entry
            if len(table) + 1 >= (1 << bits) and bits < 12:
                bits += 1
    return bytes(out)


def _png_unpredict(data, cols):
    row = cols + 1
    out, prev = bytearray(), bytearray(cols)
    for k in range(0, len(data) // row * row, row):
        ft, line = data[k], bytearray(data[k + 1:k + row])
        for i in range(cols):
            a = line[i - 1] if i else 0
            if ft == 1:
                line[i] = (line[i] + a) & 255
            elif ft == 2:
                line[i] = (line[i] + prev[i]) & 255
            elif ft == 3:
                line[i] = (line[i] + (a + prev[i]) // 2) & 255
            elif ft == 4:
                b, c = prev[i], prev[i - 1] if i else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += line
        prev = line
    return bytes(out)


class PdfDoc:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = f.read()
        if not self.data.lstrip()[:5].startswith(b"%PDF"):
            raise PdfError("PDF 파일이 아닙니다")
        self.objs = {}           # 번호 → (값, 스트림 원본 또는 None)
        self._index()
        self.trailer = self._trailer()
        if "Encrypt" in self.trailer:
            raise PdfError("암호화된 PDF 입니다(열기 암호·사용 제한). 암호를 풀어 다시 저장해 주세요")

    # ── 객체 ──
    def _index(self):
        d = self.data
        for m in OBJ.finditer(d):
            num = int(m.group(1))
            try:
                val, j = parse(d, m.end())
            except (IndexError, ValueError, RecursionError):
                continue
            stream = None
            j2 = skip_ws(d, j)
            if isinstance(val, dict) and d[j2:j2 + 6] == b"stream":
                k = j2 + 6
                if d[k:k + 2] == b"\r\n":
                    k += 2
                elif d[k:k + 1] in (b"\n", b"\r"):
                    k += 1
                ln = val.get("Length")
                end = None
                if isinstance(ln, int) and d[k + ln:k + ln + 20].lstrip().startswith(b"endstream"):
                    end = k + ln
                if end is None:
                    end = d.find(b"endstream", k)
                    end = end if end >= 0 else len(d)
                    while end > k and d[end - 1] in b"\r\n":
                        end -= 1
                stream = d[k:end]
            self.objs[num] = (val, stream)
        for num, (val, st) in list(self.objs.items()):
            if isinstance(val, dict) and val.get("Type") == "ObjStm" and st is not None:
                try:
                    raw = self.decode(val, st)
                    n, first = int(val.get("N", 0)), int(val.get("First", 0))
                    head = raw[:first].split()
                    for k in range(n):
                        onum, off = int(head[2 * k]), int(head[2 * k + 1])
                        if onum not in self.objs or self.objs[onum][0] is None:
                            v, _ = parse(raw, first + off)
                            self.objs[onum] = (v, None)
                except (ValueError, IndexError, zlib.error):
                    continue

    def _trailer(self):
        tr = {}
        for m in re.finditer(rb"trailer\s*<<", self.data):
            v, _ = parse(self.data, m.end() - 2)
            if isinstance(v, dict):
                tr.update(v)
        for val, _ in self.objs.values():
            if isinstance(val, dict) and val.get("Type") == "XRef":
                for k in ("Root", "Encrypt", "Info"):
                    if k in val:
                        tr.setdefault(k, val[k])
        return tr

    def get(self, v, depth=0):
        while isinstance(v, Ref) and depth < 32:
            v = self.objs.get(v.num, (None, None))[0]
            depth += 1
        return v

    def stream_of(self, v):
        if isinstance(v, Ref):
            val, st = self.objs.get(v.num, (None, None))
            return self.decode(val, st) if st is not None else b""
        return b""

    def decode(self, d, raw):
        filters = d.get("Filter") if isinstance(d, dict) else None
        filters = filters if isinstance(filters, list) else [filters] if filters else []
        parms = d.get("DecodeParms") if isinstance(d, dict) else None
        parms = parms if isinstance(parms, list) else [parms] * len(filters)
        data = raw
        for f, p in zip(filters, parms):
            f = str(self.get(f))
            p = self.get(p) or {}
            if f in ("FlateDecode", "Fl"):
                try:
                    data = zlib.decompress(data)
                except zlib.error:
                    data = zlib.decompressobj().decompress(data)
            elif f in ("ASCIIHexDecode", "AHx"):
                data = bytes.fromhex(re.sub(rb"[^0-9A-Fa-f]", b"", data.split(b">")[0]).decode() + "")
            elif f in ("ASCII85Decode", "A85"):
                s = data.strip()
                s = s[2:] if s.startswith(b"<~") else s
                s = s.split(b"~>")[0]
                data = base64.a85decode(s, adobe=False, ignorechars=b" \t\r\n")
            elif f in ("LZWDecode", "LZW"):
                data = _lzw(data)
            else:
                return b""            # 그림(DCT·JPX 등)은 글자와 무관
            if isinstance(p, dict) and int(p.get("Predictor", 1) or 1) >= 10:
                data = _png_unpredict(data, int(p.get("Columns", 1)) * int(p.get("Colors", 1) or 1))
        return data

    # ── 쪽 ──
    def pages(self):
        root = self.get(self.trailer.get("Root"))
        if not isinstance(root, dict):
            cats = [v for v, _ in self.objs.values() if isinstance(v, dict) and v.get("Type") == "Catalog"]
            root = cats[-1] if cats else {}
        out = []

        def walk(node, inherited, depth=0):
            node = self.get(node)
            if not isinstance(node, dict) or depth > 40:
                return
            res = node.get("Resources", inherited)
            if node.get("Type") == "Pages" or "Kids" in node:
                for k in self.get(node.get("Kids")) or []:
                    walk(k, res, depth + 1)
            else:
                out.append((node, self.get(res) or {}))
        walk(root.get("Pages"), {})
        if not out:
            out = [(v, self.get(v.get("Resources")) or {}) for v, _ in self.objs.values()
                   if isinstance(v, dict) and v.get("Type") == "Page"]
        return out

    def contents(self, page):
        """쪽 내용 스트림(여러 개면 이어 붙임)."""
        c = page.get("Contents")
        if isinstance(c, Ref):
            val, st = self.objs.get(c.num, (None, None))
            if st is not None:
                return self.decode(val, st)
            c = val
        if isinstance(c, list):
            return b"\n".join(self.stream_of(r) for r in c)
        return b""


__all__ = ["PdfDoc", "PdfError", "Name", "Ref"]
