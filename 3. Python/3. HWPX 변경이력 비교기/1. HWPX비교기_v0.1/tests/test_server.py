"""서버 API 시험 — 실제로 서버를 띄워 올리기·상태·비교·내보내기를 확인한다."""
import json
import os
import sys
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import quote

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hwpxdiff.server.app import find_port, make_handler  # noqa: E402
from hwpxdiff.service import Workspace  # noqa: E402
from sample_builder import make_hwpx  # noqa: E402


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()
        port = find_port("127.0.0.1", 18765)
        ref = {}
        cls.srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(cls.ws, ref))
        ref["server"] = cls.srv
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def call(self, path, body=None, headers=None, raw=False):
        data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
        h = {"Content-Type": "application/json"} if body is not None and not isinstance(body, bytes) else {}
        h.update(headers or {})
        req = urllib.request.Request(self.base + path, data=data, headers=h, method="POST" if data is not None else "GET")
        with urllib.request.urlopen(req) as res:
            out = res.read()
            return out if raw else json.loads(out)

    def test_flow(self):
        self.assertIn(b"HWPX", self.call("/", raw=True))
        ids = []
        for i, txt in enumerate(["첫 문단 1", "첫 문단 2"]):
            r = self.call("/api/upload", make_hwpx([txt], modified=f"2026-01-0{i + 1}T00:00:00Z"),
                          {"X-File-Name": quote(f"버전{i + 1}.hwpx")})
            ids.append(r["id"])
        for _ in range(100):
            st = self.call("/api/status")
            if not st["progress"]["busy"]:
                break
            time.sleep(0.05)
        self.assertEqual([i["status"] for i in st["items"]], ["ready", "ready"])
        r = self.call("/api/compare", {"a": ids[0], "b": ids[1]})
        self.assertEqual(r["counts"]["modified"], 1)
        h = self.call("/api/history", {})
        self.assertEqual(len(h["versions"]), 2)
        csv = self.call(f"/api/export?kind=compare&fmt=csv&a={ids[0]}&b={ids[1]}", raw=True)
        self.assertIn("수정".encode(), csv)

    def test_rejects_other_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.call("/api/reset", {}, {"Origin": "http://evil.example"})
        self.assertEqual(cm.exception.code, 403)

    def test_static_traversal(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.call("/../hwpxdiff/config.py", raw=True)
        self.assertEqual(cm.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
