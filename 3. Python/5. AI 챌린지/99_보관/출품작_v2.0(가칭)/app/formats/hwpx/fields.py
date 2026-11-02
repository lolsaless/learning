# -*- coding: utf-8 -*-
"""[한글 파일] 숫자를 누름틀(이름표 붙은 입력칸)로 감싸고, 누름틀 값을 읽고 바꾼다."""
import xml.etree.ElementTree as ET

from app import config
from app.formats.hwpx.base import T, CLICK_FIELD_ID, _idgen


class FieldMixin:
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

