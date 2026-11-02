# -*- coding: utf-8 -*-
"""[가상자료 ⑥] 문서 모형(blocks)을 한글(hwpx)·ODT 파일로 그린다.

block 종류
  {"kind": "title" | "center" | "head" | "body" | "note" | "text" | "blank", "text": 글자}
  {"kind": "p", "style": "body"|"head"|"note"|"text", "text": 글자}     ← 오류를 심을 수 있는 문단
  {"kind": "table", "rows": [[글자…]…], "widths": [비율…], "left": (왼쪽 정렬 열…)}
"""
from app.formats.hwpx_build import HwpxBuilder
from app.formats.odt import OdtBuilder
from app.formats.docx_write import DocxWriter
from app.formats.pdf_write import PdfWriter


def _text_of(b):
    return b.get("text", "")


def to_hwpx(blocks, path, meta=""):
    h = HwpxBuilder(meta)
    for b in blocks:
        k = b["kind"]
        if k == "p":
            k = b.get("style", "body")
        if k == "title":
            h.title(_text_of(b))
        elif k == "head":
            h.heading(_text_of(b))
        elif k == "body":
            h.body(_text_of(b))
        elif k in ("text", "center"):
            h.text(_text_of(b))
        elif k == "note":
            h.note(_text_of(b))
        elif k == "blank":
            h.blank()
        elif k == "table":
            ncol = max(len(r) for r in b["rows"])
            h.table(b["rows"], widths=b.get("widths") or [3] + [2] * (ncol - 1), left_cols=tuple(b.get("left", ())))
    return h.save(path)


def to_odt(blocks, path, meta=""):
    o = OdtBuilder(meta)
    for b in blocks:
        k = b["kind"]
        if k == "p":
            k = b.get("style", "body")
        if k == "title":
            o.title(_text_of(b))
        elif k == "center":
            o.center(_text_of(b))
        elif k == "head":
            o.heading(_text_of(b))
        elif k in ("body", "text"):
            o.body(_text_of(b))
        elif k == "note":
            o.note(_text_of(b))
        elif k == "blank":
            o.blank()
        elif k == "table":
            o.table([[c.get("t", "") if isinstance(c, dict) else c for c in r] for r in b["rows"]])
    return o.save(path)


def _plain(rows):
    return [[c.get("t", "") if isinstance(c, dict) else c for c in r] for r in rows]


def _simple(builder, blocks):
    for b in blocks:
        k = b["kind"]
        if k == "p":
            k = b.get("style", "body")
        t = _text_of(b)
        if k == "title":
            builder.title(t)
        elif k == "head":
            builder.heading(t)
        elif k in ("body", "text", "center"):
            builder.para(t)
        elif k == "note":
            builder.note(t)
        elif k == "blank":
            builder.blank()
        elif k == "table":
            if isinstance(builder, PdfWriter):
                builder.table(_plain(b["rows"]), widths=b.get("widths"))
            else:
                builder.table(_plain(b["rows"]))
    return builder


def to_docx(blocks, path, meta=""):
    return _simple(DocxWriter(meta), blocks).save(path)


def to_pdf(blocks, path, meta=""):
    return _simple(PdfWriter(meta), blocks).save(path)


def to_md(blocks, path, meta=""):
    """마크다운(생성형 AI 가 흔히 내놓는 꼴): # 제목, 문단, | 표 |"""
    out = []
    for b in blocks:
        k = b["kind"]
        if k == "p":
            k = b.get("style", "body")
        t = _text_of(b)
        if k == "title":
            out.append(f"# {t}\n")
        elif k == "head":
            out.append(f"## {t.lstrip('□ ').strip()}\n")
        elif k in ("body", "text", "center", "note"):
            out.append(t + "\n")
        elif k == "table":
            rows = _plain(b["rows"])
            out.append("| " + " | ".join(rows[0]) + " |")
            out.append("|" + "|".join("---" for _ in rows[0]) + "|")
            for r in rows[1:]:
                out.append("| " + " | ".join(r) + " |")
            out.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return path


WRITERS = {"hwpx": to_hwpx, "odt": to_odt, "docx": to_docx, "pdf": to_pdf, "md": to_md}


def save(blocks, path_no_ext, fmt, meta=""):
    """fmt: "hwpx" | "odt" | "docx" | "pdf" | "md" | "both"(hwpx+odt) → 만든 파일 경로 목록"""
    fmts = ["hwpx", "odt"] if fmt == "both" else [fmt]
    return [WRITERS[f](blocks, f"{path_no_ext}.{f}", meta) for f in fmts]
