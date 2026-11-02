# -*- coding: utf-8 -*-
"""[한글 파일] 공통 상수·오류·칸(Item) 정의.

한글(hwpx) 처리는 이 폴더의 파일 다섯 개로 나뉜다.
  base.py     상수·오류·칸(Item)
  package.py  zip 묶음 열기·저장(PackageMixin)
  scan.py     본문·표에서 숫자 칸 찾기(ScanMixin)
  fields.py   누름틀 만들기·값 넣기(FieldMixin)
  marks.py    빨강·노랑 표시(MarkMixin)
  grids.py    원본으로 쓰는 hwpx 표를 엑셀 시트처럼 바꾸기(table_grids)
  doc.py      위 조각을 합친 HwpxDoc
"""
import re
import itertools
import xml.etree.ElementTree as ET


HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
T = {k: "{%s}%s" % (HP, k) for k in
     ["p", "run", "t", "ctrl", "tbl", "tr", "tc", "subList", "cellAddr", "cellSpan", "fieldBegin", "fieldEnd",
      "parameters", "integerParam", "stringParam", "linesegarray", "tab", "lineBreak"]}
CLICK_FIELD_ID = "627272811"      # '%clk' (누름틀 종류 번호, 한글 문서에서 확인한 방식)
_idgen = itertools.count(1900000001)


class HwpxError(Exception):
    pass


def _register_ns(raw):
    for m in re.finditer(rb'xmlns:([A-Za-z0-9_]+)="([^"]+)"', raw[:4000]):
        try:
            ET.register_namespace(m.group(1).decode(), m.group(2).decode())
        except ValueError:
            pass


def clean_name(s, limit=40):
    s = re.sub(r"\(.*?\)", "", s or "")
    s = re.sub(r"[^0-9A-Za-z가-힣·\.]+", "", s)
    return s[:limit] or "칸"


class Item:
    """문서 속 숫자(또는 빈 칸) 하나."""
    __slots__ = ("key", "kind", "table", "row", "col", "para", "k", "raw", "value", "dec", "unit", "comma",
                 "label", "rowlab", "collab", "context", "field", "editable", "header", "_t", "_span", "empty",
                 "block", "is_total_row", "is_total_col", "is_ratio_col", "is_avg")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def public(self):
        return {k: getattr(self, k) for k in self.__slots__ if not k.startswith("_")}


