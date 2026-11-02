# -*- coding: utf-8 -*-
"""[PDF ④] 내용 스트림 따라가기: 글자 조각마다 위치(x 시작·끝, y)와 크기를 구한다."""
import math

from app.formats.pdf.lexer import parse, Keyword
from app.formats.pdf.fonts import Font


def mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return [a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F]


def tokens(data):
    """(피연산자 목록, 연산자) 를 차례로 낸다. 인라인 그림(BI…EI)은 건너뛴다."""
    i, n, ops = 0, len(data), []
    while i < n:
        try:
            v, j = parse(data, i)
        except (IndexError, ValueError, RecursionError):
            i += 1
            continue
        if j <= i:
            i += 1
            continue
        i = j
        if isinstance(v, Keyword):
            if v == "BI":
                k = data.find(b"EI", i)
                i = k + 2 if k >= 0 else n
                ops = []
                continue
            yield ops, str(v)
            ops = []
        else:
            ops.append(v)


class Extractor:
    def __init__(self, doc):
        self.doc = doc
        self.fonts = {}
        self.frags = []
        self.vlines = []        # 세로 선(표 테두리): (x, y아래, y위) — 붙어 있는 칸을 나누는 데 쓴다

    def _vert(self, x0, y0, x1, y1, ctm):
        a = mul([1, 0, 0, 1, x0, y0], ctm)
        b = mul([1, 0, 0, 1, x1, y1], ctm)
        if abs(a[4] - b[4]) <= 1.0 and abs(a[5] - b[5]) >= 4:
            self.vlines.append(((a[4] + b[4]) / 2, min(a[5], b[5]), max(a[5], b[5])))

    def font(self, res, name):
        fr = self.doc.get((self.doc.get(res.get("Font")) or {}).get(name))
        key = id(fr)
        if key not in self.fonts:
            self.fonts[key] = Font(self.doc, fr) if fr is not None else None
        return self.fonts[key]

    def run(self, data, res, ctm=None, depth=0):
        ctm = ctm or [1, 0, 0, 1, 0, 0]
        stack = []
        tm = tlm = [1, 0, 0, 1, 0, 0]
        st = {"Tc": 0.0, "Tw": 0.0, "Th": 1.0, "TL": 0.0, "Ts": 0.0, "size": 10.0, "font": None}
        path, cur = [], None
        for ops, op in tokens(data):
            try:
                if op == "m" and len(ops) == 2:
                    cur = (float(ops[0]), float(ops[1]))
                elif op == "l" and len(ops) == 2 and cur:
                    nxt = (float(ops[0]), float(ops[1]))
                    path.append((cur, nxt, list(ctm)))
                    cur = nxt
                elif op == "re" and len(ops) == 4:
                    x, y, w, h = (float(v) for v in ops)
                    if abs(w) <= 2.0:                                   # 가는 채운 사각형 = 세로 선
                        path.append(((x + w / 2, y), (x + w / 2, y + h), list(ctm)))
                    elif abs(h) > 2.0:                                  # 칸 상자: 왼쪽·오른쪽 변
                        path.append(((x, y), (x, y + h), list(ctm)))
                        path.append(((x + w, y), (x + w, y + h), list(ctm)))
                elif op in ("S", "s", "f", "F", "f*", "B", "B*", "b", "b*"):
                    for (x0, y0), (x1, y1), m in path:
                        self._vert(x0, y0, x1, y1, m)
                    path, cur = [], None
                elif op == "n":
                    path, cur = [], None
                elif op == "q":
                    stack.append((list(ctm), dict(st)))
                elif op == "Q" and stack:
                    ctm, st = stack.pop()
                elif op == "cm" and len(ops) == 6:
                    ctm = mul([float(x) for x in ops], ctm)
                elif op == "BT":
                    tm = tlm = [1, 0, 0, 1, 0, 0]
                elif op == "Tf" and len(ops) == 2:
                    st["font"] = self.font(res, str(ops[0]))
                    st["size"] = float(ops[1])
                elif op in ("Tc", "Tw", "TL", "Ts") and ops:
                    st[op] = float(ops[0])
                elif op == "Tz" and ops:
                    st["Th"] = float(ops[0]) / 100
                elif op in ("Td", "TD") and len(ops) == 2:
                    tx, ty = float(ops[0]), float(ops[1])
                    if op == "TD":
                        st["TL"] = -ty
                    tlm = mul([1, 0, 0, 1, tx, ty], tlm)
                    tm = tlm
                elif op == "Tm" and len(ops) == 6:
                    tlm = tm = [float(x) for x in ops]
                elif op == "T*":
                    tlm = mul([1, 0, 0, 1, 0, -st["TL"]], tlm)
                    tm = tlm
                elif op in ("Tj", "'", '"', "TJ"):
                    if op in ("'", '"'):
                        if op == '"' and len(ops) == 3:
                            st["Tw"], st["Tc"] = float(ops[0]), float(ops[1])
                        tlm = mul([1, 0, 0, 1, 0, -st["TL"]], tlm)
                        tm = tlm
                    arr = ops[-1] if op == "TJ" and ops and isinstance(ops[-1], list) else [ops[-1]] if ops else []
                    for x in arr:
                        if isinstance(x, (int, float)):
                            tm = mul([1, 0, 0, 1, -float(x) / 1000 * st["size"] * st["Th"], 0], tm)
                        elif isinstance(x, bytes):
                            tm = self.show(x, st, tm, ctm)
                elif op == "Do" and ops and depth < 4:
                    xo = self.doc.get((self.doc.get(res.get("XObject")) or {}).get(str(ops[0])))
                    ref = (self.doc.get(res.get("XObject")) or {}).get(str(ops[0]))
                    if isinstance(xo, dict) and xo.get("Subtype") == "Form":
                        mtx = [float(v) for v in (self.doc.get(xo.get("Matrix")) or [1, 0, 0, 1, 0, 0])]
                        sub = self.doc.get(xo.get("Resources")) or res
                        self.run(self.doc.stream_of(ref), sub, mul(mtx, ctm), depth + 1)
            except (TypeError, ValueError, ZeroDivisionError, IndexError):
                continue

    def show(self, s, st, tm, ctm):
        f = st["font"]
        if f is None:
            return tm
        trm = mul(tm, ctm)
        x0, y0 = trm[4], trm[5]
        scale = math.hypot(trm[2], trm[3]) or 1.0
        size = st["size"] * scale
        text = []
        adv = 0.0
        for code in f.codes(s):
            ch = f.char(code)
            w = f.width(code) / 1000.0
            tx = (w * st["size"] + st["Tc"] + (st["Tw"] if code == 32 and not f.type0 else 0)) * st["Th"]
            adv += tx
            text.append(ch)
        tm = mul([1, 0, 0, 1, adv, 0], tm)
        end = mul(tm, ctm)
        t = "".join(text)
        if t.strip():
            self.frags.append({"x0": min(x0, end[4]), "x1": max(x0, end[4]), "y": y0, "size": size, "text": t})
        return tm
