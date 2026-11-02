"""HWPX 읽기 — load_document() 하나만 바깥에서 쓰면 된다."""
from __future__ import annotations

import hashlib
import os
from typing import Optional, Union

from .body import BodyParser
from .model import Block, Document, Run
from .package import HwpxError, HwpxPackage
from .styles import describe, describe_delta, parse_char_styles

__all__ = ["load_document", "Document", "Block", "Run", "HwpxError", "describe", "describe_delta"]


def load_document(source: Union[str, bytes], name: Optional[str] = None,
                  doc_id: Optional[str] = None) -> Document:
    """파일 경로 또는 파일 내용(bytes)을 받아 Document 를 만든다."""
    if isinstance(source, str):
        with open(source, "rb") as f:
            data = f.read()
        name = name or os.path.basename(source)
        source_path = os.path.abspath(source)
    else:
        data = bytes(source)
        source_path = ""
    sha1 = hashlib.sha1(data).hexdigest()
    pkg = HwpxPackage(data)

    warnings = []
    styles = {}
    if pkg.header_name():
        styles = parse_char_styles(pkg.xml(pkg.header_name()))
    else:
        warnings.append("header.xml 없음 — 서식 비교를 할 수 없습니다")

    parser = BodyParser(styles)
    sections = pkg.section_names()
    for i, sec in enumerate(sections):
        parser.parse_section(pkg.xml(sec), i)
    if not parser.blocks:
        warnings.append("본문에서 글자를 찾지 못했습니다")

    stats = dict(parser.stats)
    stats["blocks"] = len(parser.blocks)
    stats["pages_est"] = parser.page
    return Document(
        id=doc_id or sha1[:12], name=name or "문서.hwpx", size=len(data), sha1=sha1,
        meta=pkg.metadata(), blocks=parser.blocks, styles=parser.style_table,
        stats=stats, warnings=warnings, source_path=source_path,
    )
