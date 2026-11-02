# -*- coding: utf-8 -*-
"""[검증 엔진] Verifier — 표 맞추기·판정·재계산·복사 힌트 조각을 합쳐 문서 전체를 검증한다."""

from app import config
from app.common import numbers as N
from app.parts.verify.engine.table_map import TableMapMixin
from app.parts.verify.engine.judge import JudgeMixin
from app.parts.verify.engine.calc import CalcMixin
from app.parts.verify.engine.clips import ClipHintMixin


class Verifier(TableMapMixin, JudgeMixin, CalcMixin, ClipHintMixin):
    def __init__(self, index, source_names=None, source_roles=None):
        self.index = index
        self.names = source_names or {}
        self.roles = source_roles or {}
        self._cand_cache = {}

    def cands(self, v, dec):
        key = (v, dec)
        if key not in self._cand_cache:
            self._cand_cache[key] = self.index.candidates(v, dec)
        return self._cand_cache[key]


    @staticmethod
    def _para_from_tables(doc, results):
        """본문 숫자가 같은 문서 표의 칸(원본과 이미 일치)과 같은 값이고, 문장에 그 칸의 행 이름이 있으면 일치로 본다.
        (예: '미리군은 1,520건으로 …' ↔ 표 '미리군' 행의 1,520). 노랑을 초록으로만 바꾼다(빨강은 만들지 않음)."""
        good = ("ok", "ok_calc", "single", "ok_user")
        cells = {}
        for it in doc.items:
            if it.kind == "cell" and it.value is not None and it.rowlab and results.get(it.key, {}).get("status") in good:
                cells.setdefault((it.value, it.dec), []).append(it)
        for it in doc.items:
            r = results.get(it.key)
            if it.kind != "para" or not r or r["status"] not in ("unknown", "multi") or r.get("calc"):
                continue
            text = it.context or ""
            hits = [c for c in cells.get((it.value, it.dec), []) if c.rowlab in text and len(c.rowlab) >= 2]
            if hits:
                r["status"] = "ok"
                r["doc_ref"] = {"key": hits[0].key, "label": hits[0].label}
                r["candidates"] = []

    # ── 전체 검증 ──
    def verify(self, doc, clips=None):
        results = {}
        table_maps = {}
        for tb in doc.tables:
            ti = tb["ti"]
            its = [doc.item(k) for k in tb["cells"]]
            cells = [(it, it.row, it.col) for it in its if it and it.k == 0]
            maps = self.map_table(cells)
            table_maps[ti] = maps
            for it in its:
                if it is None:
                    continue
                results[it.key] = self._judge_cell(it, maps)
            self._calc_checks(doc, tb, results)
        for it in doc.items:
            if it.kind == "para":
                results[it.key] = self._judge_single(it)
        text_issues = []
        for b in doc.blocks:
            if b["type"] != "p":
                continue
            for w in N.weekday_issues(b["text"], doc.year):
                text_issues.append({"para": b["para"], "kind": "weekday", "raw": w["raw"], "msg": w["msg"],
                                    "start": w["start"], "end": w["end"]})
            for cl in N.change_claims(b["text"]):
                for it in doc.items:
                    if it.kind == "para" and it.para == b["para"] and it.raw and \
                            b["text"].find(it.raw, max(0, cl["start"] - 2)) == cl["start"]:
                        r = results.get(it.key)
                        if r is None:
                            continue
                        r["calc"] = {"ok": cl["ok"], "msg": cl["msg"], "expected": cl["expected_text"]}
                        r["candidates"] = []          # 증감률은 계산으로 확인하므로 같은 값 검색 결과는 의미 없음
                        if cl["ok"]:
                            if r["status"] in ("unknown", "multi", "single"):
                                r["status"] = "ok_calc"
                        else:
                            r["status"] = "calc"
                            r["fix"] = cl["expected_text"].rstrip("%p").rstrip("%")
                        break
        self._para_from_tables(doc, results)
        if clips:
            self._clip_hints(doc, results, clips)
        for k, r in results.items():
            r["status_text"] = config.STATUS.get(r["status"], (r["status"], ""))[0]
        return {"items": results, "text_issues": text_issues,
                "tables": {ti: [{"gid": m["gid"], "sid": self.index.groups[m["gid"]]["sid"],
                                 "sheet": self.index.groups[m["gid"]]["sheet"], "orient": m["orient"],
                                 "support": m["support"]} for m in maps] for ti, maps in table_maps.items()}}

