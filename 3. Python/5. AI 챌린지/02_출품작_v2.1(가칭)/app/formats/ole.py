# -*- coding: utf-8 -*-
"""[파일 형식] OLE 복합 문서(구형 hwp·xls·doc가 쓰는 묶음 파일) 읽기. 표준 라이브러리만 사용.

    f = OleFile(경로)
    f.streams()            → ["FileHeader", "BodyText/Section0", ...]
    f.read("BodyText/Section0") → bytes

구조: 512바이트 머리 → FAT(섹터 사슬표) → 디렉터리(이름·시작 섹터·크기) → 작은 스트림은 미니 FAT 으로 읽음.
"""
import struct

MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
FREESECT, ENDOFCHAIN = 0xFFFFFFFF, 0xFFFFFFFE


class OleError(Exception):
    pass


def is_ole(path):
    try:
        with open(path, "rb") as f:
            return f.read(8) == MAGIC
    except OSError:
        return False


class OleFile:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = f.read()
        d = self.data
        if d[:8] != MAGIC:
            raise OleError("OLE 복합 문서가 아닙니다")
        self.ssz = 1 << struct.unpack_from("<H", d, 0x1E)[0]
        self.mssz = 1 << struct.unpack_from("<H", d, 0x20)[0]
        n_fat = struct.unpack_from("<I", d, 0x2C)[0]
        first_dir = struct.unpack_from("<I", d, 0x30)[0]
        self.cutoff = struct.unpack_from("<I", d, 0x38)[0]
        first_mfat, n_mfat = struct.unpack_from("<II", d, 0x3C)
        first_difat, n_difat = struct.unpack_from("<II", d, 0x44)
        difat = list(struct.unpack_from("<109I", d, 0x4C))
        s, guard = first_difat, 0
        while s not in (FREESECT, ENDOFCHAIN) and guard < n_difat + 1:
            ints = struct.unpack_from(f"<{self.ssz // 4}I", d, self._off(s))
            difat.extend(ints[:-1])
            s = ints[-1]
            guard += 1
        fat_secs = [x for x in difat if x not in (FREESECT, ENDOFCHAIN)][:n_fat]
        self.fat = []
        for fs in fat_secs:
            self.fat.extend(struct.unpack_from(f"<{self.ssz // 4}I", d, self._off(fs)))
        self.dirs = self._read_dirs(self._chain_bytes(first_dir))
        root = self.dirs[0]
        self.ministream = self._chain_bytes(root["start"])[:root["size"]] if root["start"] != ENDOFCHAIN else b""
        self.minifat = []
        if n_mfat and first_mfat not in (FREESECT, ENDOFCHAIN):
            mb = self._chain_bytes(first_mfat)
            self.minifat = list(struct.unpack_from(f"<{len(mb) // 4}I", mb, 0))
        self.paths = {}
        self._walk(root.get("child"), "")

    def _off(self, sec):
        return (sec + 1) * self.ssz

    def _chain(self, start, table):
        out, s, seen = [], start, set()
        while s not in (FREESECT, ENDOFCHAIN) and s < len(table) and s not in seen:
            seen.add(s)
            out.append(s)
            s = table[s]
        return out

    def _chain_bytes(self, start):
        return b"".join(self.data[self._off(s):self._off(s) + self.ssz] for s in self._chain(start, self.fat))

    def _read_dirs(self, raw):
        out = []
        for i in range(len(raw) // 128):
            e = raw[i * 128:(i + 1) * 128]
            nlen = struct.unpack_from("<H", e, 64)[0]
            name = e[:max(0, nlen - 2)].decode("utf-16-le", "ignore")
            typ = e[66]
            left, right, child = struct.unpack_from("<III", e, 68)
            start, size = struct.unpack_from("<II", e, 116)
            out.append({"name": name, "type": typ, "left": left, "right": right, "child": child,
                        "start": start, "size": size})
        return out

    def _walk(self, idx, prefix, depth=0):
        if idx is None or idx >= len(self.dirs) or depth > 64:
            return
        stack, seen = [idx], set()
        while stack:
            i = stack.pop()
            if i in seen or i >= len(self.dirs) or i == FREESECT:
                continue
            seen.add(i)
            e = self.dirs[i]
            path = prefix + e["name"]
            if e["type"] == 2:
                self.paths[path] = i
            elif e["type"] == 1:
                self._walk(e["child"], path + "/", depth + 1)
            for j in (e["left"], e["right"]):
                if j != FREESECT:
                    stack.append(j)

    def streams(self):
        return sorted(self.paths)

    def exists(self, name):
        return name in self.paths

    def read(self, name):
        if name not in self.paths:
            raise OleError(f"스트림이 없습니다: {name}")
        e = self.dirs[self.paths[name]]
        if e["size"] < self.cutoff:
            out = b"".join(self.ministream[s * self.mssz:(s + 1) * self.mssz] for s in self._chain(e["start"], self.minifat))
        else:
            out = self._chain_bytes(e["start"])
        return out[:e["size"]]
