# -*- coding: utf-8 -*-
"""원본 대조 엔진.

방법 요약(이름이 아니라 '숫자가 놓인 모양'으로 출처를 찾는다)
 ① 색인   : 모든 원본의 숫자 칸을 값 순서로 정렬해 둔다(배율별: 그대로·÷1,000·÷1,000,000·×1,000·×100).
 ② 후보   : 문서 숫자 하나마다 반올림 범위 안에 드는 원본 칸을 찾는다.
 ③ 열 맞추기: 문서 표의 한 열에 있는 숫자들이 원본의 어느 열(배율 포함)에 몰려 있는지 투표한다.
            표가 행·열이 뒤바뀌어 있을 수 있으므로 '그대로'와 '뒤집기' 두 방향을 모두 시험한다.
 ④ 행 맞추기: 맞춘 열 안에서 문서의 각 행이 원본의 어느 행인지 투표한다.
 ⑤ 보충    : 맞춘 행·열 정보로 아직 못 맞춘 열·행을 다시 맞춘다(작은 숫자처럼 흔한 값도 여기서 쓰임).
 ⑥ 판정    : 맞춘 위치의 원본 값과 문서 값을 비교한다(일치·반올림·단위환산·단위 다름·불일치).
 ⑦ 내부 점검: 합계 행·열, 비율(%) 열, 증감률 문장, 날짜 요일을 다시 계산한다.
"""
import bisect
from collections import defaultdict

from app import config
from app.core import numbers as N
from app.core.xlsx_io import ref as a1ref

AGREE = ("match", "round", "scale")
DISAGREE = ("mismatch", "unit")


class SourceIndex:
    def __init__(self):
        self.groups = {}       # gid -> dict(sid, sheet, kind, cells{(r,c):(v,dec)}, texts{(r,c):str})
        self._built = False
        self._arr = {}

    def add_workbook(self, sid, wb):
        for sh in wb.sheets:
            cells, texts = {}, {}
            for (r, c), cell in sh.cells.items():
                texts[(r, c)] = cell.text
                if cell.kind == "n":
                    cells[(r, c)] = (cell.v, None)
                elif cell.kind == "s":
                    tok = N.parse_cell(cell.text)
                    if tok and tok["unit"] not in ("년",):
                        cells[(r, c)] = (tok["value"], tok["dec"])
            gid = f"{sid}|{sh.name}"
            self.groups[gid] = {"sid": sid, "sheet": sh.name, "kind": "xlsx", "cells": cells, "texts": texts,
                                "nrow": sh.maxr + 1, "ncol": sh.maxc + 1}
        self._built = False

    def add_grids(self, sid, grids):
        for g in grids:
            gid = f"{sid}|{g['name']}"
            self.groups[gid] = {"sid": sid, "sheet": g["name"], "kind": "hwpx", "cells": g["cells"],
                                "texts": g["texts"], "nrow": g["nrow"], "ncol": g["ncol"], "title": g.get("title", "")}
        self._built = False

    def remove_source(self, sid):
        for gid in [g for g, v in self.groups.items() if v["sid"] == sid]:
            del self.groups[gid]
        self._built = False

    def build(self):
        self._arr = {}
        for s, _ in config.UNIT_SCALES:
            rows = []
            for gid, g in self.groups.items():
                for (r, c), (v, d) in g["cells"].items():
                    rows.append((v * s, gid, r, c, v, d))
            rows.sort(key=lambda x: x[0])
            self._arr[s] = ([x[0] for x in rows], rows)
        self._built = True

    def candidates(self, v, dec, limit=4000):
        if not self._built:
            self.build()
        out = []
        t = N.tol(dec)
        for s, _ in config.UNIT_SCALES:
            keys, rows = self._arr[s]
            lo = bisect.bisect_left(keys, v - t - 1e-9 * max(1, abs(v)))
            hi = bisect.bisect_right(keys, v + t + 1e-9 * max(1, abs(v)))
            for x in rows[lo:hi][:limit]:
                sv, gid, r, c, raw, sdec = x
                # 원본도 반올림된 글자(한글 문서)라면 자릿수를 맞춰 비교
                if sdec is not None and sdec < dec:
                    if not N.close(v, sv, sdec):
                        continue
                ex = N.exact(sv, v)
                # 강한 근거: 정확히 같음 / 단위 환산 / 소수 자리 반올림(2.338→2.3)
                # 약한 근거: 소수 값(32.8)을 정수(33)로 반올림해야 맞는 경우 → 우연일 가능성이 큼
                if s < 1.0:
                    strong = abs(raw) >= 1000              # 원→천원 같은 큰 정수 환산
                elif s > 1.0:
                    strong = (s == 1000.0 and abs(raw) >= 1) or (s == 100.0 and abs(raw) <= 1.5 and dec >= 1)
                else:
                    strong = ex or dec > 0
                if not (ex or strong) and s != 1.0:
                    continue                                # 약한 배율 일치는 후보에서 제외

                out.append((gid, r, c, s, strong))
        return out

    def describe(self, gid, r, c):
        g = self.groups[gid]
        if g["kind"] == "xlsx":
            return f"{g['sheet']}!{a1ref(r, c)}"
        if g["sheet"] == "본문":
            return f"본문 {r}번째 문단"
        return f"{g['sheet']} {r + 1}행 {c + 1}열"

    def value(self, gid, r, c):
        g = self.groups.get(gid)
        if not g:
            return None
        return g["cells"].get((r, c))

    def text(self, gid, r, c):
        g = self.groups.get(gid)
        return g["texts"].get((r, c), "") if g else ""

    def preview(self, gid, r, c, rad_r=3, rad_c=3):
        """원본 칸 주변 미리보기(격자)."""
        g = self.groups.get(gid)
        if not g:
            return None
        r0, r1 = max(0, r - rad_r), r + rad_r
        c0, c1 = max(0, c - rad_c), c + rad_c
        # 머리글을 보여 주기 위해 위쪽 첫 글자 행도 함께
        grid = []
        for rr in range(r0, r1 + 1):
            grid.append([g["texts"].get((rr, cc), "") for cc in range(c0, c1 + 1)])
        return {"r0": r0, "c0": c0, "grid": grid, "hit": [r - r0, c - c0], "kind": g["kind"], "sheet": g["sheet"],
                "cols": [a1ref(0, cc)[:-1] for cc in range(c0, c1 + 1)] if g["kind"] == "xlsx" else [str(cc + 1) for cc in range(c0, c1 + 1)]}


def _relation(index, v, dec, sv, sdec, s):
    """원본 값 sv(배율 s 적용 전)과 문서 값 v의 관계."""
    x = sv * s
    if sdec is not None and sdec < dec:
        same = N.close(v, x, sdec)
    else:
        same = N.close(x, v, dec)
    if same:
        if s != 1.0:
            return "scale"
        return "match" if N.exact(x, v) or sdec is not None else "round"
    for s2, _ in config.UNIT_SCALES:
        if s2 != s and N.close(sv * s2, v, dec):
            return "unit"
    return "mismatch"


def scale_label(s):
    for s2, lab in config.UNIT_SCALES:
        if s2 == s:
            return lab
    return f"×{s}"


class Verifier:
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

    # ── 표 하나를 원본 블록과 맞추기 ──
    def map_table(self, cells):
        """cells: [(item, hr, hc)] → 원본별 맞춤 결과 목록"""
        data = [(it, hr, hc) for it, hr, hc in cells if it.value is not None]
        if not data:
            return []
        by_g = defaultdict(list)    # (gid, orient) -> [(hr, hc, R, C, s, ex, key)]
        common = set()
        for it, hr, hc in data:
            cs = self.cands(it.value, it.dec)
            exact_n = sum(1 for x in cs if x[4])
            if exact_n > config.COMMON_VALUE_LIMIT or (exact_n == 0 and len(cs) > config.COMMON_VALUE_LIMIT):
                common.add(it.key)
            has_exact = {(x[0]) for x in cs if x[4]}
            for gid, R, C, s, ex in cs:
                # 같은 시트에 정확히 같은 값이 있으면 반올림 후보는 투표에서 뺀다
                if not ex and gid in has_exact:
                    continue
                by_g[(gid, "N")].append((hr, hc, R, C, s, ex, it.key))
                by_g[(gid, "T")].append((hr, hc, C, R, s, ex, it.key))   # 뒤집기: 문서 행↔원본 열
        n_in_col = defaultdict(int)
        for it, hr, hc in data:
            n_in_col[hc] += 1
        results = []
        for (gid, o), lst in by_g.items():
            res = self._fit(gid, o, lst, common, n_in_col)
            if res:
                results.append(res)
        if not results:
            return []
        results.sort(key=lambda x: (-x["support"], -x["exact"], x["spread"]))
        best = results[0]["support"]
        best_exact = max(r["exact"] / max(1, r["support"]) for r in results)
        if best_exact >= 0.8:
            # 정확히 같은 값으로 맞은 블록이 있으면, 반올림으로만 맞은 블록(우연일 가능성 큼)은 버린다
            results = [r for r in results if r["exact"] >= 0.5 * r["support"]]
        kept, covered, per_sid = [], set(), defaultdict(int)
        for r in results:
            sid = self.index.groups[r["gid"]]["sid"]
            if r["support"] < config.MIN_BLOCK_SUPPORT and r["support"] < len(data):
                continue
            # 우연히 맞은 값(큰 원자료 시트 여기저기에 흩어진 칸)을 걸러 낸다
            if r["spread"] > 3.0 and (r["support"] < 0.9 * best or r["exact"] < 0.8 * r["support"]
                                      or len(r["colmap"]) < 2 and len(r["rowmap"]) > 2):
                continue
            new = r["cells"] - covered
            if r["support"] <= 0.5 * best:
                # 작은 블록은 '아직 못 맞춘 칸'을 정확한 값으로 채워 줄 때만 인정
                if r["spread"] > 1.5 or len(new) < config.MIN_BLOCK_SUPPORT or r["exact"] < 0.8 * r["support"]:
                    continue
            if per_sid[sid] and len(new) < config.MIN_BLOCK_SUPPORT:
                continue
            kept.append(r)
            per_sid[sid] += 1
            covered |= r["cells"]
        return kept

    def _fit(self, gid, o, lst, common, n_in_col):
        def colvotes(filter_fn):
            v = defaultdict(lambda: defaultdict(set))
            for hr, hc, R, C, s, ex, key in lst:
                if filter_fn(hr, hc, R, C, s, ex, key):
                    v[hc][(C, s)].add(hr)
            return v
        # 1단계: 흔하지 않은 값(정확히 같은 값 우선)으로 열 맞추기
        need_c = lambda hc: min(config.MIN_LINE_SUPPORT, n_in_col[hc])
        colmap = self._assign(colvotes(lambda hr, hc, R, C, s, ex, key: ex and key not in common), need_c)
        if not colmap:
            colmap = self._assign(colvotes(lambda hr, hc, R, C, s, ex, key: key not in common), need_c)
        if not colmap:
            return None
        rowmap = {}
        for _ in range(3):
            # 2단계: 맞춘 열 안에서 행 맞추기(흔한 값 포함)
            rowv = defaultdict(lambda: defaultdict(set))
            ncols_row = defaultdict(int)
            for hr, hc, R, C, s, ex, key in lst:
                if hc in colmap and colmap[hc] == (C, s):
                    rowv[hr][R].add(hc)
            for hr in rowv:
                ncols_row[hr] = len({hc for hr2, hc, *_ in lst if hr2 == hr and hc in colmap})
            rowmap = self._assign(rowv, lambda hr: min(config.MIN_LINE_SUPPORT, max(1, ncols_row[hr])))
            # 3단계: 맞춘 행으로 남은 열 보충
            used_c = {v[0] for v in colmap.values()}
            add = self._assign(colvotes(lambda hr, hc, R, C, s, ex, key: hc not in colmap and rowmap.get(hr) == R),
                               need_c, taken=used_c)
            if not add:
                break
            colmap.update(add)
        cells, exact = set(), set()
        for hr, hc, R, C, s, ex, key in lst:
            if hc in colmap and hr in rowmap and colmap[hc] == (C, s) and rowmap[hr] == R:
                cells.add(key)
                if ex:
                    exact.add(key)
        if len(cells) < 2:
            return None
        rvals = sorted(set(rowmap.values()))
        cvals = sorted(set(v[0] for v in colmap.values()))
        spread = max((rvals[-1] - rvals[0] + 1) / max(1, len(rvals)), (cvals[-1] - cvals[0] + 1) / max(1, len(cvals)))
        return {"gid": gid, "orient": o, "colmap": colmap, "rowmap": rowmap, "support": len(cells), "cells": cells,
                "spread": spread, "exact": len(exact)}

    @staticmethod
    def _assign(votes, need, taken=None):
        """투표 결과에서 겹치지 않게(한 원본 줄은 문서 줄 하나에만) 고른다."""
        pairs = []
        for h, opts in votes.items():
            for target, sup in opts.items():
                pairs.append((len(sup), h, target))
        pairs.sort(key=lambda x: (-x[0], str(x[1]), str(x[2])))
        out, used = {}, set(taken or ())
        for sup, h, target in pairs:
            key = target[0] if isinstance(target, tuple) else target
            if h in out or key in used:
                continue
            if sup < need(h):
                continue
            out[h] = target
            used.add(key)
        return out

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
        if clips:
            self._clip_hints(doc, results, clips)
        for k, r in results.items():
            r["status_text"] = config.STATUS.get(r["status"], (r["status"], ""))[0]
        return {"items": results, "text_issues": text_issues,
                "tables": {ti: [{"gid": m["gid"], "sid": self.index.groups[m["gid"]]["sid"],
                                 "sheet": self.index.groups[m["gid"]]["sheet"], "orient": m["orient"],
                                 "support": m["support"]} for m in maps] for ti, maps in table_maps.items()}}

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
    def _calc_checks(self, doc, tb, results):
        ti = tb["ti"]
        grid = {}
        for k in tb["cells"]:
            it = doc.item(k)
            if it and it.k == 0:
                grid[(it.row, it.col)] = it
        if not grid:
            return
        rows = sorted(set(r for r, _ in grid))
        cols = sorted(set(c for _, c in grid))
        total_rows = [r for r in rows if any(grid[(r, c)].is_total_row for c in cols if (r, c) in grid)]
        total_cols = [c for c in cols if any(grid[(r, c)].is_total_col for r in rows if (r, c) in grid)]
        ratio_cols = [c for c in cols if any(grid[(r, c)].is_ratio_col for r in rows if (r, c) in grid)]
        avg_cols = [c for c in cols if any(grid[(r, c)].is_avg for r in rows if (r, c) in grid)]

        def setcalc(it, ok, msg, exp, parts=()):
            r = results.get(it.key)
            if r is None:
                return
            prev = r.get("calc")
            if prev and not prev["ok"]:
                return
            bad_parts = [p for p in parts if results.get(p.key, {}).get("status") in ("mismatch", "unit")]
            if not ok and bad_parts:
                # 구성 칸이 이미 틀렸으면 이 칸의 '고칠 값'은 내지 않는다(연쇄 오류)
                msg += f" — 먼저 '{bad_parts[0].label}' 칸을 확인하세요(그 칸 때문에 생긴 연쇄 차이일 수 있음)"
                exp = None
            r["calc"] = {"ok": ok, "msg": msg, "expected": exp, "chain": bool(bad_parts)}
            if not ok:
                if r["status"] not in ("mismatch", "unit"):
                    r["status"] = "calc"
                    if exp is not None:
                        r.setdefault("fix", exp)
            elif r["status"] in ("unknown", "multi", "single"):
                r["status"] = "ok_calc"

        # 합계 행
        for tr in total_rows:
            body = [r for r in rows if r not in total_rows and r > (max([x for x in total_rows if x < tr], default=-1))]
            if tr < max(rows) and not body:
                body = [r for r in rows if r not in total_rows and r < tr]
            body = [r for r in body if r < tr] or [r for r in rows if r not in total_rows]
            for c in cols:
                if c in ratio_cols or c in avg_cols or (tr, c) not in grid:
                    continue
                tot = grid[(tr, c)]
                if tot.value is None:
                    continue
                parts = [grid[(r, c)] for r in body if (r, c) in grid]
                if not parts or any(p.value is None for p in parts):
                    continue
                s = sum(p.value for p in parts)
                d = tot.dec
                exp = N.fmt(s, d, comma=bool(tot.comma) or abs(s) >= 1000)
                ok = N.close(s, tot.value, d)
                msg = "합계 확인" if ok else f"칸을 더하면 {exp}입니다(문서: {tot.raw})"
                if not ok:
                    # 단위 환산(원→천원)하며 칸마다 반올림하면 합계가 몇 단위 어긋날 수 있다(단수 차이)
                    unit_step = 10 ** -d
                    src_ok = any(o["relation"] in AGREE for o in results.get(tot.key, {}).get("opinions", []))
                    if src_ok and abs(s - tot.value) <= 0.5 * len(parts) * unit_step + 1e-9:
                        ok = True
                        msg = f"칸 합({exp})과 {N.fmt(abs(s - tot.value), d)} 차이 — 반올림(단수) 차이로 보이며 원본 합계와는 일치"
                setcalc(tot, ok, msg, exp, parts)
        # 합계 열
        for tc in total_cols:
            for r in rows:
                if (r, tc) not in grid:
                    continue
                tot = grid[(r, tc)]
                parts = [grid[(r, c)] for c in cols if c != tc and c not in ratio_cols and c not in avg_cols
                         and c not in total_cols and (r, c) in grid]
                if tot.value is None or not parts or any(p.value is None for p in parts):
                    continue
                s = sum(p.value for p in parts)
                ok = N.close(s, tot.value, tot.dec)
                exp = N.fmt(s, tot.dec, comma=bool(tot.comma) or abs(s) >= 1000)
                setcalc(tot, ok, "합계 확인" if ok else f"칸을 더하면 {exp}입니다(문서: {tot.raw})", exp, parts)
        # 비율 열: 같은 행의 두 열 a/b×100 과 맞는 짝을 찾는다
        for rc in ratio_cols:
            others = [c for c in cols if c != rc and c not in ratio_cols]
            best = None
            for a in others:
                for b in others:
                    if a == b:
                        continue
                    n_ok = n_all = 0
                    for r in rows:
                        if (r, rc) in grid and (r, a) in grid and (r, b) in grid:
                            x, y, z = grid[(r, rc)].value, grid[(r, a)].value, grid[(r, b)].value
                            if None in (x, y, z) or z == 0:
                                continue
                            n_all += 1
                            if N.close(y / z * 100, x, grid[(r, rc)].dec):
                                n_ok += 1
                    if n_all >= 2 and n_ok >= max(2, 0.6 * n_all):
                        if best is None or n_ok > best[0]:
                            best = (n_ok, a, b)
            if not best:
                continue
            _, a, b = best
            for r in rows:
                if (r, rc) in grid and (r, a) in grid and (r, b) in grid:
                    x, y, z = grid[(r, rc)], grid[(r, a)], grid[(r, b)]
                    if None in (x.value, y.value, z.value) or z.value == 0:
                        continue
                    e = y.value / z.value * 100
                    ok = N.close(e, x.value, x.dec)
                    exp = N.fmt(e, x.dec)
                    msg = (f"{y.collab} ÷ {z.collab} × 100 확인" if ok else
                           f"{y.collab} ÷ {z.collab} × 100 = {exp}입니다(문서: {x.raw})")
                    setcalc(x, ok, msg, exp, (y, z))

    # ── 클립보드 기록 ──
    def _clip_hints(self, doc, results, clips):
        for it in doc.items:
            if it.value is None:
                continue
            r = results.get(it.key)
            if r is None:
                continue
            for cl in clips:
                for (dr, dc), txt in cl.get("cells", {}).items():
                    tok = N.parse_cell(txt)
                    if tok and N.close(tok["value"], it.value, it.dec):
                        r.setdefault("clips", []).append({
                            "at": cl["at"], "path": cl["path"], "sheet": cl["sheet"],
                            "ref": a1ref(cl["r0"] + dr, cl["c0"] + dc), "text": txt})
                        break
                if len(r.get("clips", [])) >= 3:
                    break
