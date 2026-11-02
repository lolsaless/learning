# -*- coding: utf-8 -*-
"""[가상자료 ②] 자료 모형: 요구자료 표 하나(DataTable)와 숫자 표시 규칙.

DataTable 하나가 '원본 엑셀'과 '팀 답변서·취합본의 표'를 함께 만든다.
  - values 는 반올림 전 '진짜 값'(원본에 그대로 들어감)
  - decs 는 문서에 표시할 소수 자릿수
  - total=True 면 마지막 행을 합계 행으로 만든다(값 = 각 행의 합)
  - ratio=(비율 열, 분자 열, 분모 열) 이면 비율 열 = 분자 ÷ 분모 × 100
  - src_scale[열] = 1000 이면 원본은 원 단위, 문서는 천원 단위
"""
from decimal import Decimal, ROUND_HALF_UP


def rhalf(x, d):
    """한국 문서 관행 반올림(사사오입)."""
    return float(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def fmtd(x, d, comma=True):
    v = rhalf(x, d)
    return f"{v:,.{d}f}" if comma else f"{v:.{d}f}"


class DataTable:
    def __init__(self, key, team, title, row_head, rows, cols, values, decs, unit="", note="",
                 total=False, ratio=None, src_scale=None, src_cols=None, src_rows=None, src_title=None,
                 src_file=None, src_sheet=None, claim=None, allow_transpose=True, monthly=False, sheet_unit=""):
        self.key = key
        self.team = team
        self.title = title                  # 요구자료 제목(□ 요구자료 n. …)
        self.row_head = row_head            # 표 왼쪽 위 머리글
        self.rows = list(rows)              # 문서의 행 이름
        self.cols = list(cols)              # 문서의 열 이름(값 열만)
        self.values = values                # {(행 이름, 열 이름): 값}
        self.decs = dict(decs)              # {열 이름: 소수 자릿수}
        self.unit = unit                    # 문서에 적는 단위 문구
        self.note = note
        self.total = total
        self.ratio = ratio                  # (비율 열, 분자 열, 분모 열)
        self.src_scale = src_scale or {}    # {열 이름: 배율}  원본 값 = 문서 값 × 배율
        self.src_cols = src_cols or {c: c for c in cols}   # 원본 머리글(다른 이름)
        self.src_rows = src_rows or {r: r for r in rows}   # 원본 행 이름(코드 등)
        self.src_title = src_title or title
        self.src_file = src_file
        self.src_sheet = src_sheet or "자료"
        self.claim = claim                  # {"a": 열, "b": 열, "u": 단위, "what": 문장 주어}
        self.allow_transpose = allow_transpose
        self.monthly = monthly
        self.sheet_unit = sheet_unit
        if total:
            self._add_total()
        if ratio:
            self._fill_ratio()

    TOTAL = "합계"

    def body_rows(self):
        return [r for r in self.rows if r != self.TOTAL]

    def _add_total(self):
        for c in self.cols:
            if self.ratio and c == self.ratio[0]:
                continue
            self.values[(self.TOTAL, c)] = sum(self.values[(r, c)] for r in self.body_rows())
        if self.TOTAL not in self.rows:
            self.rows.append(self.TOTAL)

    def _fill_ratio(self):
        rc, a, b = self.ratio
        for r in self.rows:
            den = self.values[(r, b)]
            self.values[(r, rc)] = self.values[(r, a)] / den * 100 if den else 0.0

    # ── 문서 표시 ──
    def dec(self, r, c):
        """칸의 표시 자릿수. 행마다 자릿수가 다르면 row_decs 를 쓴다(예: 평균 행 1자리, 일수 행 0자리)."""
        rd = getattr(self, "row_decs", None)
        if rd and r in rd:
            return rd[r]
        return self.decs.get(c, 0)

    def cell_text(self, r, c):
        return fmtd(self.values[(r, c)], self.dec(r, c))

    def doc_rows(self):
        """팀 답변서·취합본에 넣을 표(글자). 첫 행은 머리글, 합계 행은 굵게."""
        out = [[self.row_head] + self.cols]
        for r in self.rows:
            lab = {"t": r, "total": True} if r == self.TOTAL else r
            out.append([lab] + [self.cell_text(r, c) for c in self.cols])
        return out

    def displayed(self, r, c):
        return rhalf(self.values[(r, c)], self.dec(r, c))

    def consistent(self):
        """표시된 값으로 다시 계산해도 합계·비율이 맞는지(정상 표가 오류로 보이지 않게)."""
        from app.common import numbers as N
        if self.ratio:
            rc, a, b = self.ratio
            for r in self.rows:
                den = self.displayed(r, b)
                if den and not N.close(self.displayed(r, a) / den * 100, self.displayed(r, rc), self.dec(r, rc)):
                    return False
        if self.total:
            for c in self.cols:
                if self.ratio and c == self.ratio[0]:
                    continue
                s = sum(self.displayed(r, c) for r in self.body_rows())
                d = self.dec(self.TOTAL, c)
                if abs(s - self.displayed(self.TOTAL, c)) > 0.5 * len(self.body_rows()) * 10 ** -d + 1e-9:
                    return False
        return True
