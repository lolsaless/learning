# -*- coding: utf-8 -*-
"""[엑셀 파일] xlsx 읽기(표준 라이브러리만). 값·표시 형식·수식 결과·숨은 시트를 읽는다."""
import re
import zipfile
import datetime
import xml.etree.ElementTree as ET

from app import config
from app.formats.xlsx.model import NS, RNS, DATE_FMT_IDS, parse_ref, Cell, Sheet, Workbook, _num_text


def _serial_to_date(x, date1904=False):
    base = datetime.datetime(1904, 1, 1) if date1904 else datetime.datetime(1899, 12, 30)
    try:
        d = base + datetime.timedelta(days=float(x))
    except (OverflowError, ValueError):
        return None
    if d.hour or d.minute:
        return d.strftime("%Y-%m-%d %H:%M")
    return d.strftime("%Y-%m-%d")


def read_xlsx(path, max_cells=None):
    max_cells = max_cells or config.MAX_CELLS_PER_SHEET
    wb = Workbook()
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        wbx = ET.fromstring(z.read("xl/workbook.xml"))
        pr = wbx.find(NS + "workbookPr")
        date1904 = pr is not None and pr.get("date1904") in ("1", "true")
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
                t = r.get("Target")
                if t.startswith("/"):
                    t = t[1:]
                elif not t.startswith("xl/"):
                    t = "xl/" + t
                rels[r.get("Id")] = t
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
        date_xf = set()
        dec_xf = {}
        if "xl/styles.xml" in names:
            st = ET.fromstring(z.read("xl/styles.xml"))
            custom = {}
            nf = st.find(NS + "numFmts")
            if nf is not None:
                for f in nf:
                    custom[int(f.get("numFmtId"))] = f.get("formatCode", "")
            xfs = st.find(NS + "cellXfs")
            if xfs is not None:
                for i, xf in enumerate(xfs):
                    fid = int(xf.get("numFmtId", "0"))
                    code = custom.get(fid, "")
                    clean = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", code).lower()
                    if fid in DATE_FMT_IDS or (fid >= 164 and (re.search(r"[yd]", clean) or ("mm" in clean and "0" not in clean))):
                        date_xf.add(i)
                    m = re.search(r"0\.(0+)", code)
                    if fid == 2 or fid == 4:
                        dec_xf[i] = 2
                    elif m:
                        dec_xf[i] = len(m.group(1))
        for sh in wbx.iter(NS + "sheet"):
            rid = sh.get(RNS + "id")
            target = rels.get(rid)
            s = Sheet(sh.get("name"), sh.get("state") in ("hidden", "veryHidden"))
            wb.sheets.append(s)
            if not target or target not in names:
                wb.warnings.append(f"시트 '{s.name}' 파일을 찾지 못함")
                continue
            count = 0
            with z.open(target) as fp:
                for ev, el in ET.iterparse(fp, events=("end",)):
                    if el.tag != NS + "c":
                        if el.tag == NS + "row":
                            el.clear()
                        continue
                    a1 = el.get("r")
                    if not a1:
                        el.clear()
                        continue
                    rc = parse_ref(a1)
                    t = el.get("t", "n")
                    sidx = int(el.get("s", "0"))
                    ve = el.find(NS + "v")
                    fe = el.find(NS + "f")
                    v = ve.text if ve is not None else None
                    f = fe.text if fe is not None else None
                    cell = None
                    if t == "s" and v is not None:
                        txt = shared[int(v)] if int(v) < len(shared) else ""
                        cell = Cell(txt, "s", txt, f)
                    elif t == "inlineStr":
                        txt = "".join(x.text or "" for x in el.iter(NS + "t"))
                        cell = Cell(txt, "s", txt, f)
                    elif t == "str":
                        cell = Cell(v or "", "s", v or "", f)
                    elif t == "b":
                        cell = Cell(v == "1", "b", "TRUE" if v == "1" else "FALSE", f)
                    elif t == "e":
                        cell = Cell(v or "", "e", v or "", f)
                    elif v is not None:
                        try:
                            x = float(v)
                        except ValueError:
                            cell = Cell(v, "s", v, f)
                        else:
                            if sidx in date_xf:
                                cell = Cell(x, "d", _serial_to_date(x, date1904) or v, f)
                            else:
                                d = dec_xf.get(sidx)
                                txt = (f"{x:,.{d}f}" if d is not None else _num_text(x))
                                cell = Cell(x, "n", txt, f)
                    elif f is not None:
                        cell = Cell("", "s", "", f)
                    if cell is not None and rc:
                        r, c = rc
                        s.cells[(r, c)] = cell
                        s.maxr = max(s.maxr, r)
                        s.maxc = max(s.maxc, c)
                        count += 1
                        if count >= max_cells:
                            s.truncated = True
                            wb.warnings.append(f"시트 '{s.name}'가 커서 앞 {max_cells:,}칸만 읽음")
                            break
                    el.clear()
    return wb


