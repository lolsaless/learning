# -*- coding: utf-8 -*-
"""[한글 파일] 원본으로 쓰는 hwpx(팀 제출본)의 표를 엑셀 시트처럼 바꾼다."""


def table_grids(doc):
    """원본으로 쓰는 hwpx(팀 제출본)의 표를 엑셀 시트처럼 [{(r,c): 값}] 로 돌려준다."""
    grids = []
    for tb in doc.tables:
        cells = {}
        texts = {}
        for key in tb["cells"]:
            it = doc.item(key)
            if it and it.value is not None and it.k == 0:
                cells[(it.row, it.col)] = (it.value, it.dec)
        for b in doc.blocks:
            if b["type"] == "table" and b["ti"] == tb["ti"]:
                for row in b["rows"]:
                    for c in row:
                        texts[(c["r"], c["c"])] = "".join(p["text"] for p in c["pieces"])
        grids.append({"name": f"표{tb['ti'] + 1}", "title": tb["title"], "cells": cells, "texts": texts,
                      "nrow": tb["nrow"], "ncol": tb["ncol"]})
    body = {}
    btexts = {}
    for it in doc.items:
        if it.kind == "para" and it.value is not None:
            body[(it.para, it.k)] = (it.value, it.dec)
            btexts[(it.para, it.k)] = it.context[:60]
    if body:
        grids.append({"name": "본문", "title": "본문 숫자", "cells": body, "texts": btexts,
                      "nrow": max(r for r, _ in body) + 1, "ncol": max(c for _, c in body) + 1})
    return grids

