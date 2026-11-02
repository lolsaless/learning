# -*- coding: utf-8 -*-
"""[엑셀 파일] 칸 주소 계산(A1 ↔ 행·열)과 읽은 내용을 담는 그릇(Cell·Sheet·Workbook)."""
import re

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PNS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

DATE_FMT_IDS = set(range(14, 23)) | {27, 30, 36, 45, 46, 47, 50, 57}


def col2idx(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def idx2col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def ref(r, c):
    return f"{idx2col(c)}{r + 1}"


def parse_ref(a1):
    m = re.match(r"^\$?([A-Z]+)\$?(\d+)$", a1.strip().upper())
    if not m:
        return None
    return int(m.group(2)) - 1, col2idx(m.group(1))


class Cell:
    __slots__ = ("v", "kind", "text", "f")

    def __init__(self, v, kind, text, f=None):
        self.v = v          # float(숫자) | str | bool
        self.kind = kind    # 'n' 숫자, 's' 글자, 'd' 날짜, 'b' 참거짓, 'e' 오류
        self.text = text    # 화면 표시용 글자
        self.f = f          # 수식(있으면)


class Sheet:
    def __init__(self, name, hidden=False):
        self.name = name
        self.hidden = hidden
        self.cells = {}
        self.maxr = -1
        self.maxc = -1
        self.truncated = False

    def get(self, r, c):
        return self.cells.get((r, c))


class Workbook:
    def __init__(self):
        self.sheets = []
        self.warnings = []

    def sheet(self, name):
        for s in self.sheets:
            if s.name == name:
                return s
        return None



def _num_text(x):
    if x.is_integer() and abs(x) < 1e15:
        return f"{int(x):,}"
    s = f"{x:.10f}".rstrip("0").rstrip(".")
    return s
