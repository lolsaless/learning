# -*- coding: utf-8 -*-
"""한글(hwpx) 문서 읽기·누름틀 만들기·값 넣기·색 표시.

원칙
 1. 원본 파일은 열어서 읽기만 한다. 바뀐 내용은 항상 새 파일로 저장한다.
 2. 숫자 하나 = '칸(slot)' 하나. 작업본에서는 칸마다 누름틀(이름표 붙은 입력칸)을 씌워
    문서를 고쳐도 이름으로 같은 칸을 다시 찾을 수 있게 한다.
"""
import re
import copy
import zipfile
import itertools
import xml.etree.ElementTree as ET

from app import config
from app.core import numbers as N

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
T = {k: "{%s}%s" % (HP, k) for k in
     ["p", "run", "t", "ctrl", "tbl", "tr", "tc", "subList", "cellAddr", "cellSpan", "fieldBegin", "fieldEnd",
      "parameters", "integerParam", "stringParam", "linesegarray", "tab", "lineBreak"]}
CLICK_FIELD_ID = "627272811"      # '%clk' (누름틀 종류 번호, 한글 문서에서 확인한 방식)
_idgen = itertools.count(1900000001)


class HwpxError(Exception):
    pass


def _register_ns(raw):
    for m in re.finditer(rb'xmlns:([A-Za-z0-9_]+)="([^"]+)"', raw[:4000]):
        try:
            ET.register_namespace(m.group(1).decode(), m.group(2).decode())
        except ValueError:
            pass


def clean_name(s, limit=40):
    s = re.sub(r"\(.*?\)", "", s or "")
    s = re.sub(r"[^0-9A-Za-z가-힣·\.]+", "", s)
    return s[:limit] or "칸"


class Item:
    """문서 속 숫자(또는 빈 칸) 하나."""
    __slots__ = ("key", "kind", "table", "row", "col", "para", "k", "raw", "value", "dec", "unit", "comma",
                 "label", "rowlab", "collab", "context", "field", "editable", "header", "_t", "_span", "empty",
                 "block", "is_total_row", "is_total_col", "is_ratio_col", "is_avg")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def public(self):
        return {k: getattr(self, k) for k in self.__slots__ if not k.startswith("_")}


class HwpxDoc:
    def __init__(self, path):
        self.path = path
        self.entries = []          # [(ZipInfo, bytes)]
        self.sections = []         # [(name, root, start_tag, decl)]
        self.header_name = None
        self.header_raw = None
        self.items = []
        self.blocks = []
        self.tables = []           # 표 정보 [{ti, title, grid, nrow, ncol, head_rows, label_col}]
        self.warnings = []
        self._parent = {}
        self._load()
        self._scan()

    # ── 읽기 ──────────────────────────────────────────
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

    @staticmethod
    def _t_text(t):
        s = t.text or ""
        for ch in t:
            if ch.tag == T["tab"]:
                s += "\t"
            elif ch.tag == T["lineBreak"]:
                s += "\n"
            s += ch.tail or ""
        return s

    def _para_pieces(self, p, field_state):
        """문단 하나를 [(글자, t요소|None, 누름틀이름|None)] 조각과 표 목록으로 나눈다."""
        pieces, tables = [], []
        for run in p.findall(T["run"]):
            for ch in run:
                if ch.tag == T["t"]:
                    pieces.append((self._t_text(ch), ch if len(ch) == 0 else None, field_state[-1] if field_state else None))
                elif ch.tag == T["ctrl"]:
                    for c2 in ch:
                        if c2.tag == T["fieldBegin"]:
                            if c2.get("type") == "CLICK_HERE":
                                field_state.append(c2.get("name") or "")
                            else:
                                field_state.append(None)
                        elif c2.tag == T["fieldEnd"]:
                            if field_state:
                                field_state.pop()
                elif ch.tag == T["tbl"]:
                    tables.append(ch)
                    pieces.append(("", ("TABLE", ch), None))
        return pieces, tables

    def _scan(self):
        self.items, self.blocks, self.tables = [], [], []
        pidx = 0
        last_head = ""
        texts = []
        for _, root, _, _ in self.sections:
            for p in root.findall(T["p"]):
                fs = []
                pieces, _ = self._para_pieces(p, fs)
                cur = []
                for text, t, fname in pieces:
                    if isinstance(t, tuple) and t[0] == "TABLE":
                        if any(x[0].strip() for x in cur):
                            self._emit_para(cur, pidx)
                            pidx += 1
                        cur = []
                        ti = len(self.tables)
                        self._scan_table(t[1], ti, last_head)
                        continue
                    cur.append((text, t, fname))
                txt = "".join(x[0] for x in cur)
                if txt.strip():
                    self._emit_para(cur, pidx)
                    texts.append(txt)
                    if txt.strip().startswith("□"):
                        last_head = txt.strip()
                    pidx += 1
                elif not cur:
                    pass
        self.year = N.guess_year(texts + [it.context or "" for it in self.items])

    def _emit_para(self, pieces, pidx):
        text = "".join(x[0] for x in pieces)
        st = text.strip()
        style = "head" if st.startswith("□") else ("note" if st.startswith("※") or st.startswith("(") else "body")
        if pidx == 0:
            style = "title"
        found = N.extract_numbers(text) + N.find_placeholders(text)
        fields = self._field_spans(pieces)
        # 누름틀 안의 글자는 그 자체로 하나의 칸
        tokens = []
        for fs, fe, fname in fields:
            sub = text[fs:fe]
            tok = N.parse_cell(sub)
            tokens.append({"start": fs, "end": fe, "raw": sub, "value": tok["value"] if tok else None,
                           "dec": tok["dec"] if tok else 0, "unit": tok["unit"] if tok else "",
                           "comma": tok["comma"] if tok else False, "field": fname})
        for tk in found:
            if any(not (tk["end"] <= a or tk["start"] >= b) for a, b, _ in fields):
                continue
            tokens.append(tk)
        tokens.sort(key=lambda x: x["start"])
        out_pieces = []
        pos = 0
        for k, tk in enumerate(tokens):
            fname = tk.get("field")
            t_el, span = self._locate(pieces, tk["start"], tk["end"]) if not fname else (None, None)
            key = fname or None
            it = Item(kind="para", para=pidx, k=k, raw=tk["raw"], value=tk["value"], dec=tk["dec"], unit=tk["unit"],
                      comma=tk.get("comma"), context=text.strip(), field=fname,
                      editable=bool(fname) or t_el is not None, empty=tk["value"] is None,
                      label=f"본문 {pidx}번째 문단", rowlab="", collab="", header=False)
            it._t, it._span = t_el, span
            it.key = key or f"P{pidx}_{k + 1}"
            it.block = len(self.blocks)
            self.items.append(it)
            if tk["start"] > pos:
                out_pieces.append({"text": text[pos:tk["start"]]})
            out_pieces.append({"item": it.key, "text": tk["raw"]})
            pos = tk["end"]
        if pos < len(text):
            out_pieces.append({"text": text[pos:]})
        self.blocks.append({"type": "p", "style": style, "para": pidx, "text": text, "pieces": out_pieces})

    @staticmethod
    def _field_spans(pieces):
        spans = []
        pos = 0
        cur = None
        for text, t, fname in pieces:
            if fname is not None:
                if cur and cur[2] == fname and cur[1] == pos:
                    cur[1] = pos + len(text)
                else:
                    cur = [pos, pos + len(text), fname]
                    spans.append(cur)
            else:
                cur = None
            pos += len(text)
        return [tuple(s) for s in spans]

    @staticmethod
    def _locate(pieces, s, e):
        pos = 0
        for text, t, _ in pieces:
            a, b = pos, pos + len(text)
            if a <= s and e <= b and t is not None and not isinstance(t, tuple):
                return t, (s - a, e - a)
            pos = b
        return None, None

    def _cell_info(self, tc):
        addr = tc.find(T["cellAddr"])
        span = tc.find(T["cellSpan"])
        r, c = int(addr.get("rowAddr", 0)), int(addr.get("colAddr", 0))
        rs = int(span.get("rowSpan", 1)) if span is not None else 1
        cs = int(span.get("colSpan", 1)) if span is not None else 1
        return r, c, rs, cs

    def _scan_table(self, tbl, ti, title):
        cells = []
        for tr in tbl.findall(T["tr"]):
            for tc in tr.findall(T["tc"]):
                r, c, rs, cs = self._cell_info(tc)
                paras = tc.findall(f"{T['subList']}/{T['p']}")
                fs = []
                pieces = []
                for p in paras:
                    pc, inner = self._para_pieces(p, fs)
                    if pieces:
                        pieces.append(("\n", None, None))
                    pieces.extend(x for x in pc if not isinstance(x[1], tuple))
                    for itbl in inner:
                        self.warnings.append(f"표 {ti + 1} 안에 표가 또 있어 안쪽 표는 건너뜀")
                text = "".join(x[0] for x in pieces)
                cells.append({"r": r, "c": c, "rs": rs, "cs": cs, "text": text, "pieces": pieces, "tc": tc,
                              "head": tc.get("header") == "1", "p": paras[0] if paras else None})
        nrow = max((x["r"] + x["rs"] for x in cells), default=0)
        ncol = max((x["c"] + x["cs"] for x in cells), default=0)
        grid = {}
        for x in cells:
            for rr in range(x["r"], x["r"] + x["rs"]):
                for cc in range(x["c"], x["c"] + x["cs"]):
                    grid[(rr, cc)] = x
        # 머리글 행 수: header 표시가 있는 앞쪽 행. 없으면 1행.
        #  (2~3번째 행도 모든 칸이 채워진 글자이고 숫자가 없으면 머리글로 본다)
        head_rows = 0
        for rr in range(min(3, nrow)):
            row = [grid.get((rr, cc)) for cc in range(ncol)]
            row = [x for x in row if x]
            marked = row and all(x["head"] for x in row)
            textual = row and all(x["text"].strip() and not N.parse_cell(x["text"]) for x in row)
            if rr == 0 and (marked or textual or True):
                head_rows = 1
            elif marked or (textual and head_rows == rr and rr > 0 and any(x["r"] < rr for x in row)):
                head_rows = rr + 1
            else:
                break
        if nrow <= 1:
            head_rows = 0
        # 이름 열: 머리글 아래 칸 대부분이 숫자가 아닌 왼쪽 열
        label_col = -1
        for cc in range(min(2, ncol)):
            col = [grid.get((rr, cc)) for rr in range(head_rows, nrow)]
            col = [x for x in col if x]
            if col and sum(1 for x in col if x["text"].strip() and not N.parse_cell(x["text"])) >= max(1, len(col) * 0.6):
                label_col = cc
                break
        info = {"ti": ti, "title": title, "nrow": nrow, "ncol": ncol, "head_rows": head_rows, "label_col": label_col,
                "cells": [], "tbl": tbl}
        self.tables.append(info)

        def col_label(cc):
            labs = []
            for rr in range(head_rows):
                x = grid.get((rr, cc))
                if x and x["text"].strip() and x["text"].strip() not in labs:
                    labs.append(x["text"].strip())
            return " ".join(labs)

        def row_label(rr):
            if label_col < 0:
                return f"{rr + 1}행"
            x = grid.get((rr, label_col))
            return x["text"].strip() if x else f"{rr + 1}행"

        rows_out = []
        used = set(it.key for it in self.items)
        for rr in range(nrow):
            row_out = []
            rlab = row_label(rr)
            total_row = N.is_total_label(rlab)
            for x in sorted([c for c in cells if c["r"] == rr], key=lambda c: c["c"]):
                cc = x["c"]
                clab = col_label(cc)
                is_data = rr >= head_rows and cc != label_col
                cell_out = {"r": rr, "c": cc, "rs": x["rs"], "cs": x["cs"], "head": not is_data, "pieces": []}
                txt = x["text"]
                toks = []
                if is_data:
                    fields = self._field_spans(x["pieces"])
                    if fields:
                        for fs_, fe_, fname in fields:
                            sub = txt[fs_:fe_]
                            tok = N.parse_cell(sub)
                            toks.append({"start": fs_, "end": fe_, "raw": sub, "value": tok["value"] if tok else None,
                                         "dec": tok["dec"] if tok else 0, "unit": tok["unit"] if tok else "",
                                         "comma": tok["comma"] if tok else False, "field": fname})
                    else:
                        tok = N.parse_cell(txt)
                        if tok:
                            toks = [tok]
                        elif not txt.strip():
                            toks = [{"start": 0, "end": 0, "raw": "", "value": None, "dec": 0, "unit": "", "comma": False,
                                     "empty_cell": True}]
                        elif txt.strip() not in ("-", "－", "—"):
                            toks = N.extract_numbers(txt)
                pos = 0
                for k, tk in enumerate(toks):
                    fname = tk.get("field")
                    t_el, span = (None, None)
                    if not fname and not tk.get("empty_cell"):
                        t_el, span = self._locate(x["pieces"], tk["start"], tk["end"])
                    base = fname or f"표{ti + 1}_{clean_name(rlab, 16)}_{clean_name(clab, 16)}" + (f"_{k + 1}" if len(toks) > 1 else "")
                    key = base
                    n = 2
                    while key in used:
                        key = f"{base}_{n}"
                        n += 1
                    used.add(key)
                    it = Item(kind="cell", table=ti, row=rr, col=cc, k=k, raw=tk["raw"], value=tk["value"], dec=tk["dec"],
                              unit=tk["unit"], comma=tk.get("comma"), rowlab=rlab, collab=clab,
                              label=f"표{ti + 1} › {rlab} › {clab}", context=title, field=fname,
                              editable=bool(fname) or t_el is not None or bool(tk.get("empty_cell")),
                              empty=tk["value"] is None, header=False, is_total_row=total_row,
                              is_total_col=N.is_total_label(clab), is_ratio_col=N.is_ratio_label(clab),
                              is_avg=N.is_average_label(clab) or N.is_average_label(rlab))
                    it._t, it._span = t_el, span
                    if tk.get("empty_cell"):
                        it._t = ("EMPTY", x["p"])
                    it.key = key
                    it.block = len(self.blocks)
                    self.items.append(it)
                    info["cells"].append(it.key)
                    if tk["start"] > pos:
                        cell_out["pieces"].append({"text": txt[pos:tk["start"]]})
                    cell_out["pieces"].append({"item": key, "text": tk["raw"]})
                    pos = tk["end"]
                if pos < len(txt):
                    cell_out["pieces"].append({"text": txt[pos:]})
                row_out.append(cell_out)
            rows_out.append(row_out)
        self.blocks.append({"type": "table", "ti": ti, "title": title, "rows": rows_out, "ncol": ncol,
                            "head_rows": head_rows, "label_col": label_col})

    def item(self, key):
        for it in self.items:
            if it.key == key:
                return it
        return None

    def plain_texts(self):
        return [b["text"] for b in self.blocks if b["type"] == "p"]

    # ── 누름틀 만들기 ─────────────────────────────────
    def _field_ctrls(self, name, help_text):
        fid = str(next(_idgen))
        ctrl_b = ET.Element(T["ctrl"])
        fb = ET.SubElement(ctrl_b, T["fieldBegin"], {"id": fid, "type": "CLICK_HERE", "name": name, "editable": "1",
                                                     "dirty": "0", "zorder": "-1", "fieldid": CLICK_FIELD_ID, "metaTag": ""})
        prm = ET.SubElement(fb, T["parameters"], {"cnt": "3", "name": ""})
        ip = ET.SubElement(prm, T["integerParam"], {"name": "Prop"})
        ip.text = "9"
        guide = config.FIELD_GUIDE
        rest = f"Direction:wstring:{len(guide)}:{guide} HelpState:wstring:{len(help_text)}:{help_text} "
        sp = ET.SubElement(prm, T["stringParam"], {"name": "Command"})
        sp.text = f"Clickhere:set:{len(rest)}:{rest}"
        sp2 = ET.SubElement(prm, T["stringParam"], {"name": "Help"})
        sp2.text = help_text
        ctrl_e = ET.Element(T["ctrl"])
        ET.SubElement(ctrl_e, T["fieldEnd"], {"beginIDRef": fid, "fieldid": CLICK_FIELD_ID})
        return ctrl_b, ctrl_e

    def _drop_lineseg(self, el):
        p = el
        while p is not None and p.tag != T["p"]:
            p = self._parent.get(p)
        if p is not None:
            for ls in p.findall(T["linesegarray"]):
                p.remove(ls)

    def make_fields(self):
        """편집 가능한 숫자·빈 칸을 모두 누름틀로 감싼다. 바뀐 개수를 돌려준다."""
        if not config.USE_FIELDS:
            return 0
        by_t = {}
        empties = []
        for it in self.items:
            if it.field:
                continue
            if isinstance(it._t, tuple) and it._t[0] == "EMPTY":
                empties.append(it)
            elif it._t is not None:
                by_t.setdefault(id(it._t), (it._t, []))[1].append(it)
        n = 0
        for t, its in by_t.values():
            run = self._parent.get(t)
            if run is None:
                continue
            para = self._parent.get(run)
            its.sort(key=lambda i: i._span[0])
            text = t.text or ""
            kids = list(run)
            idx = kids.index(t)
            before, after = kids[:idx], kids[idx + 1:]
            new_runs = []
            pos = 0
            cur = ET.Element(T["run"], dict(run.attrib))
            for ch in before:
                cur.append(ch)
            for it in its:
                s, e = it._span
                if s > pos:
                    tt = ET.SubElement(cur, T["t"])
                    tt.text = text[pos:s]
                if len(cur):
                    new_runs.append(cur)
                fr = ET.Element(T["run"], dict(run.attrib))
                cb, ce = self._field_ctrls(it.key, it.label)
                fr.append(cb)
                tn = ET.SubElement(fr, T["t"])
                tn.text = text[s:e]
                fr.append(ce)
                new_runs.append(fr)
                it.field = it.key
                it._t = tn
                it._span = (0, e - s)
                pos = e
                cur = ET.Element(T["run"], dict(run.attrib))
                n += 1
            if pos < len(text):
                tt = ET.SubElement(cur, T["t"])
                tt.text = text[pos:]
            for ch in after:
                cur.append(ch)
            if len(cur):
                new_runs.append(cur)
            ri = list(para).index(run)
            para.remove(run)
            for j, nr in enumerate(new_runs):
                para.insert(ri + j, nr)
            self._reparent()
            self._drop_lineseg(new_runs[0])
        for it in empties:
            p = it._t[1]
            if p is None:
                continue
            run = p.find(T["run"])
            if run is None:
                run = ET.SubElement(p, T["run"], {"charPrIDRef": "0"})
            cb, ce = self._field_ctrls(it.key, it.label)
            run.append(cb)
            tn = ET.SubElement(run, T["t"])
            tn.text = ""
            run.append(ce)
            it.field = it.key
            it._t = tn
            n += 1
            self._reparent()
            self._drop_lineseg(run)
        return n

    # ── 값 읽기·넣기(누름틀) ─────────────────────────
    def field_values(self):
        out = {}
        for it in self.items:
            if it.field:
                out[it.field] = it.raw
        return out

    def _field_texts(self, name):
        """이름이 name인 누름틀 안의 t 요소 목록."""
        res = []
        for _, root, _, _ in self.sections:
            for p in root.iter(T["p"]):
                inside = []
                for run in p.findall(T["run"]):
                    for ch in run:
                        if ch.tag == T["ctrl"]:
                            for c2 in ch:
                                if c2.tag == T["fieldBegin"]:
                                    inside.append(c2.get("name") if c2.get("type") == "CLICK_HERE" else None)
                                elif c2.tag == T["fieldEnd"] and inside:
                                    inside.pop()
                        elif ch.tag == T["t"] and inside and inside[-1] == name:
                            res.append((ch, run))
                        elif ch.tag == T["t"] and inside and inside[-1] == name:
                            pass
                if inside and inside[-1] == name and not res:
                    pass
        return res

    def set_field(self, name, text):
        tl = self._field_texts(name)
        if not tl:
            # 빈 누름틀: fieldBegin 바로 뒤에 t 를 만든다
            for _, root, _, _ in self.sections:
                for fb in root.iter(T["fieldBegin"]):
                    if fb.get("name") == name and fb.get("type") == "CLICK_HERE":
                        ctrl = self._parent[fb]
                        run = self._parent[ctrl]
                        kids = list(run)
                        tn = ET.Element(T["t"])
                        tn.text = text
                        run.insert(kids.index(ctrl) + 1, tn)
                        self._reparent()
                        self._drop_lineseg(run)
                        return True
            return False
        first = True
        for t, run in tl:
            for ch in list(t):
                t.remove(ch)
            t.text = text if first else ""
            first = False
        self._drop_lineseg(tl[0][1])
        return True

    def set_text_at(self, item, text):
        """누름틀이 없는 칸(위치 추적 모드)의 값을 바꾼다."""
        if item._t is None or isinstance(item._t, tuple):
            return False
        t = item._t
        s, e = item._span
        old = t.text or ""
        t.text = old[:s] + text + old[e:]
        item._span = (s, s + len(text))
        self._drop_lineseg(t)
        return True

    # ── 색 표시(검증표시본) ──────────────────────────
    def _color_charpr(self, base_id, color=None, shade=None):
        h = self.header_raw
        key = f"{base_id}|{color}|{shade}"
        if not hasattr(self, "_cp_cache"):
            self._cp_cache = {}
        if key in self._cp_cache:
            return self._cp_cache[key]
        m = re.search(r'<hh:charPr id="%s"[\s\S]*?</hh:charPr>' % re.escape(str(base_id)), h)
        if not m:
            return None
        ids = [int(x) for x in re.findall(r'<hh:charPr id="(\d+)"', h)]
        new_id = max(ids) + 1
        x = m.group(0)
        x = re.sub(r'id="\d+"', f'id="{new_id}"', x, count=1)
        if color:
            x = re.sub(r'textColor="[^"]*"', f'textColor="{color}"', x, count=1)
        if shade:
            x = re.sub(r'shadeColor="[^"]*"', f'shadeColor="{shade}"', x, count=1)
        if color and "<hh:bold/>" not in x:
            x = re.sub(r'(<hh:charPr [^>]*>)', r'\1<hh:bold/>', x, count=1)
        h = h.replace("</hh:charProperties>", x + "</hh:charProperties>", 1)
        h = re.sub(r'<hh:charProperties itemCnt="(\d+)"', lambda mm: f'<hh:charProperties itemCnt="{int(mm.group(1)) + 1}"', h, count=1)
        self.header_raw = h
        self._header_changed = True
        self._cp_cache[key] = str(new_id)
        return str(new_id)

    def mark(self, key, level):
        """level: 'red'(불일치·오류) | 'yellow'(확인 필요)"""
        it = self.item(key)
        if it is None:
            return False
        run = None
        if it.field:
            tl = self._field_texts(it.field)
            if tl:
                run = tl[0][1]
        elif it._t is not None and not isinstance(it._t, tuple):
            run = self._parent.get(it._t)
        if run is None or run.tag != T["run"]:
            return False
        base = run.get("charPrIDRef", "0")
        if level == "red":
            nid = self._color_charpr(base, color=config.MARK_RED)
        else:
            nid = self._color_charpr(base, shade=config.MARK_YELLOW_SHADE)
        if nid:
            run.set("charPrIDRef", nid)
            return True
        return False

    # ── 저장 ──────────────────────────────────────────
    def to_bytes(self):
        import io
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


def table_grids(doc):
    """원본으로 쓰는 hwpx(팀 제출본)의 표를 엑셀 시트처럼 [{(r,c): 값}] 로 돌려준다."""
    grids = []
    for tb in doc.tables:
        cells = {}
        texts = {}
        for key in tb["cells"]:
            it = doc.item(key)
            if it and it.value is not None and it.k == 0:
                cells[(it.row, it.col)] = (it.value, it.dec)
        for b in doc.blocks:
            if b["type"] == "table" and b["ti"] == tb["ti"]:
                for row in b["rows"]:
                    for c in row:
                        texts[(c["r"], c["c"])] = "".join(p["text"] for p in c["pieces"])
        grids.append({"name": f"표{tb['ti'] + 1}", "title": tb["title"], "cells": cells, "texts": texts,
                      "nrow": tb["nrow"], "ncol": tb["ncol"]})
    body = {}
    btexts = {}
    for it in doc.items:
        if it.kind == "para" and it.value is not None:
            body[(it.para, it.k)] = (it.value, it.dec)
            btexts[(it.para, it.k)] = it.context[:60]
    if body:
        grids.append({"name": "본문", "title": "본문 숫자", "cells": body, "texts": btexts,
                      "nrow": max(r for r, _ in body) + 1, "ncol": max(c for _, c in body) + 1})
    return grids
