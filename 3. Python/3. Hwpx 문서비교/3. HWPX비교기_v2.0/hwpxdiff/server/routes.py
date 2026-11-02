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
from ..export import comparison_csv, comparison_html, document_html, history_csv, history_html
from ..render import doc_css
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


def render(ws, req):
    """(v1.1) 원본 문서 모양 보기. {a, b?, view: merged|pair}"""
    a = req.json.get("a")
    if not a:
        raise ApiError("볼 문서를 고르세요")
    try:
        return ws.render(a, req.json.get("b") or None, req.json.get("view", "merged"), _opts(ws, req))
    except KeyError as e:
        raise ApiError(str(e), 404)


def docview_css(ws, req):
    return doc_css().encode("utf-8"), "text/css; charset=utf-8", None


# ── (v2.0) 계보·역할 ────────────────────────────────
def _guard(fn):
    """엔진 오류(KeyError·ValueError·병합/프로젝트 오류)를 화면에 보일 수 있는 400/404 로."""
    def wrapped(ws, req):
        try:
            return fn(ws, req)
        except KeyError as e:
            raise ApiError(str(e).strip("'\""), 404)
        except (ValueError, RuntimeError, OSError) as e:
            raise ApiError(str(e))
        except Exception as e:
            from ..merge.engine import MergeError
            from ..project import ProjectError
            if isinstance(e, (MergeError, ProjectError)):
                raise ApiError(str(e))
            raise
    wrapped.__name__ = fn.__name__
    return wrapped


@_guard
def lineage(ws, req):
    if len(ws.ready_docs()) < 1:
        return {"nodes": [], "edges": [], "notes": [], "positions": {}}
    return ws.lineage()


@_guard
def set_role(ws, req):
    return {"messages": ws.set_role(req.json.get("id", ""), req.json.get("role", ""))}


@_guard
def set_parents(ws, req):
    ws.set_parents(req.json.get("id", ""), req.json.get("parents") or [])
    return {"ok": True}


@_guard
def positions(ws, req):
    ws.set_positions({k: v for k, v in (req.json.get("positions") or {}).items()})
    return {"ok": True}


# ── (v2.0) 병합 ─────────────────────────────────────
@_guard
def merge_plan(ws, req):
    return ws.merge_plan(req.json.get("base", ""), req.json.get("versions") or [])


@_guard
def merge_preview(ws, req):
    j = req.json
    return ws.merge_preview(j.get("base", ""), j.get("versions") or [], j.get("choices") or {})


@_guard
def merge_save(ws, req):
    j = req.json
    return ws.merge_save(j.get("base", ""), j.get("versions") or [], j.get("choices") or {},
                         j.get("name", ""), j.get("role", "final"))


# ── (v2.0) 직접 고치기 ───────────────────────────────
@_guard
def edit_save(ws, req):
    j = req.json
    return ws.edit_save(j.get("doc", ""), j.get("edits") or {}, j.get("mark_color") or None, j.get("name", ""))


@_guard
def editable(ws, req):
    """블록이 여기서 고칠 수 있는 문단인지 미리 확인 (고칠 수 없으면 이유)."""
    from ..merge.edit import EditError, edit_document
    d = ws.document(req.query.get("doc", ""))
    bi = int(req.query.get("block", "-1"))
    if not 0 <= bi < len(d.blocks):
        raise ApiError("없는 문단입니다")
    try:
        edit_document(d, {bi: d.blocks[bi].text + " "})
        return {"ok": True, "text": d.blocks[bi].text, "location": d.blocks[bi].location}
    except EditError as e:
        return {"ok": False, "reason": str(e).split(": ", 1)[-1], "text": d.blocks[bi].text,
                "location": d.blocks[bi].location}


# ── (v2.0) 파일·한글 ─────────────────────────────────
@_guard
def download(ws, req):
    data, name = ws.file_bytes(req.query.get("id", ""))
    return data, "application/hwp+zip", quote(name)


@_guard
def hangul_open(ws, req):
    return {"path": ws.open_in_hangul(req.json.get("id", ""))}


@_guard
def hangul_resave(ws, req):
    return ws.hangul_resave(req.json.get("id", ""))


@_guard
def hangul_pdf(ws, req):
    return {"path": ws.hangul_pdf(req.json.get("id", ""))}


@_guard
def pick_folder(ws, req):
    from .. import bridge
    return {"path": bridge.pick_folder(req.json.get("title", "폴더 고르기"), req.json.get("initial", ""))}


# ── (v2.0) 프로젝트 ─────────────────────────────────
@_guard
def project_info(ws, req):
    return {"project": ws.project_info()}


@_guard
def project_create(ws, req):
    folder = (req.json.get("folder") or "").strip()
    if not folder:
        raise ApiError("프로젝트를 저장할 폴더를 고르세요")
    return {"project": ws.project_create(folder, req.json.get("name", ""))}


@_guard
def project_open(ws, req):
    folder = (req.json.get("folder") or "").strip()
    if not folder:
        raise ApiError("열 프로젝트 폴더를 고르세요")
    return {"project": ws.project_open(folder)}


@_guard
def project_close(ws, req):
    ws.project_close()
    return {"ok": True}


def export(ws, req) -> Tuple[bytes, str, str]:
    kind, fmt = req.query.get("kind", "compare"), req.query.get("fmt", "html")
    stamp = time.strftime("%Y%m%d_%H%M")
    try:
        if kind == "doc":
            a, b = req.query.get("a", ""), req.query.get("b", "")
            data = ws.render(a, b, "merged")
            body = document_html(data, ws.document(a), ws.document(b))
            fmt = "html"
            name = f"HWPX_문서보기_{stamp}.html"
        elif kind == "history":
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
    if req.query.get("save") == "1" and ws.project:          # (v2.0) 프로젝트 5_보고서 에도 저장
        ws.save_report(name, body)
    return body, ctype, quote(name)


ROUTES: Dict[Tuple[str, str], Callable[[Workspace, Request], Any]] = {
    ("GET", "/api/info"): info,
    ("GET", "/api/status"): status,
    ("GET", "/api/document"): document,
    ("GET", "/api/export"): export,
    ("GET", "/api/docview.css"): docview_css,
    ("POST", "/api/render"): render,
    ("POST", "/api/upload"): upload,
    ("POST", "/api/folder"): folder,
    ("POST", "/api/remove"): remove,
    ("POST", "/api/reset"): reset,
    ("POST", "/api/order"): order,
    ("POST", "/api/options"): options,
    ("POST", "/api/compare"): compare,
    ("POST", "/api/history"): history,
    # v2.0
    ("GET", "/api/lineage"): lineage,
    ("POST", "/api/role"): set_role,
    ("POST", "/api/parents"): set_parents,
    ("POST", "/api/positions"): positions,
    ("POST", "/api/merge/plan"): merge_plan,
    ("POST", "/api/merge/preview"): merge_preview,
    ("POST", "/api/merge/save"): merge_save,
    ("POST", "/api/edit/save"): edit_save,
    ("GET", "/api/edit/check"): editable,
    ("GET", "/api/download"): download,
    ("POST", "/api/hangul/open"): hangul_open,
    ("POST", "/api/hangul/resave"): hangul_resave,
    ("POST", "/api/hangul/pdf"): hangul_pdf,
    ("POST", "/api/pick-folder"): pick_folder,
    ("GET", "/api/project"): project_info,
    ("POST", "/api/project/create"): project_create,
    ("POST", "/api/project/open"): project_open,
    ("POST", "/api/project/close"): project_close,
}
