"""
serve.py — 대시보드 로컬 서버 (지점 정보 저장·V월드 검색·배경지도용)

사용법
    python serve.py            # 대시보드를 새로 만들고 http://localhost:8765 로 열기
    python serve.py --no-open  # 브라우저 자동 열기 안 함

이 서버로 열면
- '지점 관리' 화면에서 고친 하천명·주소·좌표·비고가 DB 엑셀(지점정보 시트)에 바로 저장된다(저장 전 '백업' 폴더에 복사).
- [V월드 검색] 버튼으로 주소를 검색해 좌표 후보를 받을 수 있다.
- DB 엑셀을 고치거나 월별 결과를 가져온 뒤 브라우저에서 새로고침하면 대시보드를 자동으로 다시 만든다.
- V월드 배경지도가 http://localhost:8765 주소로 요청된다(인증키 서비스 URL에 이 주소를 등록).
보안: 이 PC(127.0.0.1)에서만 접속되며, 다른 사이트에서 보낸 저장 요청은 거절한다.
"""
import argparse
import http.server
import importlib.util
import json
import socketserver
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wq_common as W  # noqa: E402


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


BUILD = _load("build_dashboard", "02_build_dashboard.py")
COORDS = _load("coords_tool", "04_coords_tool.py")
PORT = 8765
HTML_NAME = "한탄강_수질대시보드.html"
EDITABLE = {"하천명": str, "주소": str, "시군": str, "위도": float, "경도": float, "좌표상태": str, "좌표출처": str,
            "비고": str, "정렬순서": float}
LOCK = threading.Lock()


_BUILT = {"mtime": 0}


def rebuild():
    _BUILT["mtime"] = W.DEFAULT_DB.stat().st_mtime if W.DEFAULT_DB.exists() else 0
    out, data, warns = BUILD.build(str(W.DEFAULT_DB), str(HERE / HTML_NAME))
    for w in warns:
        print("[확인]", w)
    print(f"[대시보드] {out.name} 다시 만듦 ({len(data['stations'])}개 시료번호)")


def apply_station_edits(edits):
    """edits = {시료번호: {열: 값}} → 지점정보 시트에 반영"""
    with LOCK:
        db = W.read_db(W.DEFAULT_DB)
        by = {str(s["시료번호"]).strip(): s for s in db["stations"]}
        changed = []
        for name, fields in edits.items():
            s = by.get(name)
            if s is None:
                raise ValueError(f"지점정보에 없는 시료번호: {name}")
            for k, v in fields.items():
                if k not in EDITABLE:
                    continue
                if v in ("", None):
                    v = None
                elif EDITABLE[k] is float:
                    v = float(v)
                    if k == "정렬순서" and v.is_integer():
                        v = int(v)
                else:
                    v = str(v).strip()
                if k == "위도" and v is not None and not (33 <= v <= 39):
                    raise ValueError(f"{name}: 위도 {v} 는 범위(33~39)를 벗어납니다")
                if k == "경도" and v is not None and not (124 <= v <= 132):
                    raise ValueError(f"{name}: 경도 {v} 는 범위(124~132)를 벗어납니다")
                s[k] = v
            changed.append(name)
        db["stations"].sort(key=lambda s: (s.get("정렬순서") is None, s.get("정렬순서") or 0))
        W.write_db(W.DEFAULT_DB, db)
        rebuild()
        return changed


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def log_message(self, fmt, *args):  # 조용히: API 요청만 출력
        if "/api/" in (self.path or ""):
            sys.stderr.write("[요청] %s\n" % (fmt % args))

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _same_origin(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        origin = self.headers.get("Origin")
        ok_hosts = ("localhost", "127.0.0.1")
        if host not in ok_hosts:
            return False
        if origin and not any(origin == f"http://{h}:{PORT}" for h in ok_hosts):
            return False
        return True

    def end_headers(self):
        if self.path.endswith(".html") or self.path in ("/", ""):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/" + HTML_NAME)
            self.end_headers()
            return
        if self.path.startswith("/api/ping"):
            return self._json(200, {"ok": True, "server": True, "db": W.DEFAULT_DB.name})
        if self.path.split("?")[0].endswith(".html"):
            # DB 엑셀이 바뀌었으면(월별 가져오기·엑셀 직접 수정) 새로고침할 때 자동으로 다시 만든다
            try:
                if W.DEFAULT_DB.stat().st_mtime > _BUILT["mtime"] + 0.5:
                    with LOCK:
                        rebuild()
            except Exception as e:  # noqa: BLE001
                print("[오류] 다시 만들기 실패:", e)
        if self.path.split("?")[0].endswith((".py", ".xlsx", ".bat", ".csv")):
            return self._json(403, {"ok": False, "error": "이 파일은 내려받을 수 없습니다"})
        return super().do_GET()

    def do_POST(self):
        if not self._same_origin():
            return self._json(403, {"ok": False, "error": "다른 사이트에서 보낸 요청은 거절합니다"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:  # noqa: BLE001
            return self._json(400, {"ok": False, "error": "요청 형식 오류"})
        try:
            if self.path.startswith("/api/stations"):
                changed = apply_station_edits(body.get("edits") or {})
                return self._json(200, {"ok": True, "changed": changed})
            if self.path.startswith("/api/geocode"):
                cfg = W.settings_dict(W.read_db(W.DEFAULT_DB))
                key = str(cfg.get("VWORLD_KEY") or "").strip()
                if not key:
                    return self._json(200, {"ok": False, "error": "DB 설정 시트에 VWORLD_KEY가 없습니다"})
                hits = COORDS.find_coords(body.get("addr"), body.get("sigun"), key, str(cfg.get("VWORLD_DOMAIN") or "").strip())
                return self._json(200, {"ok": True, "hits": hits})
            if self.path.startswith("/api/rebuild"):
                with LOCK:
                    rebuild()
                return self._json(200, {"ok": True})
            return self._json(404, {"ok": False, "error": "없는 주소"})
        except W.DBLocked as e:
            return self._json(200, {"ok": False, "error": str(e)})
        except COORDS.VWorldError as e:
            return self._json(200, {"ok": False, "error": str(e)})
        except ValueError as e:
            return self._json(200, {"ok": False, "error": str(e)})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._json(500, {"ok": False, "error": f"서버 오류: {e}"})


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--port", type=int, default=PORT)
    a = ap.parse_args()
    globals()["PORT"] = a.port
    rebuild()
    try:
        srv = Server(("127.0.0.1", a.port), Handler)
    except OSError:
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{a.port}/api/ping", timeout=3) as r:
                ok = json.loads(r.read().decode("utf-8")).get("server")
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            print(f"[안내] 대시보드 서버가 이미 켜져 있습니다. 브라우저만 엽니다.")
            if not a.no_open:
                webbrowser.open(f"http://localhost:{a.port}/{HTML_NAME}")
        else:
            print(f"[오류] {a.port} 포트를 다른 프로그램(예: 이전 버전 서버 창)이 쓰고 있습니다. 그 창을 닫고 다시 실행하세요.")
            input("Enter를 누르면 닫힙니다...")
        return
    url = f"http://localhost:{a.port}/{HTML_NAME}"
    print(f"[서버] {url}\n  이 창을 닫으면 저장·V월드 검색·배경지도가 멈춥니다. (끝내기: Ctrl+C)")
    if not a.no_open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[서버] 종료")


if __name__ == "__main__":
    main()
