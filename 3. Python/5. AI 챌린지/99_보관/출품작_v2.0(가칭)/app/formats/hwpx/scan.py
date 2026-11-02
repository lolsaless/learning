# -*- coding: utf-8 -*-
"""[한글 파일] 본문 문단과 표에서 숫자 칸(Item)을 찾고, 화면에 그릴 블록을 만든다."""
from app.common import numbers as N
from app.formats.hwpx.base import T, Item, clean_name


class ScanMixin:
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

