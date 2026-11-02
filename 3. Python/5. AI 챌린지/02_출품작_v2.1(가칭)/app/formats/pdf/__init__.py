# -*- coding: utf-8 -*-
"""[파일 형식] PDF 읽기(글자 PDF) → 문단·표 블록. 표준 라이브러리만.

    read_pdf(경로) → {"blocks": [...], "warnings": [...]}

  lexer.py    ① PDF 낱말·객체
  document.py ② 객체 찾기·압축 풀기·쪽 목록
  fonts.py    ③ 글자 코드 → 글자(ToUnicode·UCS-2·WinAnsi), 글자 폭
  content.py  ④ 내용 스트림 → 글자 조각 위치
  layout.py   ⑤ 조각 → 줄 → 표·문단
한계: 스캔(그림) PDF 는 글자가 없어 읽지 못한다(OCR 없음). 표는 칸 정렬로 복원하므로 합친 칸은 나뉠 수 있다.
"""
from app.formats.pdf.document import PdfDoc, PdfError
from app.formats.pdf.content import Extractor
from app.formats.pdf.layout import lines_of, blocks_of


def merge_page_tables(blocks):
    """쪽이 바뀌며 끊긴 표를 하나로 잇는다: 쪽 끝 표 다음 쪽 첫 블록이 같은 열 수의 표면 이어 붙임
    (다음 쪽에서 머리글 행이 되풀이되면 그 행은 뺀다)."""
    def as_para(t):
        return {"type": "p", "text": " ".join(c["text"] for c in t["cells"]), "page": t.get("page")}
    out = []
    for b in blocks:
        prev = out[-1] if out else None
        if b.get("cont_only") and not (prev and prev["type"] == "table" and b.get("page") == prev.get("page", 0) + 1
                                       and b["ncol"] == prev["ncol"] and not prev.get("header_only")):
            out.append(as_para(b))
            continue
        if prev and prev.get("header_only") and not (b["type"] == "table" and b.get("page") == prev.get("page", 0) + 1
                                                     and b["ncol"] == prev["ncol"]):
            out[-1] = {"type": "p", "text": " ".join(c["text"] for c in prev["cells"]), "page": prev.get("page")}
            prev = out[-1]
        if prev and b["type"] == "table" and prev["type"] == "table" and b.get("page") == prev.get("page", 0) + 1 \
                and b["ncol"] == prev["ncol"]:
            first = {c["c"]: c["text"] for c in prev["cells"] if c["r"] == 0}
            nfirst = {c["c"]: c["text"] for c in b["cells"] if c["r"] == 0}
            skip = 1 if first == nfirst else 0
            base = prev["nrow"]
            for c in b["cells"]:
                if c["r"] >= skip:
                    prev["cells"].append(dict(c, r=c["r"] - skip + base))
            prev["nrow"] = base + b["nrow"] - skip
            prev["page"] = b["page"]
            prev.pop("header_only", None)
            prev.pop("cont_only", None)
            continue
        out.append(b)
    if out and out[-1].get("header_only"):
        b = out.pop()
        out.append({"type": "p", "text": " ".join(c["text"] for c in b["cells"]), "page": b.get("page")})
    return out


def read_pdf(path, max_pages=300):
    doc = PdfDoc(path)
    blocks, warnings = [], []
    pages = doc.pages()
    if len(pages) > max_pages:
        warnings.append(f"쪽이 많아 앞 {max_pages}쪽만 읽음")
    nchars = 0
    for pno, (page, res) in enumerate(pages[:max_pages]):
        ex = Extractor(doc)
        ex.run(doc.contents(page), res)
        lines = lines_of(ex.frags, ex.vlines)
        nchars += sum(len(f["text"]) for f in ex.frags)
        bl = blocks_of(lines)
        for b in bl:
            b["page"] = pno + 1
        blocks.extend(bl)
    blocks = merge_page_tables(blocks)
    if nchars == 0:
        warnings.append("글자가 없는 PDF 입니다(스캔 그림일 수 있음 — 글자 인식 OCR 은 지원하지 않음)")
    unknown = sum(1 for b in blocks if b["type"] == "p" and "�" in b["text"])
    if unknown:
        warnings.append("일부 글꼴의 글자 대응표가 없어 깨진 글자가 있습니다")
    return {"blocks": blocks, "warnings": warnings, "pages": len(pages)}


__all__ = ["read_pdf", "PdfError"]
