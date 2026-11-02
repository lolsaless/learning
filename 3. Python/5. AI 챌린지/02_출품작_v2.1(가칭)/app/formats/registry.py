# -*- coding: utf-8 -*-
"""[파일 형식] 형식 등록부: 확장자 → 읽기 함수. 새 형식은 FORMATS 에 한 줄 추가하면 된다.

    read_source(경로)  → ("sheet", Workbook) | ("doc", TextDoc|HwpxDoc)   ← 원본(대조할 자료)으로 읽기
    open_target(경로)  → HwpxDoc(고칠 수 있음) | TextDoc(읽기 전용)      ← 검증 대상 문서로 열기
    describe()         → 화면 안내용 형식 목록

kind: sheet = 칸 주소(A1)가 있는 표 파일 / doc = 문단·표로 된 문서
"""
import os

from app.common.errors import WorkError

# 확장자: (종류, 이름, 읽는 모듈.함수, 검증 대상으로 고칠 수 있나)
FORMATS = {
    ".xlsx": ("sheet", "엑셀", "app.formats.xlsx:read_xlsx", False),
    ".xlsm": ("sheet", "엑셀(매크로)", "app.formats.xlsx:read_xlsx", False),
    ".xls": ("sheet", "구형 엑셀(97~2003)", "app.formats.xls:read_xls", False),
    ".ods": ("sheet", "오픈문서 스프레드시트", "app.formats.odf:read_ods", False),
    ".csv": ("sheet", "CSV(쉼표 구분)", "app.formats.text:read_csv", False),
    ".tsv": ("sheet", "TSV(탭 구분)", "app.formats.text:read_csv", False),
    ".hwpx": ("doc", "한글(hwpx)", None, True),
    ".hwp": ("doc", "구형 한글(hwp 5.0)", "app.formats.hwp:read_hwp", False),
    ".docx": ("doc", "워드", "app.formats.docx:read_docx", False),
    ".odt": ("doc", "오픈문서 텍스트(전자문서 공문)", "app.formats.odf:read_odt", False),
    ".pdf": ("doc", "PDF(글자 PDF)", "app.formats.pdf:read_pdf", False),
    ".txt": ("doc", "글자 파일", "app.formats.text:read_txt", False),
    ".md": ("doc", "마크다운(AI 초안 등)", "app.formats.text:read_txt", False),
    ".html": ("doc", "HTML", "app.formats.html:read_html", False),
    ".htm": ("doc", "HTML", "app.formats.html:read_html", False),
}
HINTS = {
    ".doc": "구형 워드(doc)는 워드에서 docx 로 저장해 주세요",
    ".ppt": "파워포인트는 PDF 로 저장하면 읽을 수 있습니다",
    ".pptx": "파워포인트는 PDF 로 저장하면 읽을 수 있습니다",
    ".hwt": "한글 서식 파일은 hwpx 로 저장해 주세요",
    ".jpg": "그림 파일은 글자를 읽을 수 없습니다(글자 인식 OCR 미지원)",
    ".png": "그림 파일은 글자를 읽을 수 없습니다(글자 인식 OCR 미지원)",
}


def ext_of(path):
    return os.path.splitext(path)[1].lower()


def supported(path):
    return ext_of(path) in FORMATS


def extensions():
    return tuple(FORMATS)


def describe():
    return [{"ext": e, "kind": k, "name": n, "editable": ed} for e, (k, n, _, ed) in FORMATS.items()]


def _load(spec):
    import importlib
    mod, fn = spec.split(":")
    return getattr(importlib.import_module(mod), fn)


def _doc_from(path):
    e = ext_of(path)
    if e == ".hwpx":
        from app.formats.hwpx import HwpxDoc
        return HwpxDoc(path)
    from app.formats.textdoc import TextDoc
    d = _load(FORMATS[e][2])(path)
    return TextDoc(d["blocks"], path=path, kind=e[1:], warnings=d.get("warnings"))


def read_source(path):
    """원본으로 읽기. 실패하면 WorkError(사람이 읽을 수 있는 이유)."""
    e = ext_of(path)
    if e not in FORMATS:
        raise WorkError(HINTS.get(e, f"지원하지 않는 형식입니다({e or '확장자 없음'})"))
    kind, name, spec, _ = FORMATS[e]
    try:
        if kind == "sheet":
            return "sheet", _load(spec)(path)
        return "doc", _doc_from(path)
    except WorkError:
        raise
    except Exception as ex:          # 각 형식의 오류(HwpError·PdfError …)를 한 가지로
        raise WorkError(str(ex) or ex.__class__.__name__)


def open_target(path):
    e = ext_of(path)
    if e not in FORMATS or FORMATS[e][0] != "doc":
        if e in FORMATS:
            raise WorkError(f"{FORMATS[e][1]} 파일은 원본(대조 자료)으로 등록하세요. 검증할 문서는 한글·워드·PDF·글자 파일입니다")
        raise WorkError(HINTS.get(e, f"지원하지 않는 형식입니다({e})"))
    try:
        return _doc_from(path)
    except Exception as ex:
        raise WorkError(str(ex) or ex.__class__.__name__)
