# -*- coding: utf-8 -*-
"""시험 전용: 아주 작은 HWP 5.0 파일 만들기(OLE 묶음 + 레코드). 프로그램 기능이 아니라 hwp 읽기 시험용.

공개된 HWP 5.0 형식대로 FileHeader 와 BodyText/Section0(압축) 를 만든다. 문단과 표(칸 합치기 포함)만 넣는다.
OLE 는 최소 구조(미니 스트림 없이 모든 스트림을 일반 섹터에 저장)로 쓴다.
"""
import struct
import zlib

SS = 512
FREESECT, ENDOFCHAIN, FATSECT, NOSTREAM = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFF


def _rec(tag, level, payload):
    size = len(payload)
    if size >= 0xFFF:
        return struct.pack("<I", tag | (level << 10) | (0xFFF << 20)) + struct.pack("<I", size) + payload
    return struct.pack("<I", tag | (level << 10) | (size << 20)) + payload


def _text(s):
    return (s + "\r").encode("utf-16-le")


def para(text, level=0):
    return _rec(66, level, b"\x00" * 22) + _rec(67, level + 1, _text(text))


def table(rows, level=0, merges=None):
    """rows: [[글자…]…], merges: {(행, 열): (행 합치기, 열 합치기)} — 합쳐진 칸 자리는 None."""
    merges = merges or {}
    nrow, ncol = len(rows), max(len(r) for r in rows)
    out = _rec(66, level, b"\x00" * 22) + _rec(67, level + 1, ("\x0b" + "\x00" * 7 + "\r").encode("utf-16-le"))
    out += _rec(71, level + 1, b" lbt" + b"\x00" * 40)                 # 'tbl ' (거꾸로 저장)
    out += _rec(77, level + 2, struct.pack("<IHH", 0, nrow, ncol) + b"\x00" * 10)
    for r, row in enumerate(rows):
        for c, t in enumerate(row):
            if t is None:
                continue
            rs, cs = merges.get((r, c), (1, 1))
            out += _rec(72, level + 2, struct.pack("<HIH", 1, 0, 0) + struct.pack("<HHHH", c, r, cs, rs) + b"\x00" * 16)
            out += para(str(t), level + 2)
    return out


def _dir_entry(name, typ, child=NOSTREAM, right=NOSTREAM, start=ENDOFCHAIN, size=0):
    n = name.encode("utf-16-le") + b"\x00\x00"
    e = n.ljust(64, b"\x00") + struct.pack("<HBB", len(n), typ, 1) + struct.pack("<III", NOSTREAM, right, child)
    e += b"\x00" * 16 + b"\x00" * 4 + b"\x00" * 16 + struct.pack("<II", start, size) + b"\x00" * 4
    return e


def write_hwp(path, body, compressed=True, password=False):
    fh = b"HWP Document File".ljust(32, b"\x00") + struct.pack("<I", 0x05010000)
    fh += struct.pack("<I", (1 if compressed else 0) | (2 if password else 0))
    fh = fh.ljust(256, b"\x00")
    sec = zlib.compress(body)[2:-4] if compressed else body          # 원시 deflate(-15)
    streams = [fh, sec]
    sectors, starts = [], []
    nxt = 2                                                          # 0: FAT, 1: 디렉터리
    fat = [FATSECT, ENDOFCHAIN]
    for data in streams:
        n = max(1, (len(data) + SS - 1) // SS)
        starts.append(nxt)
        for k in range(n):
            fat.append(nxt + k + 1 if k < n - 1 else ENDOFCHAIN)
            sectors.append(data[k * SS:(k + 1) * SS].ljust(SS, b"\x00"))
        nxt += n
    assert len(fat) <= SS // 4
    fat += [FREESECT] * (SS // 4 - len(fat))
    dirs = (_dir_entry("Root Entry", 5, child=1) +
            _dir_entry("FileHeader", 2, right=2, start=starts[0], size=len(fh)) +
            _dir_entry("BodyText", 1, child=3) +
            _dir_entry("Section0", 2, start=starts[1], size=len(sec)))
    hdr = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 16 + struct.pack("<HHHH", 0x3E, 3, 0xFFFE, 9)
    hdr += struct.pack("<H", 6) + b"\x00" * 10 + struct.pack("<I", 1) + struct.pack("<I", 1) + b"\x00" * 4
    hdr += struct.pack("<I", 0)                                       # 미니 스트림 기준 0 → 모두 일반 섹터
    hdr += struct.pack("<II", ENDOFCHAIN, 0) + struct.pack("<II", ENDOFCHAIN, 0)
    hdr += struct.pack("<I", 0) + struct.pack("<I", FREESECT) * 108
    assert len(hdr) == SS
    with open(path, "wb") as f:
        f.write(hdr + struct.pack(f"<{SS // 4}I", *fat) + dirs + b"".join(sectors))
    return path
