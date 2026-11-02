# -*- coding: utf-8 -*-
"""[검증 엔진 ⑦] 표 내부 점검: 합계 행·열, 비율(%) 열을 다시 계산한다."""

from app.common import numbers as N
from app.parts.verify.engine.index import AGREE


class CalcMixin:
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
