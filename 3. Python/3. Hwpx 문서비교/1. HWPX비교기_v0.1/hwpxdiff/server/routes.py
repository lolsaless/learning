"""API 경로표 — 대시보드(web/js/api.js)가 부르는 주소와 처리 함수.

새 기능을 추가할 때: ① 여기에 함수를 만들고 ROUTES 에 등록 → ② web/js/api.js 에 같은 이름의 호출 추가.
처리 함수는 (ws, req) 를 받아 dict(JSON 응답) 또는 (bytes, content_type, 파일이름) 을 돌려준다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Tuple
from urllib.parse import quote

from .. import APP_NAME, VERSION, config
from ..compare import CompareOptions
from ..export import comparison_csv, comparison_html, history_csv, history_html
from ..service import Workspace


@dataclass
class Request:
    method: str
    path: str
    query: Dict[str, str]
    headers: Dict[str, str]
    body: bytes = b""
    json: Dict[str, Any] = field(default_factory=dict)


class ApiError(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


def _opts(ws: Workspace, req: Request) -> CompareOptions:
    o = req.json.get("options")
    return CompareOptions.from_dict({**ws.options.to_dict(), **o}) if o else ws.options


# ── 처리 함수 ─────────────────────────────────────────
def info(ws, req):
    return {"app": APP_NAME, "version": VERSION, "defaults": config.DEFAULT_OPTIONS,
            "max_upload_mb": config.MAX_UPLOAD_MB}


def status(ws, req):
    return ws.status(int(req.query.get("since", "0") or 0))


def upload(ws, req):
    from urllib.parse import unquote
    name = unquote(req.headers.get("x-file-name", "")) or "문서.hwpx"
    rel = unquote(req.headers.get("x-rel-path", "")) or name
    if not name.lower().endswith(".hwpx"):
        raise ApiError(f"HWPX 파일만 넣을 수 있습니다: {name}")
    if not req.body:
        raise ApiError("파일 내용이 비어 있습니다")
    return {"id": ws.submit_bytes(name, req.body, rel)}


def folder(ws, req):
    path = (req.json.get("path") or "").strip()
    if not path:
        raise ApiError("폴더 경로를 입력하세요")
    try:
        n = ws.scan_folder(path, bool(req.json.get("recursive")))
    except FileNotFoundError as e:
        raise ApiError(str(e), 404)
    return {"found": n}


def remove(ws, req):
    ws.remove(req.json.get("id", ""))
    return {"ok": True}


def reset(ws, req):
    ws.reset()
    return {"ok": True}


def order(ws, req):
    if req.json.get("ids"):
        ws.set_order(req.json["ids"])
    else:
        ws.sort(req.json.get("mode", "modified"))
    return {"ok": True}


def options(ws, req):
    return {"options": ws.set_options(req.json.get("options")).to_dict()}


def document(ws, req):
    try:
        return ws.document(req.query.get("id", "")).to_dict()
    except KeyError as e:
        raise ApiError(str(e), 404)


def compare(ws, req):
    a, b = req.json.get("a"), req.json.get("b")
    if not a or not b:
        raise ApiError("비교할 두 문서를 고르세요")
    try:
        return ws.compare(a, b, _opts(ws, req))
    except KeyError as e:
        raise ApiError(str(e), 404)


def history(ws, req):
    try:
        return ws.history(_opts(ws, req), req.json.get("ids") or None)
    except KeyError as e:
        raise ApiError(str(e), 404)


def export(ws, req) -> Tuple[bytes, str, str]:
    kind, fmt = req.query.get("kind", "compare"), req.query.get("fmt", "html")
    stamp = time.strftime("%Y%m%d_%H%M")
    try:
        if kind == "history":
            data = ws.history()
            body = history_csv(data) if fmt == "csv" else history_html(data)
            name = f"HWPX_변경이력_{stamp}.{fmt}"
        else:
            data = ws.compare(req.query.get("a", ""), req.query.get("b", ""))
            body = comparison_csv(data) if fmt == "csv" else comparison_html(data)
            name = f"HWPX_비교_{stamp}.{fmt}"
    except KeyError as e:
        raise ApiError(str(e), 404)
    ctype = "text/csv; charset=utf-8" if fmt == "csv" else "text/html; charset=utf-8"
    return body, ctype, quote(name)


ROUTES: Dict[Tuple[str, str], Callable[[Workspace, Request], Any]] = {
    ("GET", "/api/info"): info,
    ("GET", "/api/status"): status,
    ("GET", "/api/document"): document,
    ("GET", "/api/export"): export,
    ("POST", "/api/upload"): upload,
    ("POST", "/api/folder"): folder,
    ("POST", "/api/remove"): remove,
    ("POST", "/api/reset"): reset,
    ("POST", "/api/order"): order,
    ("POST", "/api/options"): options,
    ("POST", "/api/compare"): compare,
    ("POST", "/api/history"): history,
}
