# -*- coding: utf-8 -*-
"""[파일 형식] 읽기 전용 문서(TextDoc): hwp·docx·odt·pdf·txt·md·html 을 HwpxDoc 과 같은 모양으로.

검증 엔진은 문서의 items(숫자 칸)·blocks(화면 그리기)·tables 만 본다. 그래서 어느 형식이든
'문단·표 블록'으로 바꾸면 hwpx 와 똑같이 대조·재계산할 수 있다. 칸 찾기 규칙은 hwpx 와 같은 코드(ScanMixin)를 쓴다.
차이: 원본 파일을 고칠 수 없으므로 모든 칸이 editable=False(고치기·입력하기는 hwpx 작업본에서만).
"""
from app.common import numbers as N
from app.formats.hwpx.scan import ScanMixin


class TextDoc(ScanMixin):
    read_only = True

    def __init__(self, blocks, path="", kind="", warnings=None):
        self.path = path
        self.kind = kind
        self.warnings = list(warnings or [])
        self.items, self.blocks, self.tables = [], [], []
        self._build(blocks)

    def _build(self, src):
        pidx = 0
        last_head = ""
        texts = []
        for b in src:
            if b["type"] == "p":
                for line in [x for x in b["text"].split("\n") if x.strip()] or []:
                    self._emit_para([(line, None, None)], pidx)
                    texts.append(line)
                    if line.strip().startswith("□"):
                        last_head = line.strip()
                    pidx += 1
            elif b["type"] == "table" and b.get("cells"):
                cells = [{"r": c["r"], "c": c["c"], "rs": c.get("rs", 1), "cs": c.get("cs", 1), "text": c["text"] or "",
                          "pieces": [(c["text"] or "", None, None)], "tc": None, "head": False, "p": None}
                         for c in b["cells"]]
                self._scan_cells(cells, len(self.tables), last_head)
        for it in self.items:
            it.editable = False
            if isinstance(it._t, tuple):
                it._t = None
        self.year = N.guess_year(texts + [it.context or "" for it in self.items])

    def item(self, key):
        for it in self.items:
            if it.key == key:
                return it
        return None

    def plain_texts(self):
        return [b["text"] for b in self.blocks if b["type"] == "p"]

    def make_fields(self):
        return 0
