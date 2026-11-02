# -*- coding: utf-8 -*-
"""내보내기: 출처대장(xlsx) · 검증표시본(hwpx) · 검증보고(html)."""
import os
import html
import datetime

from app import config
from app.formats.xlsx import write_xlsx
from app.formats.hwpx import HwpxDoc

REL = {"match": "일치", "round": "반올림 일치", "scale": "단위 환산 일치", "unit": "단위 다름", "mismatch": "불일치"}
RED = ("mismatch", "unit", "calc")
YELLOW = ("conflict", "unknown", "multi")


def _h(s):
    return {"v": s, "bold": True, "fill": "#DDE6F0", "align": "center", "text": True}


def _t(s):
    return {"v": "" if s is None else str(s), "text": True}


def export_all(ws):
    day = datetime.date.today().strftime("%Y-%m-%d")
    stamp = datetime.datetime.now().strftime("%H%M%S")
    out_dir = os.path.join(ws.folder, config.DIR_EXPORT)
    os.makedirs(out_dir, exist_ok=True)
    doc = ws.doc(fresh=True)
    res = ws.last["items"]
    ver = ws.db.last_version()
    stem = ws.db.meta("stem") or "문서"
    files = {}

    # 1) 출처대장
    rows = [[_h(x) for x in ["번호", "칸 이름(누름틀)", "위치", "문서 값", "상태", "고칠 값", "출처 파일(전체 경로)",
                              "시트·칸", "관계", "원본 값", "확인 방법", "비고"]]]
    n = 0
    for it in doc.items:
        r = res.get(it.key)
        if not r:
            continue
        n += 1
        ops = r.get("opinions") or []
        conf = r.get("confirmed")
        if conf:
            src, ref_, rel, sv, how = conf["source_path"], conf["source_ref"], "확정", "", f"담당자 확정({conf['user']}, {conf['ts']})"
        elif ops:
            o = ops[0]
            src, ref_, rel, sv = o.get("path"), o["ref"], REL.get(o["relation"], o["relation"]), o["source_text"]
            how = "표 블록 자동 대조"
            if len(ops) > 1:
                how += f" (출처 {len(ops)}곳: " + ", ".join(f"{x['source']} {x['ref']}={x['expected_text']}" for x in ops) + ")"
        elif r.get("candidates"):
            o = r["candidates"][0]
            src, ref_, rel, sv = o.get("path"), o["ref"], REL.get(o["relation"], o["relation"]), o["source_text"]
            how = f"같은 값 검색(후보 {r.get('n_candidates', 1)}곳)"
        else:
            src = ref_ = rel = sv = ""
            how = "출처를 찾지 못함"
        note = (r.get("calc") or {}).get("msg") or ""
        rows.append([_t(n), _t(it.key), _t(it.label), _t(it.raw), _t(config.STATUS.get(r["status"], (r["status"],))[0]),
                     _t(r.get("fix")), _t(src), _t(ref_), _t(rel), _t(sv), _t(how), _t(note)])
    for t in ws.last["text_issues"]:
        n += 1
        rows.append([_t(n), _t(""), _t(f"본문 {t['para']}번째 문단"), _t(t["raw"]), _t("날짜·요일 오류"), _t(""), _t(""),
                     _t(""), _t(""), _t(""), _t("달력 계산"), _t(t["msg"])])
    s1 = {"name": "검증결과", "rows": rows, "widths": [6, 28, 34, 14, 18, 12, 60, 16, 12, 12, 30, 40],
          "freeze": (1, 2), "autofilter": True}
    ev = [[_h(x) for x in ["번호", "시각", "작업본 버전", "칸", "위치", "이전 값", "새 값", "방법", "출처 파일", "시트·칸",
                            "출처 파일 고유값(SHA-256 앞 12자)", "사유", "작업자"]]]
    for e in reversed(ws.db.events()):
        ev.append([_t(e["id"]), _t(e["ts"]), _t(f"v{e['ver']:03d}" if e["ver"] else ""), _t(e["slot"]), _t(e["label"]),
                   _t(e["old"]), _t(e["new"]), _t(e["method"]), _t(e["source_path"]), _t(e["source_ref"]),
                   _t((e["source_sha"] or "")[:12]), _t(e["reason"]), _t(e["user"])])
    s2 = {"name": "값 이력", "rows": ev, "widths": [6, 18, 9, 26, 32, 12, 12, 16, 50, 14, 18, 24, 10],
          "freeze": (1, 0), "autofilter": True}
    so = [[_h(x) for x in ["번호", "파일 이름", "구분", "전체 경로", "고유값(SHA-256)", "크기(바이트)", "수정 시각", "등록 시각", "상태"]]]
    for s in ws.db.sources(active_only=False):
        mt = datetime.datetime.fromtimestamp(s["mtime"]).strftime("%Y-%m-%d %H:%M:%S") if s["mtime"] else ""
        st = "등록 해제" if not s["active"] else {"ok": "정상", "fail": "읽기 실패", "missing": "파일 없음"}.get(s["status"], s["status"])
        so.append([_t(s["sid"]), _t(s["name"]), _t(s["role"]), _t(s["path"]), _t(s["sha"]), _t(s["size"]), _t(mt),
                   _t(s["added"]), _t(st)])
    s3 = {"name": "원본 목록", "rows": so, "widths": [6, 34, 8, 70, 66, 12, 18, 18, 10], "freeze": (1, 0), "autofilter": True}
    se = [[_h(x) for x in ["시각", "번호", "파일", "구분", "이전 고유값", "새 고유값", "비고"]]]
    for e in ws.db.source_events():
        se.append([_t(e["ts"]), _t(e["sid"]), _t(e["name"]), _t(e["kind"]), _t((e["old_sha"] or "")[:12]),
                   _t((e["new_sha"] or "")[:12]), _t(e["note"])])
    s4 = {"name": "원본 변경 기록", "rows": se, "widths": [18, 6, 34, 10, 16, 16, 60], "freeze": (1, 0), "autofilter": True}
    vs = [[_h(x) for x in ["버전", "파일", "고유값", "만든 시각", "메모", "작업자"]]]
    for v in ws.db.versions():
        vs.append([_t(f"v{v['ver']:03d}"), _t(v["path"]), _t(v["sha"]), _t(v["created"]), _t(v["note"]), _t(v["user"])])
    s5 = {"name": "작업본 버전", "rows": vs, "widths": [8, 70, 66, 18, 30, 10], "freeze": (1, 0), "autofilter": True}
    p = os.path.join(out_dir, f"출처대장_{stem}_{day}.xlsx")
    if os.path.exists(p):
        p = os.path.join(out_dir, f"출처대장_{stem}_{day}_{stamp}.xlsx")
    write_xlsx(p, [s1, s2, s3, s4, s5])
    files["ledger"] = p

    # 2) 검증표시본(hwpx 사본에 색)
    md = HwpxDoc(ver["path"])
    marked = 0
    for it in md.items:
        r = res.get(it.key)
        if not r:
            continue
        if r["status"] in RED:
            marked += md.mark(it.key, "red")
        elif r["status"] in YELLOW:
            marked += md.mark(it.key, "yellow")
    p2 = os.path.join(out_dir, f"검증표시본_{stem}_v{ver['ver']:03d}_{day}.hwpx")
    if os.path.exists(p2):
        p2 = os.path.join(out_dir, f"검증표시본_{stem}_v{ver['ver']:03d}_{day}_{stamp}.hwpx")
    md.save(p2)
    files["marked"] = p2
    files["marked_count"] = marked

    # 3) 검증보고(html)
    p3 = os.path.join(out_dir, f"검증보고_{stem}_{day}.html")
    if os.path.exists(p3):
        p3 = os.path.join(out_dir, f"검증보고_{stem}_{day}_{stamp}.html")
    with open(p3, "w", encoding="utf-8") as f:
        f.write(_report_html(ws, doc, res, ver))
    files["report"] = p3
    return files


def _report_html(ws, doc, res, ver):
    sm = ws.last["summary"]
    e = html.escape
    issues = []
    for it in doc.items:
        r = res.get(it.key)
        if r and r["status"] in RED + YELLOW:
            ops = r.get("opinions") or r.get("candidates") or []
            src = "<br>".join(f"{e(o['source'])} · {e(o['ref'])} = {e(o['expected_text'])} ({REL.get(o['relation'], '')})"
                              for o in ops[:3]) or "—"
            note = e((r.get("calc") or {}).get("msg") or "")
            issues.append((r["status"], f"<tr class='{r['status']}'><td>{e(it.label)}</td><td class='n'>{e(it.raw or '')}</td>"
                                        f"<td>{e(config.STATUS[r['status']][0])}</td><td class='n'>{e(r.get('fix') or '')}</td>"
                                        f"<td>{src}</td><td>{note}</td></tr>"))
    for t in ws.last["text_issues"]:
        issues.append(("calc", f"<tr class='calc'><td>본문 {t['para']}번째 문단</td><td>{e(t['raw'])}</td><td>날짜·요일 오류</td>"
                               f"<td></td><td>달력 계산</td><td>{e(t['msg'])}</td></tr>"))
    order = {"mismatch": 0, "unit": 1, "calc": 2, "conflict": 3, "unknown": 4, "multi": 5}
    issues.sort(key=lambda x: order.get(x[0], 9))
    srcs = "".join(f"<tr><td>{e(s['sid'])}</td><td>{e(s['name'])}</td><td>{e(s['role'])}</td><td class='p'>{e(s['path'])}</td>"
                   f"<td class='p'>{e(s['sha'][:16])}…</td></tr>" for s in ws.db.sources())
    cnt = lambda *ks: sum(sm.get(k, 0) for k in ks)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>검증보고 — {e(ws.db.meta('target_name') or '')}</title>
<style>
body{{font-family:'Malgun Gothic','맑은 고딕',sans-serif;font-size:13px;margin:24px;color:#222;background:#fff}}
h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:15px;margin:22px 0 8px;border-bottom:2px solid #345;padding-bottom:4px}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #bbb;padding:5px 7px;vertical-align:top}}
th{{background:#DDE6F0}} td.n{{text-align:right;white-space:nowrap}} td.p{{font-size:11px;word-break:break-all}}
tr.mismatch td,tr.unit td,tr.calc td{{background:#FBE3E3}} tr.conflict td,tr.unknown td,tr.multi td{{background:#FFF6CC}}
.k{{display:inline-block;margin-right:14px;padding:6px 10px;border-radius:6px;background:#f2f4f7}}
.k b{{font-size:16px}} .meta{{color:#555}}
@media print{{body{{margin:10mm}} h2{{break-after:avoid}} tr{{break-inside:avoid}}}}
</style></head><body>
<h1>숫자 검증 보고</h1>
<div class="meta">문서: {e(ws.db.meta('target_name') or '')} · 작업본 v{ver['ver']:03d} · 검증 {e(sm.get('at', ''))} · 작업자 {e(ws.user)}</div>
<h2>요약</h2>
<span class="k">검사한 숫자 <b>{sm.get('total', 0)}</b></span>
<span class="k">일치 <b>{cnt('ok', 'ok_calc', 'ok_user', 'single')}</b></span>
<span class="k">불일치·오류 <b>{cnt('mismatch', 'unit', 'calc') + sm.get('text_issues', 0)}</b></span>
<span class="k">확인 필요 <b>{cnt('conflict', 'unknown', 'multi')}</b></span>
<h2>확인할 곳</h2>
<table><tr><th>위치</th><th>문서 값</th><th>상태</th><th>고칠 값</th><th>원본(파일·칸 = 값)</th><th>비고</th></tr>
{''.join(x[1] for x in issues) or '<tr><td colspan=6>없음</td></tr>'}</table>
<h2>대조한 원본</h2>
<table><tr><th>번호</th><th>파일</th><th>구분</th><th>경로</th><th>고유값</th></tr>{srcs}</table>
<p class="meta">※ '일치'는 원본 값을 문서의 표시 자릿수로 반올림했을 때 같다는 뜻입니다. 계산된 값(여러 칸을 더한 값 등)은 원본에 그대로 없으면 '출처 미확인'으로 표시됩니다.</p>
</body></html>"""
