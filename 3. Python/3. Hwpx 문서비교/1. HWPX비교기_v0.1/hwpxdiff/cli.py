"""명령줄 진입점.

    python HWPX비교기.py                         대시보드 실행 (브라우저 자동 열림)
    python HWPX비교기.py --folder D:\\문서         폴더의 HWPX 를 미리 넣고 대시보드 실행
    python HWPX비교기.py a.hwpx b.hwpx c.hwpx    파일을 미리 넣고 대시보드 실행
    python HWPX비교기.py a.hwpx b.hwpx --report  화면 없이 결과를 글자로 출력
    python HWPX비교기.py ... --html 결과.html     화면 없이 보고서 저장 (--csv, --json 도 가능)
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import APP_NAME, VERSION, config
from .service import Workspace


def _print_report(ws: Workspace) -> None:
    hist = ws.history()
    vers = hist["versions"]
    print(f"\n[{APP_NAME} v{VERSION}] 버전 {len(vers)}개 (문서 수정일 순)")
    for v in vers:
        print(f"  v{v['no']}  {v['modified'] or '-':20}  {v['name']}")
    for s in hist["steps"]:
        print(f"\n■ v{s['from']} → v{s['to']} : {s['headline']}")
        res = ws.compare(s["a"], s["b"])
        for c in res["changes"]:
            print(f"  [{c['label']}] {c['location']}  {c['summary']}")
            for f in c["format"]:
                print(f"        서식 ‘{f['text']}’ {', '.join(f['details'])}")
            for n in c["notes"]:
                print(f"        {n}")
    if len(vers) > 2 and hist["chains"]:
        print(f"\n■ 전체 이력: " + ", ".join(f"{hist['kind_labels'][k]} {n}" for k, n in hist["counts"].items() if k != "total"))
        for c in hist["chains"]:
            texts = " | ".join("(없음)" if t is None else t for t in c["texts_short"])
            print(f"  [{c['kind_label']}] {c['location']}: {texts}")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="HWPX비교기", description=APP_NAME)
    p.add_argument("files", nargs="*", help="비교할 .hwpx 파일들")
    p.add_argument("--folder", help="이 폴더의 .hwpx 를 모두 넣기")
    p.add_argument("--recursive", action="store_true", help="하위 폴더까지 찾기")
    p.add_argument("--order", choices=["modified", "name"], default="modified", help="버전 순서 기준")
    p.add_argument("--report", action="store_true", help="화면 없이 결과를 출력")
    p.add_argument("--html", help="화면 없이 이력 보고서(HTML) 저장")
    p.add_argument("--csv", help="화면 없이 이력 보고서(CSV) 저장")
    p.add_argument("--json", help="화면 없이 이력 결과(JSON) 저장")
    p.add_argument("--port", type=int, default=config.PORT)
    p.add_argument("--no-browser", action="store_true", help="브라우저 자동 열기 안 함")
    args = p.parse_args(argv)

    ws = Workspace()
    ws.order_mode = args.order
    if args.folder:
        ws.scan_folder(args.folder, args.recursive)
    for f in args.files:
        ws.submit_path(f)

    headless = args.report or args.html or args.csv or args.json
    if headless:
        ws.wait()
        for it in ws.status()["items"]:
            if it["status"] == "error":
                print(f"  해석 실패: {it['name']} — {it['error']}", file=sys.stderr)
        if len(ws.ready_docs()) < 2:
            print("비교하려면 HWPX 파일이 2개 이상 필요합니다.", file=sys.stderr)
            return 1
        from .export import history_csv, history_html
        if args.report:
            _print_report(ws)
        if args.html:
            open(args.html, "wb").write(history_html(ws.history()))
            print(f"저장: {args.html}")
        if args.csv:
            open(args.csv, "wb").write(history_csv(ws.history()))
            print(f"저장: {args.csv}")
        if args.json:
            with open(args.json, "w", encoding="utf-8") as fp:
                json.dump(ws.history(), fp, ensure_ascii=False, indent=1)
            print(f"저장: {args.json}")
        return 0

    from .server import run_server
    run_server(ws, port=args.port, open_browser=not args.no_browser)
    return 0
