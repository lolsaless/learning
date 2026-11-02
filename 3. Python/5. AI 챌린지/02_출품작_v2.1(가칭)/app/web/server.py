# -*- coding: utf-8 -*-
"""[화면 연결] 이 PC 안에서만 동작하는 작은 웹 서버.

  주소:  http://127.0.0.1:8765  (다른 PC에서는 접속할 수 없음)
  화면:  app/ui/ 폴더의 파일을 그대로 보여 준다(index.html · css · js)
  주소표: 공통 주소(core_routes.py) + 켜진 파트(config.PARTS)의 routes.py 를 모아 만든다
"""
import os
import sys
import json
import socket
import threading
import importlib
import traceback
import webbrowser
import urllib.parse
import urllib.request
import mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from app import config
from app.common.errors import WorkError
from app.workspace import Workspace
from app.parts.clip.clipwatch import ClipWatcher
from app.web import core_routes, eval_routes, partmap

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(APP_DIR)
UI_DIR = os.path.join(APP_DIR, "ui")
RECENT = os.path.join(ROOT, "최근작업.json")
HEADER = "X-App-Request"        # 화면(js/core.js)이 POST 때 붙이는 머리글. 다른 사이트의 요청을 막는다


class App:
    """프로그램 전체에 하나: 열린 작업, 클립보드 감시기, 주소표."""

    def __init__(self):
        self.ws = None
        self.lock = threading.RLock()
        self.clip = ClipWatcher(self._on_clip)
        self.port = None
        self.server = None
        self.parts = []
        self.table = {}          # (방식, 주소) -> (처리 함수, 잠금 여부)
        self._build_routes()

    def _build_routes(self):
        groups = [("core", core_routes.routes(self))]
        self.mock = None
        for name in config.PARTS:
            mod = importlib.import_module(f"app.parts.{name}.routes")
            groups.append((name, mod.routes(self)))
            self.parts.append(name)
        if self.mock:                      # 가상자료 파트가 켜져 있을 때만 평가 주소를 연다
            groups.append(("eval", eval_routes.routes(self)))
        groups.append(("partmap", partmap.routes(self)))
        for owner, lst in groups:
            for r in lst:
                method, path, fn = r[:3]
                opt = r[3] if len(r) > 3 else ("lock" if method == "POST" else "")
                if (method, path) in self.table:
                    raise SystemExit(f"화면 주소가 겹칩니다: {method} {path} ({owner})")
                self.table[(method, path)] = (fn, opt == "lock")

    def _on_clip(self, info):
        if self.ws:
            self.ws.record_clip(info)

    def recent(self):
        try:
            with open(RECENT, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"folders": []}

    def remember(self, folder):
        r = self.recent()
        fs = [x for x in r.get("folders", []) if os.path.normcase(x) != os.path.normcase(folder)]
        r["folders"] = [folder] + fs[:9]
        try:
            with open(RECENT, "w", encoding="utf-8") as f:
                json.dump(r, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def close_work(self):
        if self.ws:
            self.ws.db.close()
            self.ws = None

    def open_work(self, folder, user=None):
        with self.lock:
            self.close_work()
            self.ws = Workspace(folder, user)
            self.remember(self.ws.folder)
            return self.ws.state()

    def need(self):
        if not self.ws:
            raise WorkError("먼저 작업 폴더를 여세요")
        return self.ws


A = None


class H(BaseHTTPRequestHandler):
    server_version = "LocalApp/2.0"

    def log_message(self, fmt, *args):
        if os.environ.get("APP_DEBUG"):
            sys.stderr.write("%s [%s] %s\n" % (self.log_date_time_string(), threading.current_thread().name, fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        h = (self.headers.get("Host") or "").split(":")[0]
        return h in ("127.0.0.1", "localhost")

    def _static(self, path):
        rel = "index.html" if path in ("/", "/index.html") else path[len("/ui/"):]
        full = os.path.normpath(os.path.join(UI_DIR, rel))
        if not full.startswith(UI_DIR + os.sep) or not os.path.isfile(full):
            return self._send(404, {"error": "없는 화면 파일"})
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            return self._send(200, f.read(), ctype)

    def _run(self, method, path, args):
        hit = A.table.get((method, path))
        if not hit:
            return self._send(404, {"error": "없는 주소"})
        fn, locked = hit
        try:
            if locked:
                with A.lock:              # 작업 준비·검증·저장이 겹쳐 실행되지 않게 한 번에 하나씩
                    r = fn(args)
            else:
                r = fn(args)
            return self._send(200, r)
        except WorkError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {"error": f"처리 중 오류: {e}"})

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "허용되지 않은 접속"})
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/index.html") or u.path.startswith("/ui/"):
            return self._static(u.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        return self._run("GET", u.path, q)

    def do_POST(self):
        if not self._host_ok() or self.headers.get(HEADER) != "1":
            return self._send(403, {"error": "허용되지 않은 요청"})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except ValueError:
            return self._send(400, {"error": "요청 형식 오류"})
        return self._run("POST", urllib.parse.urlparse(self.path).path, body)


def find_port():
    for port in range(config.PORT, config.PORT + config.PORT_TRY):
        try:          # 이미 이 프로그램이 켜져 있으면 그 주소를 쓴다
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=0.4) as r:
                if json.loads(r.read().decode()).get("app") == config.APP_ID:
                    return port, True
        except Exception:
            pass
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform != "win32":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            return port, False
        except OSError:
            s.close()
    raise SystemExit("빈 포트를 찾지 못했습니다. app/config.py 의 PORT 값을 바꿔 보세요")


def main(argv=None):
    global A
    argv = argv if argv is not None else sys.argv
    if sys.version_info < (3, 8):
        raise SystemExit("Python 3.8 이상이 필요합니다")
    port, running = find_port()
    url = f"http://127.0.0.1:{port}/"
    if running:
        print(f"{config.APP_NAME}이(가) 이미 켜져 있습니다 → {url}")
        if config.OPEN_BROWSER and "--no-browser" not in argv:
            webbrowser.open(url)
        return
    A = App()
    A.port = port
    A.server = ThreadingHTTPServer(("127.0.0.1", port), H)
    print("=" * 56)
    print(f"  {config.APP_NAME} v{config.APP_VERSION} 실행 중")
    print(f"  화면 주소: {url}")
    print(f"  켜진 파트: {', '.join(A.parts)}")
    print("  이 창을 닫으면 프로그램이 종료됩니다.")
    print("=" * 56)
    rec = A.recent().get("folders", [])
    if rec and os.path.isdir(rec[0]) and "--fresh" not in argv:
        try:
            A.open_work(rec[0])
        except Exception as e:
            print("최근 작업 폴더를 여는 중 오류:", e)
    if config.OPEN_BROWSER and "--no-browser" not in argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        A.server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        A.clip.stop()
        print("종료했습니다.")
