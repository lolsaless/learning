# -*- coding: utf-8 -*-
"""[PDF ①] 낱말 읽기: PDF 객체(숫자·이름·글자·배열·사전·참조)를 파이썬 값으로 바꾼다."""
import re

WS = b" \t\r\n\x0c\x00"
DELIM = b"()<>[]{}/%"


class Name(str):
    """PDF 이름(/Type 등). 글자와 구별하려고 따로 둔다."""


class Ref:
    __slots__ = ("num", "gen")

    def __init__(self, num, gen):
        self.num, self.gen = num, gen

    def __repr__(self):
        return f"Ref({self.num})"


class Keyword(str):
    pass


NUM = re.compile(rb"[+-]?(\d+\.?\d*|\.\d+)")


def skip_ws(d, i):
    n = len(d)
    while i < n:
        c = d[i]
        if c in WS:
            i += 1
        elif c == 37:                       # % 주석
            while i < n and d[i] not in b"\r\n":
                i += 1
        else:
            break
    return i


def _literal(d, i):
    """( … ) 글자. 괄호 짝·탈출 문자 처리."""
    out = bytearray()
    depth = 1
    i += 1
    n = len(d)
    while i < n:
        c = d[i]
        if c == 92:                          # \
            i += 1
            if i >= n:
                break
            e = d[i]
            m = {110: 10, 114: 13, 116: 9, 98: 8, 102: 12, 40: 40, 41: 41, 92: 92}
            if e in m:
                out.append(m[e])
            elif 48 <= e <= 55:
                j = i
                while j < n and j < i + 3 and 48 <= d[j] <= 55:
                    j += 1
                out.append(int(d[i:j], 8) & 255)
                i = j - 1
            elif e in (13, 10):
                if e == 13 and i + 1 < n and d[i + 1] == 10:
                    i += 1
            else:
                out.append(e)
        elif c == 40:
            depth += 1
            out.append(c)
        elif c == 41:
            depth -= 1
            if depth == 0:
                return bytes(out), i + 1
            out.append(c)
        else:
            out.append(c)
        i += 1
    return bytes(out), i


def _name(d, i):
    j = i + 1
    n = len(d)
    while j < n and d[j] not in WS and d[j] not in DELIM:
        j += 1
    raw = d[i + 1:j]
    if b"#" in raw:
        raw = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), raw)
    return Name(raw.decode("latin-1")), j


def parse(d, i):
    """i 위치의 값 하나를 읽어 (값, 다음 위치)를 돌려준다."""
    i = skip_ws(d, i)
    if i >= len(d):
        return None, i
    c = d[i]
    if c == 47:
        return _name(d, i)
    if c == 40:
        return _literal(d, i)
    if c == 60:
        if d[i + 1:i + 2] == b"<":
            out = {}
            i += 2
            while True:
                i = skip_ws(d, i)
                if d[i:i + 2] == b">>" or i >= len(d):
                    return out, i + 2
                k, i = parse(d, i)
                v, i = parse(d, i)
                if isinstance(k, Name):
                    out[str(k)] = v
        j = d.find(b">", i)
        hx = re.sub(rb"\s", b"", d[i + 1:j])
        if len(hx) % 2:
            hx += b"0"
        try:
            return bytes.fromhex(hx.decode("latin-1")), j + 1
        except ValueError:
            return b"", j + 1
    if c == 91:
        out = []
        i += 1
        while True:
            i = skip_ws(d, i)
            if i >= len(d) or d[i] == 93:
                return out, i + 1
            v, i = parse(d, i)
            if isinstance(v, Keyword) and v == "R" and len(out) >= 2 and isinstance(out[-1], int) and isinstance(out[-2], int):
                g, num = out.pop(), out.pop()
                out.append(Ref(num, g))
            else:
                out.append(v)
    m = NUM.match(d, i)
    if m and (m.end() >= len(d) or d[m.end()] in WS or d[m.end()] in DELIM):
        s = m.group(0)
        v = float(s) if b"." in s else int(s)
        j = m.end()
        if isinstance(v, int):                      # 참조 n g R ?
            k = skip_ws(d, j)
            m2 = re.match(rb"(\d+)\s+R(?![A-Za-z])", d[k:k + 24])
            if m2:
                return Ref(v, int(m2.group(1))), k + m2.end()
        return v, j
    j = i
    while j < len(d) and d[j] not in WS and d[j] not in DELIM:
        j += 1
    if j == i:
        return None, i + 1
    w = d[i:j].decode("latin-1")
    if w == "true":
        return True, j
    if w == "false":
        return False, j
    if w == "null":
        return None, j
    return Keyword(w), j
