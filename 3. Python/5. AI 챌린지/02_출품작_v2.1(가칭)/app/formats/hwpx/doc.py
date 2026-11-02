# -*- coding: utf-8 -*-
"""[한글 파일] HwpxDoc — 읽기·누름틀·색 표시·저장 조각을 합친 문서 객체.

원칙
 1. 원본 파일은 열어서 읽기만 한다. 바뀐 내용은 항상 새 파일로 저장한다.
 2. 숫자 하나 = '칸(slot)' 하나. 작업본에서는 칸마다 누름틀(이름표 붙은 입력칸)을 씌워
    문서를 고쳐도 이름으로 같은 칸을 다시 찾을 수 있게 한다.
"""
from app.formats.hwpx.package import PackageMixin
from app.formats.hwpx.scan import ScanMixin
from app.formats.hwpx.fields import FieldMixin
from app.formats.hwpx.marks import MarkMixin


class HwpxDoc(PackageMixin, ScanMixin, FieldMixin, MarkMixin):
    def __init__(self, path):
        self.path = path
        self.entries = []          # [(ZipInfo, bytes)]
        self.sections = []         # [(name, root, start_tag, decl)]
        self.header_name = None
        self.header_raw = None
        self.items = []
        self.blocks = []
        self.tables = []           # 표 정보 [{ti, title, grid, nrow, ncol, head_rows, label_col}]
        self.warnings = []
        self._parent = {}
        self._load()
        self._scan()

