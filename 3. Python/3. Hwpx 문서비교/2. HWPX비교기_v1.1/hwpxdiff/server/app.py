"""로컬 HTTP 서버 — web/ 폴더의 대시보드 파일을 보내고, /api/* 요청을 routes.py 로 넘긴다.

표준 라이브러리 http.server 만 사용 (설치 필요 없음). 127.0.0.1 에만 열리므로 다른 컴퓨터에서는 접속할 수 없다.
"""
from __future__ import annotations

import json
import mimetypes
import os
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import parse_qsl, urlsplit

from .. import config
from ..service import Workspace
from .routes import ROUTES, ApiError, Request

WEB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web"))


def make_handler(ws: Workspace, server_ref: dict):
    class Handler(BaseHTTPRequestHandler):
        server_version = "HwpxDiff"

        def log_message(self, fmt, *args):      # 콘솔을 조용히 (작업 로그는 대시보드에 표시)
            pass

        # ── 공통 응답 ───────────────────────────────
        def _send(self, code: int, body: bytes, ctype: str, extra: Optional[dict] = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _origin_ok(self) -> bool:
            """다른 웹사이트가 이 서버로 요청을 보내지 못하게 막는다."""
            origin = self.headers.get("Origin")
            if not origin:
                return True
            host = self.headers.get("Host", "")
            return urlsplit(origin).netloc == host

        # ── 메서드 ─────────────────────────────────
        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def _dispatch(self, method: str):
            url = urlsplit(self.path)
            if url.path == "/api/shutdown" and method == "POST":
                self._json(200, {"ok": True})
                threading.Thread(target=server_ref["server"].shutdown, daemon=True).start()
                return
            if url.path.startswith("/api/"):
                return self._api(method, url)
            if method == "GET":
                return self._static(url.path)
            self._json(405, {"error": "허용되지 않는 요청"})

        def _api(self, method, url):
            if not self._origin_ok():
                return self._json(403, {"error": "다른 출처의 요청은 받지 않습니다"})
            fn = ROUTES.get((method, url.path))
            if fn is None:
                return self._json(404, {"error": f"없는 API: {url.path}"})
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > config.MAX_UPLOAD_MB * 1024 * 1024:
                return self._json(413, {"error": f"파일이 너무 큽니다 (최대 {config.MAX_UPLOAD_MB}MB)"})
            body = self.rfile.read(length) if length else b""
            req = Request(method=method, path=url.path, query=dict(parse_qsl(url.query)),
                          headers={k.lower(): v for k, v in self.headers.items()}, body=body)
            if body and "json" in self.headers.get("Content-Type", ""):
                try:
                    req.json = json.loads(body.decode("utf-8"))
                except ValueError:
                    return self._json(400, {"error": "JSON 형식 오류"})
            try:
                out = fn(ws, req)
            except ApiError as e:
                return self._json(e.status, {"error": str(e)})
            except Exception as e:                  # 서버가 죽지 않게 하고 화면에 알림
                ws.log(f"서버 오류: {type(e).__name__}: {e}", "error")
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})
            if isinstance(out, tuple):              # 파일 내려받기
                data, ctype, fname = out
                extra = {"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"} if fname else {}
                return self._send(200, data, ctype, extra)
            self._json(200, out)

        def _static(self, path: str):
            rel = "index.html" if path in ("", "/") else path.lstrip("/")
            full = os.path.abspath(os.path.join(WEB_DIR, rel))
            if not full.startswith(WEB_DIR + os.sep) or not os.path.isfile(full):
                return self._json(404, {"error": "파일 없음"})
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            with open(full, "rb") as f:
                self._send(200, f.read(), ctype)

    return Handler


def find_port(host: str, start: int) -> int:
    for port in range(start, start + config.PORT_TRIES):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise OSError(f"{start}~{start + config.PORT_TRIES} 사이에 빈 포트가 없습니다")


def run_server(ws: Optional[Workspace] = None, host: str = config.HOST, port: int = config.PORT,
               open_browser: bool = True) -> None:
    ws = ws or Workspace()
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    port = find_port(host, port)
    ref: dict = {}
    server = ThreadingHTTPServer((host, port), make_handler(ws, ref))
    server.daemon_threads = True
    ref["server"] = server
    url = f"http://{host}:{port}/"
    ws.log(f"서버 시작: {url}")
    print(f"\n  HWPX 변경이력 비교기 실행 중 →  {url}\n  (끝내려면 이 창에서 Ctrl+C 또는 대시보드의 [종료] 버튼)\n")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("  서버를 종료했습니다.")
