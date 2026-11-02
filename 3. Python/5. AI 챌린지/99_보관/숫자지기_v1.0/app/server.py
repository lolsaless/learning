# -*- coding: utf-8 -*-
"""숫자지기 실행 파일: 이 PC 안에서만 동작하는 작은 웹 서버를 켜고 브라우저로 화면을 연다.

  실행:  python app/server.py        (Windows는 '숫자지기_열기.bat' 더블클릭)
  주소:  http://127.0.0.1:8765        (다른 PC에서는 접속할 수 없음)
  종료:  화면 오른쪽 위 [종료] 또는 검은 창 닫기
"""
import os
import sys
import json
import shutil
import socket
import string
import threading
import traceback
import webbrowser
import subprocess
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from app import config                                  # noqa: E402
from app.core.workspace import Workspace, WorkError     # noqa: E402
from app.core.clipwatch import ClipWatcher              # noqa: E402

UI = os.path.join(HERE, "ui", "index.html")
RECENT = os.path.join(ROOT, "최근작업.json")
DEMO = os.path.join(ROOT, "시연자료")
DEMO_WORK = os.path.join(DEMO, "작업(시연)")
DEMO_BASE = os.path.join(DEMO, "공유폴더(가상)", "2026 행정사무감사")


class App:
    def __init__(self):
        self.ws = None
        self.lock = threading.RLock()
        self.clip = ClipWatcher(self._on_clip)
        self.port = None
        self.server = None

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

    def open_work(self, folder, user=None):
        with self.lock:
            if self.ws:
                self.ws.db.close()
            self.ws = Workspace(folder, user)
            self.remember(self.ws.folder)
            return self.ws.state()

    def need(self):
        if not self.ws:
            raise WorkError("먼저 작업 폴더를 여세요")
        return self.ws


A = App()


def fs_list(path):
    if not path:
        roots = []
        if sys.platform == "win32":
            for d in string.ascii_uppercase:
                if os.path.exists(f"{d}:\\"):
                    roots.append({"name": f"{d}:\\", "path": f"{d}:\\", "dir": True})
        else:
            roots.append({"name": "/", "path": "/", "dir": True})
        home = os.path.expanduser("~")
        quick = [{"name": "홈 폴더", "path": home, "dir": True}]
        for nm in ("Desktop", "바탕 화면", "Documents", "문서", "Downloads", "다운로드"):
            p = os.path.join(home, nm)
            if os.path.isdir(p):
                quick.append({"name": nm, "path": p, "dir": True})
        if os.path.isdir(DEMO):
            quick.insert(0, {"name": "시연자료(이 프로그램 폴더)", "path": DEMO, "dir": True})
        return {"path": "", "parent": None, "entries": quick + roots}
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise WorkError("폴더가 아닙니다")
    out = []
    try:
        names = sorted(os.listdir(path), key=lambda s: s.lower())
    except OSError as e:
        raise WorkError(f"폴더를 열 수 없습니다: {e}")
    for n in names:
        if n.startswith(".") or n.startswith("~$"):
            continue
        p = os.path.join(path, n)
        isd = os.path.isdir(p)
        if isd or n.lower().endswith((".hwpx", ".xlsx", ".xlsm", ".hwp", ".xls")):
            out.append({"name": n, "path": p, "dir": isd, "size": None if isd else os.path.getsize(p)})
    parent = os.path.dirname(path)
    return {"path": path, "parent": parent if parent != path else "", "entries": out}


def open_in_os(path):
    if not os.path.exists(path):
        raise WorkError("파일이 없습니다")
    if sys.platform == "win32":
        os.startfile(path)                                       # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
    return {"ok": True}


def demo_setup(reset=False):
    if not os.path.isdir(DEMO_BASE):
        raise WorkError("시연자료 폴더가 없습니다. 먼저 '시연자료_다시만들기'를 실행하세요")
    if reset and os.path.isdir(DEMO_WORK):
        if A.ws and os.path.normcase(A.ws.folder) == os.path.normcase(DEMO_WORK):
            A.ws.db.close()
            A.ws = None
        shutil.rmtree(DEMO_WORK)
    demo_restore()
    st = A.open_work(DEMO_WORK)
    ws = A.ws
    if not ws.db.versions():
        ws.set_target(os.path.join(DEMO_BASE, "03_취합", "2026_행정사무감사_요구자료_취합본.hwpx"))
    if not ws.db.sources():
        ws.add_sources([os.path.join(DEMO_BASE, "01_원본자료")], "원본")
        ws.add_sources([os.path.join(DEMO_BASE, "02_팀제출")], "팀제출")
    return ws.state()


def demo_stage2():
    src = os.path.join(DEMO, "나중에_받은_자료", "하천수질_측정결과_2026.xlsx")
    dst = os.path.join(DEMO_BASE, "01_원본자료", "수질분석팀", "하천수질_측정결과_2026.xlsx")
    shutil.copy2(src, dst)
    os.utime(dst, None)
    return {"ok": True, "msg": "수질분석팀이 수정한 엑셀로 공유폴더의 원본을 바꿨습니다(시연)"}


def demo_restore():
    keep = os.path.join(DEMO, "나중에_받은_자료", "_처음_원본_보관", "하천수질_측정결과_2026.xlsx")
    dst = os.path.join(DEMO_BASE, "01_원본자료", "수질분석팀", "하천수질_측정결과_2026.xlsx")
    if os.path.exists(keep):
        with open(keep, "rb") as a, open(dst, "rb") as b:
            if a.read() == b.read():
                return
        shutil.copy2(keep, dst)
        os.utime(dst, None)


class H(BaseHTTPRequestHandler):
    server_version = "Numjigi/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("NUMJIGI_DEBUG"):
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

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "허용되지 않은 접속"})
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                with open(UI, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if u.path == "/api/ping":
                return self._send(200, {"app": config.APP_NAME, "version": config.APP_VERSION})
            if u.path == "/api/state":
                st = A.ws.state() if A.ws else None
                return self._send(200, {"work": st, "recent": A.recent().get("folders", []),
                                        "demo": os.path.isdir(DEMO_BASE), "demo_work": DEMO_WORK,
                                        "clip": {"available": A.clip.available, "running": A.clip.running,
                                                 "count": A.clip.count, "error": A.clip.last_error},
                                        "version": config.APP_VERSION, "status_names": config.STATUS})
            if u.path == "/api/fs":
                return self._send(200, fs_list(q.get("path", "")))
            if u.path == "/api/view":
                with A.lock:
                    ws = A.need()
                    return self._send(200, ws.view() if ws.last else ws.verify())
            if u.path == "/api/slot":
                return self._send(200, A.need().slot_detail(q["key"]))
            if u.path == "/api/grid":
                return self._send(200, A.need().grid(q["sid"], q.get("sheet", ""), int(q.get("r0", 0)), int(q.get("c0", 0)),
                                                     int(q.get("nr", 80)), int(q.get("nc", 30))))
            if u.path == "/api/history":
                return self._send(200, A.need().history(q.get("slot")))
            if u.path == "/api/clips":
                return self._send(200, {"clips": [dict(c, cells={f"{k[0]},{k[1]}": v for k, v in c["cells"].items()})
                                                  for c in A.need().db.clips(100)]})
            return self._send(404, {"error": "없는 주소"})
        except WorkError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {"error": f"처리 중 오류: {e}"})

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Numjigi") != "1":
            return self._send(403, {"error": "허용되지 않은 요청"})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except ValueError:
            return self._send(400, {"error": "요청 형식 오류"})
        p = urllib.parse.urlparse(self.path).path
        try:
            if p == "/api/shutdown":
                r = self.route(p, body)
            else:
                with A.lock:                   # 작업 준비·검증·저장이 겹쳐 실행되지 않게 한 번에 하나씩
                    r = self.route(p, body)
            if r is None:
                return self._send(404, {"error": "없는 주소"})
            return self._send(200, r)
        except WorkError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {"error": f"처리 중 오류: {e}"})

    def route(self, p, b):
        if p == "/api/work/open":
            return A.open_work(b["folder"], b.get("user"))
        if p == "/api/demo/setup":
            return demo_setup(reset=b.get("reset", False))
        if p == "/api/demo/stage2":
            return demo_stage2()
        if p == "/api/demo/restore":
            demo_restore()
            return {"ok": True}
        if p == "/api/fs/mkdir":
            os.makedirs(b["path"], exist_ok=True)
            return {"ok": True, "path": os.path.abspath(b["path"])}
        if p == "/api/open":
            return open_in_os(b["path"])
        if p == "/api/shutdown":
            threading.Thread(target=lambda: (A.clip.stop(), A.server.shutdown()), daemon=True).start()
            return {"ok": True}
        if p == "/api/clip":
            if b.get("on"):
                A.need()
                ok = A.clip.start()
                return {"ok": ok, "error": A.clip.last_error}
            A.clip.stop()
            return {"ok": True}
        ws = A.need()
        if p == "/api/user":
            ws.set_user(b.get("name"))
            return ws.state()
        if p == "/api/target":
            r = ws.set_target(b["path"])
            return dict(r, state=ws.state())
        if p == "/api/sources/add":
            r = ws.add_sources(b["paths"], b.get("role"))
            return dict(r, state=ws.state())
        if p == "/api/sources/remove":
            ws.remove_source(b["sid"])
            return ws.state()
        if p == "/api/sources/role":
            ws.set_role(b["sid"], b["role"])
            return ws.state()
        if p == "/api/sources/check":
            return ws.check_sources()
        if p == "/api/verify":
            return ws.verify()
        if p == "/api/pending":
            return ws.set_pending(b["slot"], b["value"], b.get("method", "직접 입력"), b.get("sid"), b.get("ref"),
                                  b.get("reason", ""))
        if p == "/api/pending/drop":
            return ws.drop_pending(b.get("slot"))
        if p == "/api/fix":
            return ws.fix_from_source(b["slot"], b["sid"], b["ref"], b["value"], b.get("reason") or "원본 값으로 수정")
        if p == "/api/input":
            return ws.input_values(b["sid"], b["sheet"], int(b["r0"]), int(b["c0"]), int(b["r1"]), int(b["c1"]),
                                   b["slot"], b.get("dec"), float(b.get("scale", 1.0)), b.get("comma", True))
        if p == "/api/confirm":
            return ws.confirm(b["slot"], b["sid"], b["ref"])
        if p == "/api/unconfirm":
            return ws.unconfirm(b["slot"])
        if p == "/api/save":
            return ws.save_version(b.get("note", ""))
        if p == "/api/export":
            return ws.export()
        return None


def find_port():
    for port in range(config.PORT, config.PORT + config.PORT_TRY):
        # 이미 숫자지기가 켜져 있으면 그 주소를 쓴다
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=0.4) as r:
                if json.loads(r.read().decode()).get("app") == config.APP_NAME:
                    return port, True
        except Exception:
            pass
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform != "win32":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # 방금 끈 서버의 대기 상태 포트도 다시 사용
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            return port, False
        except OSError:
            s.close()
            continue
    raise SystemExit("빈 포트를 찾지 못했습니다. config.py의 PORT 값을 바꿔 보세요")


def main():
    if sys.version_info < (3, 8):
        raise SystemExit("Python 3.8 이상이 필요합니다")
    port, running = find_port()
    url = f"http://127.0.0.1:{port}/"
    if running:
        print(f"숫자지기가 이미 켜져 있습니다 → {url}")
        if config.OPEN_BROWSER and "--no-browser" not in sys.argv:
            webbrowser.open(url)
        return
    A.port = port
    A.server = ThreadingHTTPServer(("127.0.0.1", port), H)
    print("=" * 56)
    print(f"  {config.APP_NAME} v{config.APP_VERSION} 실행 중")
    print(f"  화면 주소: {url}")
    print("  이 창을 닫으면 프로그램이 종료됩니다.")
    print("=" * 56)
    rec = A.recent().get("folders", [])
    if rec and os.path.isdir(rec[0]) and "--fresh" not in sys.argv:
        try:
            A.open_work(rec[0])
        except Exception as e:
            print("최근 작업 폴더를 여는 중 오류:", e)
    if config.OPEN_BROWSER and "--no-browser" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        A.server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        A.clip.stop()
        print("종료했습니다.")


if __name__ == "__main__":
    main()
