# -*- coding: utf-8 -*-
"""[한글 파일] hwpx(zip 묶음) 열기와 저장. 원본 파일은 읽기만 하고, 저장은 항상 새 파일로 한다."""
import io
import re
import zipfile
import xml.etree.ElementTree as ET

from app.formats.hwpx.base import HwpxError, _register_ns


class PackageMixin:
    def _load(self):
        try:
            z = zipfile.ZipFile(self.path)
        except (zipfile.BadZipFile, OSError) as e:
            with open(self.path, "rb") as f:
                head = f.read(8)
            if head.startswith(b"\xd0\xcf\x11\xe0"):
                raise HwpxError("구형 hwp 또는 암호가 걸린 문서입니다(본문을 읽을 수 없음)")
            raise HwpxError(f"hwpx 파일을 열 수 없습니다: {e}")
        with z:
            names = z.namelist()
            if "Contents/section0.xml" not in names:
                raise HwpxError("hwpx 본문(Contents/section0.xml)이 없습니다")
            for zi in z.infolist():
                self.entries.append((zi, z.read(zi.filename)))
        order = []
        hpf = dict((zi.filename, b) for zi, b in self.entries).get("Contents/content.hpf", b"").decode("utf-8", "ignore")
        for m in re.finditer(r'href="(Contents/section\d+\.xml)"', hpf):
            order.append(m.group(1))
        allsec = sorted([zi.filename for zi, _ in self.entries if re.match(r"Contents/section\d+\.xml$", zi.filename)],
                        key=lambda n: int(re.findall(r"\d+", n)[0]))
        order = [n for n in order if n in allsec] + [n for n in allsec if n not in order]
        data = dict((zi.filename, b) for zi, b in self.entries)
        for name in order:
            raw = data[name]
            _register_ns(raw)
            decl_m = re.match(rb"\s*(<\?xml[^>]*\?>)", raw)
            decl = decl_m.group(1).decode() if decl_m else '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            st = re.search(rb"<hs:sec\b[^>]*>", raw)
            start_tag = st.group(0).decode() if st else None
            root = ET.fromstring(raw)
            self.sections.append([name, root, start_tag, decl])
        if "Contents/header.xml" in data:
            self.header_name = "Contents/header.xml"
            self.header_raw = data["Contents/header.xml"].decode("utf-8")
        self._reparent()

    def _reparent(self):
        self._parent = {}
        for _, root, _, _ in self.sections:
            for p in root.iter():
                for c in p:
                    self._parent[c] = p


    def to_bytes(self):
        bio = io.BytesIO()
        secs = {name: (root, st, decl) for name, root, st, decl in self.sections}
        with zipfile.ZipFile(bio, "w") as z:
            for zi, data in self.entries:
                name = zi.filename
                if name in secs:
                    root, st, decl = secs[name]
                    body = ET.tostring(root, encoding="unicode")
                    if st:
                        body = re.sub(r"^<hs:sec\b[^>]*>", lambda m: st, body, count=1)
                    data = (decl + body).encode("utf-8")
                elif name == self.header_name and getattr(self, "_header_changed", False):
                    data = self.header_raw.encode("utf-8")
                nz = zipfile.ZipInfo(name, date_time=zi.date_time)
                nz.compress_type = zipfile.ZIP_STORED if name in ("mimetype", "version.xml") or name.endswith(".png") else zipfile.ZIP_DEFLATED
                nz.external_attr = zi.external_attr
                z.writestr(nz, data)
        return bio.getvalue()

    def save(self, path):
        data = self.to_bytes()
        with open(path, "wb") as f:
            f.write(data)
        return path

