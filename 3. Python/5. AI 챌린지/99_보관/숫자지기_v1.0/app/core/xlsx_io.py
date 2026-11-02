# -*- coding: utf-8 -*-
"""엑셀(xlsx) 읽기·쓰기 — 표준 라이브러리만 사용(설치 불필요)."""
import re
import zipfile
import datetime
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from app import config

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PNS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

DATE_FMT_IDS = set(range(14, 23)) | {27, 30, 36, 45, 46, 47, 50, 57}


def col2idx(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def idx2col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def ref(r, c):
    return f"{idx2col(c)}{r + 1}"


def parse_ref(a1):
    m = re.match(r"^\$?([A-Z]+)\$?(\d+)$", a1.strip().upper())
    if not m:
        return None
    return int(m.group(2)) - 1, col2idx(m.group(1))


class Cell:
    __slots__ = ("v", "kind", "text", "f")

    def __init__(self, v, kind, text, f=None):
        self.v = v          # float(숫자) | str | bool
        self.kind = kind    # 'n' 숫자, 's' 글자, 'd' 날짜, 'b' 참거짓, 'e' 오류
        self.text = text    # 화면 표시용 글자
        self.f = f          # 수식(있으면)


class Sheet:
    def __init__(self, name, hidden=False):
        self.name = name
        self.hidden = hidden
        self.cells = {}
        self.maxr = -1
        self.maxc = -1
        self.truncated = False

    def get(self, r, c):
        return self.cells.get((r, c))


class Workbook:
    def __init__(self):
        self.sheets = []
        self.warnings = []

    def sheet(self, name):
        for s in self.sheets:
            if s.name == name:
                return s
        return None


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


def _num_text(x):
    if x.is_integer() and abs(x) < 1e15:
        return f"{int(x):,}"
    s = f"{x:.10f}".rstrip("0").rstrip(".")
    return s


# ─────────────────────────────────────────────────────
#  쓰기
# ─────────────────────────────────────────────────────
class _Styles:
    def __init__(self):
        self.fmts = {}     # code -> id
        self.fills = ["none", "gray125"]
        self.xfs = [(0, 0, 0, 0, False, None)]   # numFmtId, fontId, fillId, borderId, wrap, align
        self.xf_map = {self.xfs[0]: 0}

    def fmt_id(self, code):
        builtin = {"General": 0, "0": 1, "0.00": 2, "#,##0": 3, "#,##0.00": 4, "@": 49}
        if code in builtin:
            return builtin[code]
        if code not in self.fmts:
            self.fmts[code] = 164 + len(self.fmts)
        return self.fmts[code]

    def fill_id(self, color):
        if not color:
            return 0
        if color not in self.fills:
            self.fills.append(color)
        return self.fills.index(color)

    def xf(self, fmt=None, bold=False, fill=None, border=True, wrap=False, align=None):
        key = (self.fmt_id(fmt or "General"), 1 if bold else 0, self.fill_id(fill), 1 if border else 0, wrap, align)
        if key not in self.xf_map:
            self.xf_map[key] = len(self.xfs)
            self.xfs.append(key)
        return self.xf_map[key]

    def xml(self):
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">']
        if self.fmts:
            out.append(f'<numFmts count="{len(self.fmts)}">')
            for code, i in self.fmts.items():
                out.append(f'<numFmt numFmtId="{i}" formatCode="{escape(code, {chr(34): "&quot;"})}"/>')
            out.append("</numFmts>")
        out.append('<fonts count="2"><font><sz val="10"/><name val="맑은 고딕"/><family val="3"/><charset val="129"/></font>'
                   '<font><b/><sz val="10"/><name val="맑은 고딕"/><family val="3"/><charset val="129"/></font></fonts>')
        out.append(f'<fills count="{len(self.fills)}">')
        for f in self.fills:
            if f in ("none", "gray125"):
                out.append(f'<fill><patternFill patternType="{f}"/></fill>')
            else:
                c = f.lstrip("#").upper()
                out.append(f'<fill><patternFill patternType="solid"><fgColor rgb="FF{c}"/><bgColor indexed="64"/></patternFill></fill>')
        out.append("</fills>")
        out.append('<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
                   '<border><left style="thin"><color indexed="64"/></left><right style="thin"><color indexed="64"/></right>'
                   '<top style="thin"><color indexed="64"/></top><bottom style="thin"><color indexed="64"/></bottom><diagonal/></border></borders>')
        out.append('<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>')
        out.append(f'<cellXfs count="{len(self.xfs)}">')
        for (nf, fo, fi, bo, wrap, align) in self.xfs:
            attrs = f'numFmtId="{nf}" fontId="{fo}" fillId="{fi}" borderId="{bo}" xfId="0"'
            if nf:
                attrs += ' applyNumberFormat="1"'
            if fo:
                attrs += ' applyFont="1"'
            if fi:
                attrs += ' applyFill="1"'
            if bo:
                attrs += ' applyBorder="1"'
            if wrap or align:
                al = '<alignment'
                if align:
                    al += f' horizontal="{align}"'
                al += ' vertical="center"'
                if wrap:
                    al += ' wrapText="1"'
                al += '/>'
                out.append(f'<xf {attrs} applyAlignment="1">{al}</xf>')
            else:
                out.append(f'<xf {attrs}/>')
        out.append("</cellXfs>")
        out.append('<cellStyles count="1"><cellStyle name="표준" xfId="0" builtinId="0"/></cellStyles>')
        out.append("</styleSheet>")
        return "".join(out)


def _x(s):
    s = escape(str(s))
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)


def write_xlsx(path, sheets, author="숫자지기"):
    """sheets: [{name, rows:[[cell,...]], widths:[..], freeze:(r,c), autofilter:bool, merges:[...]}]
    cell: None | str | int | float | {"v":..., "fmt":"#,##0", "bold":bool, "fill":"#RRGGBB",
                                      "text":bool(글자로 저장), "wrap":bool, "align":"center", "f":"수식"}"""
    st = _Styles()
    shared, smap = [], {}

    def sidx(s):
        if s not in smap:
            smap[s] = len(shared)
            shared.append(s)
        return smap[s]

    sheet_xml = []
    for sh in sheets:
        rows = sh.get("rows", [])
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">']
        maxc = max((len(r) for r in rows), default=1)
        out.append(f'<dimension ref="A1:{ref(max(len(rows) - 1, 0), max(maxc - 1, 0))}"/>')
        fr = sh.get("freeze")
        if fr:
            r0, c0 = fr
            tl = ref(r0, c0)
            pane = '<pane '
            if c0:
                pane += f'xSplit="{c0}" '
            if r0:
                pane += f'ySplit="{r0}" '
            act = "bottomRight" if (r0 and c0) else ("bottomLeft" if r0 else "topRight")
            pane += f'topLeftCell="{tl}" activePane="{act}" state="frozen"/>'
            out.append(f'<sheetViews><sheetView workbookViewId="0">{pane}<selection pane="{act}" activeCell="{tl}" sqref="{tl}"/></sheetView></sheetViews>')
        else:
            out.append('<sheetViews><sheetView workbookViewId="0"/></sheetViews>')
        out.append('<sheetFormatPr defaultRowHeight="16.5"/>')
        widths = sh.get("widths")
        if widths:
            out.append("<cols>")
            for i, w in enumerate(widths):
                out.append(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>')
            out.append("</cols>")
        out.append("<sheetData>")
        for ri, row in enumerate(rows):
            out.append(f'<row r="{ri + 1}">')
            for ci, cell in enumerate(row):
                if cell is None:
                    continue
                spec = cell if isinstance(cell, dict) else {"v": cell}
                v = spec.get("v")
                s = st.xf(spec.get("fmt"), spec.get("bold", False), spec.get("fill"),
                          spec.get("border", True), spec.get("wrap", False), spec.get("align"))
                a = ref(ri, ci)
                if spec.get("f"):
                    cv = "" if v is None else f"<v>{v}</v>"
                    out.append(f'<c r="{a}" s="{s}"><f>{_x(spec["f"])}</f>{cv}</c>')
                elif v is None or v == "":
                    out.append(f'<c r="{a}" s="{s}"/>')
                elif isinstance(v, bool):
                    out.append(f'<c r="{a}" s="{s}" t="b"><v>{1 if v else 0}</v></c>')
                elif isinstance(v, (int, float)) and not spec.get("text"):
                    out.append(f'<c r="{a}" s="{s}"><v>{repr(float(v)) if isinstance(v, float) else v}</v></c>')
                else:
                    out.append(f'<c r="{a}" s="{s}" t="s"><v>{sidx(str(v))}</v></c>')
            out.append("</row>")
        out.append("</sheetData>")
        if sh.get("autofilter") and rows:
            out.append(f'<autoFilter ref="A1:{ref(len(rows) - 1, maxc - 1)}"/>')
        merges = sh.get("merges") or []
        if merges:
            out.append(f'<mergeCells count="{len(merges)}">' + "".join(f'<mergeCell ref="{m}"/>' for m in merges) + "</mergeCells>")
        out.append('<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>')
        out.append("</worksheet>")
        sheet_xml.append("".join(out))

    n = len(sheets)
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
    for i in range(n):
        ct.append(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    ct += ['<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
           '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>',
           '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
           '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
           '</Types>']
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            '</Relationships>')
    wbx = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
           '<bookViews><workbookView/></bookViews><sheets>']
    for i, sh in enumerate(sheets):
        nm = _x(sh["name"][:31])
        wbx.append(f'<sheet name="{nm}" sheetId="{i + 1}" r:id="rId{i + 1}"/>')
    wbx.append("</sheets>")
    dn = []
    for i, sh in enumerate(sheets):
        rows = sh.get("rows", [])
        if sh.get("autofilter") and rows:
            maxc = max(len(r) for r in rows)
            nm = sh["name"][:31].replace("'", "''")
            dn.append(f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">\'{_x(nm)}\'!$A$1:${idx2col(maxc - 1)}${len(rows)}</definedName>')
    if dn:
        wbx.append("<definedNames>" + "".join(dn) + "</definedNames>")
    wbx.append("</workbook>")
    wrels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for i in range(n):
        wrels.append(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>')
    wrels.append(f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    wrels.append(f'<Relationship Id="rId{n + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>')
    wrels.append("</Relationships>")
    sst = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared)}" uniqueCount="{len(shared)}">']
    for s in shared:
        sp = ' xml:space="preserve"' if s != s.strip() or "\n" in s else ""
        sst.append(f"<si><t{sp}>{_x(s)}</t></si>")
    sst.append("</sst>")
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:creator>{_x(author)}</dc:creator><cp:lastModifiedBy>{_x(author)}</cp:lastModifiedBy>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>')
    app = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
           'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Excel</Application></Properties>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(ct))
        z.writestr("_rels/.rels", rels)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)
        z.writestr("xl/workbook.xml", "".join(wbx))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(wrels))
        z.writestr("xl/styles.xml", st.xml())
        z.writestr("xl/sharedStrings.xml", "".join(sst))
        for i, x in enumerate(sheet_xml):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", x)
