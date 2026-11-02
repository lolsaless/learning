# -*- coding: utf-8 -*-
"""[파일 형식] 구형 엑셀(xls, BIFF8 = 엑셀 97~2003) 읽기 → xlsx 와 같은 Workbook 그릇. 표준 라이브러리만.

    read_xls(경로) → Workbook (app/formats/xlsx/model.py)

읽는 레코드: BOUNDSHEET(시트) · SST/CONTINUE(공유 글자) · FORMAT·XF(표시 자릿수·날짜·%) ·
LABELSST·LABEL·NUMBER·RK·MULRK·FORMULA(+STRING)·BOOLERR.
'xls' 확장자이지만 실제로는 HTML·XML 인 파일(전자문서·통계 시스템 내보내기에 흔함)은 html 읽기로 넘긴다.
"""
import re
import struct
import datetime

from app import config
from app.formats.ole import OleFile, OleError, is_ole
from app.formats.xlsx.model import Cell, Sheet, Workbook, _num_text

BUILTIN_DATE = set(range(14, 23)) | set(range(45, 48))
BUILTIN_DEC = {2: 2, 4: 2, 10: 2, 11: 2, 39: 2, 40: 2, 9: 0, 3: 0, 1: 0, 37: 0, 38: 0}
PERCENT_IDS = {9: 0, 10: 2}


class XlsError(Exception):
    pass


def _records(stream):
    i, n = 0, len(stream)
    while i + 4 <= n:
        rt, ln = struct.unpack_from("<HH", stream, i)
        yield i, rt, stream[i + 4:i + 4 + ln]
        i += 4 + ln


class _Reader:
    """CONTINUE 레코드로 이어지는 글자를 경계 넘어 읽는다(SST)."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.ci = 0
        self.pos = 0

    def _cur(self):
        return self.chunks[self.ci]

    def bytes(self, k):
        out = b""
        while k > 0:
            if self.pos >= len(self._cur()):
                self.ci += 1
                self.pos = 0
                if self.ci >= len(self.chunks):
                    raise XlsError("SST 가 잘렸습니다")
            take = min(k, len(self._cur()) - self.pos)
            out += self._cur()[self.pos:self.pos + take]
            self.pos += take
            k -= take
        return out

    def u8(self):
        return self.bytes(1)[0]

    def u16(self):
        return struct.unpack("<H", self.bytes(2))[0]

    def u32(self):
        return struct.unpack("<I", self.bytes(4))[0]

    def chars(self, cch, high):
        out = []
        while cch > 0:
            if self.pos >= len(self._cur()):
                self.ci += 1
                self.pos = 0
                high = self.u8() & 1             # CONTINUE 첫 바이트 = 새 글자 폭 표시
            avail = len(self._cur()) - self.pos
            per = 2 if high else 1
            take = min(cch, avail // per) or 1
            raw = self.bytes(take * per)
            out.append(raw.decode("utf-16-le", "replace") if high else raw.decode("latin-1"))
            cch -= take
        return "".join(out)

    def xlstring(self):
        cch = self.u16()
        flags = self.u8()
        high, ext, rich = flags & 1, flags & 4, flags & 8
        nrun = self.u16() if rich else 0
        next_ = self.u32() if ext else 0
        s = self.chars(cch, high)
        if nrun:
            self.bytes(4 * nrun)
        if next_:
            self.bytes(next_)
        return s


def _short_string(p, off, cch_size=1):
    cch = p[off] if cch_size == 1 else struct.unpack_from("<H", p, off)[0]
    off += cch_size
    high = p[off] & 1
    off += 1
    raw = p[off:off + cch * (2 if high else 1)]
    return raw.decode("utf-16-le", "replace") if high else raw.decode("latin-1")


def _rk(v):
    mul100 = v & 1
    if v & 2:
        x = float(v >> 2 if v < 0x80000000 else (v >> 2) - (1 << 30))
    else:
        x = struct.unpack("<d", struct.pack("<Q", (v & 0xFFFFFFFC) << 32))[0]
    return x / 100 if mul100 else x


def _sniff_text(path):
    with open(path, "rb") as f:
        head = f.read(2048).lstrip(b"\xef\xbb\xbf").lower()
    return head.startswith((b"<", b"\xff\xfe<", b"\xfe\xff\x00<")) or b"<html" in head or b"<table" in head


def read_xls(path, max_cells=None):
    if not is_ole(path):
        if _sniff_text(path):
            from app.formats.html import read_html_book
            return read_html_book(path)
        raise XlsError("xls 파일 형식이 아닙니다")
    max_cells = max_cells or config.MAX_CELLS_PER_SHEET
    try:
        ole = OleFile(path)
    except OleError as e:
        raise XlsError(str(e))
    name = "Workbook" if ole.exists("Workbook") else ("Book" if ole.exists("Book") else None)
    if not name:
        raise XlsError("엑셀 통합문서 스트림이 없습니다")
    data = ole.read(name)
    recs = list(_records(data))
    if not recs or recs[0][1] != 0x0809 or struct.unpack_from("<H", recs[0][2], 0)[0] != 0x0600:
        raise XlsError("엑셀 5.0/95 이하 형식입니다. 엑셀에서 xlsx 로 다시 저장해 주세요")
    sheets, sst, fmts, xf_fmt = [], [], {}, []
    date1904 = False
    i = 0
    while i < len(recs):
        off, rt, p = recs[i]
        if rt == 0x002F:
            raise XlsError("암호가 걸린 xls 입니다. 엑셀에서 암호를 풀고 다시 저장해 주세요")
        if rt == 0x0085:
            pos, vis = struct.unpack_from("<IB", p, 0)
            typ = p[5]
            if typ == 0:
                sheets.append((pos, _short_string(p, 6), vis != 0))
        elif rt == 0x0022:
            date1904 = struct.unpack_from("<H", p, 0)[0] == 1
        elif rt == 0x041E:
            fmts[struct.unpack_from("<H", p, 0)[0]] = _short_string(p, 2, 2)
        elif rt == 0x00E0:
            xf_fmt.append(struct.unpack_from("<H", p, 2)[0])
        elif rt == 0x00FC:
            chunks = [p[8:]]
            j = i + 1
            while j < len(recs) and recs[j][1] == 0x003C:
                chunks.append(recs[j][2])
                j += 1
            total = struct.unpack_from("<I", p, 4)[0]
            rd = _Reader(chunks)
            try:
                for _ in range(total):
                    sst.append(rd.xlstring())
            except (XlsError, struct.error, IndexError):
                pass
            i = j - 1
        elif rt == 0x000A:
            break
        i += 1

    def style(xf):
        fid = xf_fmt[xf] if xf < len(xf_fmt) else 0
        code = fmts.get(fid, "")
        clean = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", code).lower()
        is_date = fid in BUILTIN_DATE or (fid >= 164 and (re.search(r"[yd]", clean) or ("mm" in clean and "0" not in clean)))
        dec = BUILTIN_DEC.get(fid)
        m = re.search(r"0\.(0+)", code)
        if m:
            dec = len(m.group(1))
        pct = fid in PERCENT_IDS or "%" in clean
        return is_date, dec, pct

    cache = {}

    def mk(x, xf):
        st = cache.get(xf)
        if st is None:
            st = cache[xf] = style(xf)
        is_date, dec, pct = st
        if is_date:
            base = datetime.datetime(1904, 1, 1) if date1904 else datetime.datetime(1899, 12, 30)
            try:
                return Cell(x, "d", (base + datetime.timedelta(days=x)).strftime("%Y-%m-%d"))
            except (OverflowError, ValueError):
                pass
        if pct:
            d = dec or 0
            return Cell(x, "n", f"{x * 100:.{d}f}%")
        return Cell(x, "n", f"{x:,.{dec}f}" if dec is not None else _num_text(x))

    wb = Workbook()
    by_off = {o: k for k, (o, _, _) in enumerate(recs)}
    for pos, sname, hidden in sheets:
        sh = Sheet(sname, hidden)
        wb.sheets.append(sh)
        k = by_off.get(pos)
        if k is None:
            wb.warnings.append(f"시트 '{sname}' 위치를 찾지 못함")
            continue
        count = 0
        pending_formula = None
        k += 1
        while k < len(recs):
            _, rt, p = recs[k]
            k += 1
            cells = []
            if rt == 0x000A:
                break
            if rt == 0x00FD and len(p) >= 10:
                r, c, xf, idx = struct.unpack_from("<HHHI", p, 0)
                t = sst[idx] if idx < len(sst) else ""
                cells.append((r, c, Cell(t, "s", t)))
            elif rt == 0x0204 and len(p) >= 8:
                r, c, xf = struct.unpack_from("<HHH", p, 0)
                t = _short_string(p, 6, 2)
                cells.append((r, c, Cell(t, "s", t)))
            elif rt == 0x0203 and len(p) >= 14:
                r, c, xf = struct.unpack_from("<HHH", p, 0)
                cells.append((r, c, mk(struct.unpack_from("<d", p, 6)[0], xf)))
            elif rt == 0x027E and len(p) >= 10:
                r, c, xf, v = struct.unpack_from("<HHHI", p, 0)
                cells.append((r, c, mk(_rk(v), xf)))
            elif rt == 0x00BD and len(p) >= 6:
                r, c0 = struct.unpack_from("<HH", p, 0)
                n = (len(p) - 6) // 6
                for j in range(n):
                    xf, v = struct.unpack_from("<HI", p, 4 + j * 6)
                    cells.append((r, c0 + j, mk(_rk(v), xf)))
            elif rt == 0x0006 and len(p) >= 20:
                r, c, xf = struct.unpack_from("<HHH", p, 0)
                res = p[6:14]
                if res[6:8] == b"\xff\xff":
                    if res[0] == 0:
                        pending_formula = (r, c)
                    elif res[0] == 1:
                        cells.append((r, c, Cell(bool(res[2]), "b", "TRUE" if res[2] else "FALSE")))
                else:
                    cells.append((r, c, mk(struct.unpack("<d", res)[0], xf)))
            elif rt == 0x0207 and pending_formula:
                t = _short_string(p, 0, 2)
                cells.append((pending_formula[0], pending_formula[1], Cell(t, "s", t)))
                pending_formula = None
            elif rt == 0x0205 and len(p) >= 8:
                r, c, xf = struct.unpack_from("<HHH", p, 0)
                if p[7] == 0:
                    cells.append((r, c, Cell(bool(p[6]), "b", "TRUE" if p[6] else "FALSE")))
            for r, c, cell in cells:
                sh.cells[(r, c)] = cell
                sh.maxr = max(sh.maxr, r)
                sh.maxc = max(sh.maxc, c)
                count += 1
            if count >= max_cells:
                sh.truncated = True
                wb.warnings.append(f"시트 '{sname}'가 커서 앞 {max_cells:,}칸만 읽음")
                break
    return wb
