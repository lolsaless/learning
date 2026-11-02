# -*- coding: utf-8 -*-
"""[검증 엔진 ②③④⑤] 문서 표 하나를 원본의 어느 블록(시트·열·행·배율)과 맞출지 투표로 정한다."""
from collections import defaultdict

from app import config


class TableMapMixin:
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
        if not results and common:
            # 마지막 수단: 작은 정수처럼 흔한 값만 있는 표. 흔한 값도 넣어 다시 투표하되,
            # 표 대부분(60% 이상)이 정확히 같은 값으로 한 덩어리(흩어짐 1.5 이하)에 맞을 때만 인정한다.
            for (gid, o), lst in by_g.items():
                res = self._fit(gid, o, lst, set(), n_in_col)
                if res and res["support"] >= 0.6 * len(data) and res["exact"] >= 0.9 * res["support"] \
                        and res["spread"] <= 1.5:
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
        for r in kept:
            self._fill_rows_by_label(r, data)
        return kept

    @staticmethod
    def _norm_label(s):
        return "".join(ch for ch in str(s or "") if not ch.isspace()).replace("·", "")

    def _fill_rows_by_label(self, m, data):
        """⑤-보조: 숫자로 못 맞춘 문서 행을, 원본에서 이름이 똑같은 행(한 곳뿐일 때만)과 연결한다.
        한 행에 숫자가 1~2개뿐이고 그중 하나가 틀리면 숫자만으로는 행을 정할 수 없기 때문이다."""
        g = self.index.groups.get(m["gid"])
        if not g or not m["colmap"]:
            return
        texts = g.get("texts") or {}
        used = set(m["rowmap"].values())
        want = {}
        for it, hr, hc in data:
            if hr not in m["rowmap"] and it.rowlab:
                want[hr] = self._norm_label(it.rowlab)
        if not want:
            return
        # 원본에서 '줄 번호 → 그 줄의 글자들' (뒤집힌 표는 원본 열이 문서 행)
        lines = defaultdict(set)
        for (r, c), t in texts.items():
            key = c if m["orient"] == "T" else r
            lines[key].add(self._norm_label(t))
        for hr, lab in want.items():
            hits = [k for k, labs in lines.items() if lab in labs and k not in used]
            if len(hits) == 1:
                m["rowmap"][hr] = hits[0]
                used.add(hits[0])
                m.setdefault("label_rows", []).append(hr)

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

