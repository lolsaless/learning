# -*- coding: utf-8 -*-
"""[검증 엔진 ⑥] 맞춘 위치의 원본 값과 문서 값을 비교해 칸마다 상태(일치·불일치·충돌…)를 정한다."""

from app import config
from app.common import numbers as N
from app.parts.verify.engine.index import AGREE, DISAGREE, _relation, scale_label


class JudgeMixin:
    def _opinion(self, gid, R, C, s, it):
        sv = self.index.value(gid, R, C)
        if sv is None:
            return None
        v, sdec = sv
        rel = _relation(self.index, it.value, it.dec, v, sdec, s)
        g = self.index.groups[gid]
        exp_x = v * s
        if rel == "unit":
            for s2, _ in config.UNIT_SCALES:
                if N.close(v * s2, it.value, it.dec):
                    break
        return {"sid": g["sid"], "gid": gid, "sheet": g["sheet"], "r": R, "c": C, "ref": self.index.describe(gid, R, C),
                "source": self.names.get(g["sid"], g["sid"]), "role": self.roles.get(g["sid"], ""),
                "relation": rel, "scale": s, "scale_label": scale_label(s),
                "expected": exp_x, "expected_text": N.fmt(exp_x, it.dec, comma=bool(it.comma) or abs(exp_x) >= 1000),
                "source_text": self.index.text(gid, R, C)}

    def _judge_cell(self, it, maps):
        res = {"key": it.key, "value": it.value, "raw": it.raw, "opinions": [], "candidates": [], "calc": None}
        if it.value is None:
            res["status"] = "empty"
            return res
        for m in maps:
            hr, hc = it.row, it.col
            if hc not in m["colmap"] or hr not in m["rowmap"]:
                continue
            C, s = m["colmap"][hc]
            R = m["rowmap"][hr]
            if m["orient"] == "T":
                R, C = C, R
            op = self._opinion(m["gid"], R, C, s, it)
            if op:
                res["opinions"].append(op)
        self._status_from_opinions(it, res)
        return res

    def _status_from_opinions(self, it, res):
        # 원본(엑셀)을 팀 제출본보다 앞에 둔다
        res["opinions"].sort(key=lambda o: (o["role"] != "원본", o["source"]))
        rels = [o["relation"] for o in res["opinions"]]
        agree = [r for r in rels if r in AGREE]
        dis = [r for r in rels if r in DISAGREE]
        if agree and dis:
            res["status"] = "conflict"
        elif dis:
            res["status"] = "unit" if "unit" in dis else "mismatch"
            exp = [o for o in res["opinions"] if o["relation"] in DISAGREE]
            res["fix"] = exp[0]["expected_text"]
        elif agree:
            res["status"] = "ok"
        else:
            self._single_into(it, res)

    COUNT_UNITS = ("건", "명", "회", "대", "개", "곳", "개소", "종", "점")

    def _single_into(self, it, res):
        cs = self.cands(it.value, it.dec)
        lst = []
        seen = set()
        exact_only = it.dec == 0 and (it.unit in self.COUNT_UNITS or it.kind == "para")
        for gid, R, C, s, ex in cs:
            if exact_only and (s != 1.0 or not N.exact(self.index.value(gid, R, C)[0], it.value)):
                continue
            op = self._opinion(gid, R, C, s, it)
            if not op or op["relation"] not in AGREE:
                continue
            k = (gid, R, C)
            if k in seen:
                continue
            seen.add(k)
            lst.append(op)
        lst.sort(key=lambda o: (o["relation"] != "match", o["scale"] != 1.0, o["role"] != "원본", o["source"]))
        res["candidates"] = lst[:12]
        res["n_candidates"] = len(lst)
        digits = len(it.raw.replace(",", "").replace(".", "").replace("-", "").lstrip("0")) if it.raw else 0
        if not lst:
            res["status"] = "unknown"
        elif len(lst) == 1 or len(set((o["sid"], o["sheet"]) for o in lst)) == 1 and len(lst) <= 2:
            res["status"] = "single"
        elif digits >= 3 and len(set(o["expected_text"] for o in lst)) == 1 and len(lst) <= 8:
            res["status"] = "single"     # 자릿수가 많은 같은 값이 여러 원본에 있음(취합 과정의 정상 복사)
        else:
            res["status"] = "multi"

    def _judge_single(self, it):
        res = {"key": it.key, "value": it.value, "raw": it.raw, "opinions": [], "candidates": [], "calc": None}
        if it.value is None:
            res["status"] = "empty"
            return res
        self._single_into(it, res)
        return res

    # ── 합계·비율 다시 계산 ──
