"""보고서 저장 — 비교 결과(dict)를 CSV(엑셀용) 또는 단독 HTML 파일로 만든다.

새 형식(예: 엑셀 xlsx, 워드)을 추가하려면 이 파일에 함수를 만들고
server/routes.py 의 EXPORTERS 에 등록한다.
"""
from __future__ import annotations

import csv
import html
import io
import time
from typing import Any, Dict

from .. import APP_NAME, VERSION


def comparison_csv(res: Dict[str, Any]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["번호", "종류", "위치", "구역(제목)", "쪽(추정,이전)", "쪽(추정,새)", "요약", "이전 내용", "새 내용",
                "서식 변경", "꼬리표"])
    for c in res["changes"]:
        fmt = " / ".join(f"‘{f['text']}’ {', '.join(f['details'])}" for f in c["format"])
        fmt = " / ".join(x for x in [fmt] + c["notes"] if x)
        w.writerow([c["id"], c["label"], c["location"], c["context"], c["page_a"] or "", c["page_b"] or "",
                    c["summary"], c["old_text"], c["new_text"], fmt, ",".join(c["tags"])])
    return ("﻿" + buf.getvalue()).encode("utf-8")      # BOM: 엑셀에서 한글 깨짐 방지


def history_csv(hist: Dict[str, Any]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    vers = hist["versions"]
    w.writerow(["번호", "구분", "위치", "변경 횟수"] + [f"v{v['no']} {v['name']}" for v in vers])
    for n, c in enumerate(hist["chains"], 1):
        w.writerow([n, c["kind_label"], c["location"], c["n_changes"]] +
                   [("(없음)" if t is None else t) for t in c["texts"]])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _segments_html(segs) -> str:
    out = []
    for s in segs:
        t = html.escape(s["text"]).replace("\n", "⏎<br>")
        if s["op"] == "delete":
            out.append(f"<del>{t}</del>")
        elif s["op"] == "insert":
            out.append(f"<ins>{t}</ins>")
        else:
            out.append(t)
    return "".join(out)


_CSS = """
body{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;margin:24px;color:#1f2933;background:#fff}
h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 8px}
.meta{color:#52606d;font-size:13px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid #d9e2ec;padding:6px 8px;vertical-align:top;text-align:left}
th{background:#f0f4f8}
del{background:#ffe3e3;color:#c92a2a;text-decoration:line-through}
ins{background:#d3f9d8;color:#2b8a3e;text-decoration:none;border-bottom:2px solid #2b8a3e}
.tag{display:inline-block;padding:0 6px;border-radius:8px;background:#e4e7eb;font-size:11px;margin-right:2px}
.t-modified{color:#d97706}.t-added{color:#2b8a3e}.t-deleted{color:#c92a2a}.t-format{color:#6741d9}
.note{color:#6741d9;font-size:12px}
"""


def comparison_html(res: Dict[str, Any]) -> bytes:
    a, b = res["a"], res["b"]
    rows = []
    for c in res["changes"]:
        notes = [f"‘{html.escape(f['text'])}’ {html.escape(', '.join(f['details']))}" for f in c["format"]]
        notes += [html.escape(n) for n in c["notes"]]
        tags = "".join(f"<span class=tag>{html.escape(t)}</span>" for t in c["tags"])
        rows.append(
            f"<tr><td>{c['id']}</td><td class='t-{c['type']}'><b>{c['label']}</b></td>"
            f"<td>{html.escape(c['location'])}<br><span class=meta>{html.escape(c['context'])}</span></td>"
            f"<td>{_segments_html(c['segments'])}"
            + (f"<div class=note>{'<br>'.join(notes)}</div>" if notes else "")
            + f"</td><td>{tags}</td></tr>")
    meta = "".join(f"<tr><td>{html.escape(m['field'])}</td><td>{html.escape(m['a'])}</td>"
                   f"<td>{html.escape(m['b'])}</td></tr>" for m in res["meta_changes"])
    body = f"""<!doctype html><html lang=ko><head><meta charset=utf-8>
<title>HWPX 비교 보고서</title><style>{_CSS}</style></head><body>
<h1>HWPX 비교 보고서</h1>
<div class=meta>{APP_NAME} v{VERSION} · 작성 {time.strftime('%Y-%m-%d %H:%M')}</div>
<h2>대상</h2>
<table><tr><th></th><th>파일</th><th>문서 수정일</th><th>마지막 저장자</th></tr>
<tr><td>이전(A)</td><td>{html.escape(a['name'])}</td><td>{html.escape(a['meta'].get('ModifiedDate', ''))}</td><td>{html.escape(a['meta'].get('lastsaveby', ''))}</td></tr>
<tr><td>새(B)</td><td>{html.escape(b['name'])}</td><td>{html.escape(b['meta'].get('ModifiedDate', ''))}</td><td>{html.escape(b['meta'].get('lastsaveby', ''))}</td></tr></table>
<h2>요약: {html.escape(res['headline'])}</h2>
{('<table><tr><th>문서 정보</th><th>A</th><th>B</th></tr>' + meta + '</table>') if meta else ''}
<h2>변경 목록</h2>
<table><tr><th>#</th><th>종류</th><th>위치</th><th>내용 (<del>삭제</del> <ins>추가</ins>)</th><th>꼬리표</th></tr>
{''.join(rows) or '<tr><td colspan=5>변경 없음</td></tr>'}</table>
</body></html>"""
    return body.encode("utf-8")


def history_html(hist: Dict[str, Any]) -> bytes:
    vers = hist["versions"]
    head = "".join(f"<th>v{v['no']}<br><span class=meta>{html.escape(v['name'])}<br>{html.escape(v['modified'])}</span></th>" for v in vers)
    rows = []
    for n, c in enumerate(hist["chains"], 1):
        cells = []
        for k, t in enumerate(c["texts"]):
            changed = k > 0 and c["steps"][k - 1] not in ("same", "")
            style = " style='background:#fff4e6'" if changed else ""
            cells.append(f"<td{style}>{'<i class=meta>(없음)</i>' if t is None else html.escape(t)}</td>")
        rows.append(f"<tr><td>{n}</td><td><b>{c['kind_label']}</b></td><td>{html.escape(c['location'])}</td>{''.join(cells)}</tr>")
    steps = "".join(f"<li>v{s['from']} → v{s['to']}: {html.escape(s['headline'])}</li>" for s in hist["steps"])
    body = f"""<!doctype html><html lang=ko><head><meta charset=utf-8>
<title>HWPX 변경 이력 보고서</title><style>{_CSS}</style></head><body>
<h1>HWPX 변경 이력 보고서</h1>
<div class=meta>{APP_NAME} v{VERSION} · 작성 {time.strftime('%Y-%m-%d %H:%M')} · 버전 {len(vers)}개</div>
<h2>단계별 요약</h2><ul>{steps}</ul>
<h2>이력 추적표 (주황 칸 = 그 버전에서 바뀜)</h2>
<table><tr><th>#</th><th>구분</th><th>위치</th>{head}</tr>{''.join(rows) or '<tr><td>변경 없음</td></tr>'}</table>
</body></html>"""
    return body.encode("utf-8")
