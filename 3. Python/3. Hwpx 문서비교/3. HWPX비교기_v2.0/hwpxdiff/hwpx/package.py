"""HWPX 꾸러미(zip) 열기 — 파일 목록·메타정보·본문(section) XML 위치 찾기.

HWPX 내부 구조 (한글 2014 이후 OWPML 형식)
    mimetype                    'application/hwp+zip'
    Contents/content.hpf        메타정보(작성자·수정일) + 본문 파일 목록(spine)
    Contents/header.xml         글꼴·글자모양(charPr)·문단모양 정의
    Contents/section0.xml ...   본문 (구역별 1개씩)
    Preview/PrvText.txt         미리보기 글자 (앞부분만)
"""
from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Union

Source = Union[str, bytes]


class HwpxError(Exception):
    """HWPX 형식이 아니거나 손상된 파일."""


def local(tag: str) -> str:
    """'{namespace}name' 또는 'hp:name' → 'name'."""
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1] if isinstance(tag, str) else ""


class HwpxPackage:
    def __init__(self, source: Source):
        try:
            fp = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
            self.zip = zipfile.ZipFile(fp)
        except zipfile.BadZipFile as e:
            raise HwpxError("zip 형식이 아닙니다 (HWP 5.0 .hwp 파일은 지원하지 않음 — 한글에서 HWPX로 저장)") from e
        self.names = set(self.zip.namelist())
        if "Contents/content.hpf" not in self.names and not self._section_names_fallback():
            raise HwpxError("HWPX 본문(Contents/section*.xml)을 찾을 수 없습니다")

    # ── 원시 읽기 ───────────────────────────────────
    def read(self, name: str) -> bytes:
        return self.zip.read(name)

    def xml(self, name: str) -> ET.Element:
        try:
            return ET.fromstring(self.read(name))
        except ET.ParseError as e:
            raise HwpxError(f"{name} XML 해석 실패: {e}") from e

    # ── 메타정보 ────────────────────────────────────
    def xml_spans(self, name: str):
        """(v2.0) 위치 기억 읽기 → (root, spans, 원문 bytes). 병합·고치기에서 원문을 그대로 갈아 끼울 때 씀."""
        from .xmlspan import parse_with_spans
        data = self.read(name)
        try:
            root, spans = parse_with_spans(data)
        except Exception as e:
            raise HwpxError(f"{name} XML 해석 실패: {e}") from e
        return root, spans, data

    def metadata(self) -> Dict[str, str]:
        meta: Dict[str, str] = {}
        if "Contents/content.hpf" not in self.names:
            return meta
        root = self.xml("Contents/content.hpf")
        for el in root.iter():
            name = local(el.tag)
            if name == "meta" and el.get("name"):
                meta[el.get("name")] = (el.text or "").strip()
            elif name in ("title", "language") and (el.text or "").strip():
                meta[name] = el.text.strip()
        if "version.xml" in self.names:
            v = self.xml("version.xml")
            app = v.get("application") or ""
            ver = v.get("appVersion") or ""
            if app or ver:
                meta["application"] = f"{app} {ver}".strip()
        return meta

    # ── 본문 파일 순서 ──────────────────────────────
    def section_names(self) -> List[str]:
        """spine(읽기 순서)에 적힌 section 파일 목록."""
        if "Contents/content.hpf" in self.names:
            root = self.xml("Contents/content.hpf")
            hrefs = {}
            for el in root.iter():
                if local(el.tag) == "item" and el.get("id"):
                    hrefs[el.get("id")] = el.get("href", "")
            ordered = []
            for el in root.iter():
                if local(el.tag) == "itemref":
                    href = hrefs.get(el.get("idref", ""), "")
                    if re.search(r"section\d+\.xml$", href) and href in self.names:
                        ordered.append(href)
            if ordered:
                return ordered
        return self._section_names_fallback()

    def _section_names_fallback(self) -> List[str]:
        found = [n for n in self.names if re.fullmatch(r"Contents/section\d+\.xml", n)]
        return sorted(found, key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))

    def header_name(self) -> str:
        return "Contents/header.xml" if "Contents/header.xml" in self.names else ""

    def preview_text(self) -> str:
        if "Preview/PrvText.txt" in self.names:
            raw = self.read("Preview/PrvText.txt")
            for enc in ("utf-8", "utf-16", "cp949"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
        return ""
