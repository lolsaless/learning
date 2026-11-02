"""작업공간 — 불러온 문서 목록, 백그라운드 해석 작업, 진행상황, 로그, 결과 캐시,
(v2.0) 역할(원본·수정본·최종본)·부모 관계, 계보 분석, 병합, 직접 고치기, 프로젝트(폴더·이력 JSON), 한글 연동.

서버(server/)는 이 클래스의 메서드만 호출한다. 화면 없이 파이썬에서 직접 써도 된다:
    ws = Workspace(); ws.submit_path("a.hwpx"); ws.wait(); ws.lineage(); ws.merge_plan(base, [v1, v2])

문서 id = 파일 내용 SHA-1 앞 12자리 → 같은 파일은 두 번 들어가지 않고, 프로젝트 기록과 id 가 일치한다.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import tempfile
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple, Union

from .. import bridge
from ..compare import CompareOptions, build_history, compare_documents, order_documents
from ..hwpx import HwpxError, load_document
from ..hwpx.model import Document
from ..lineage import analyze
from ..merge.edit import edit_document
from ..merge.engine import apply_merge, plan_merge
from ..project import ROLE_LABELS, Project
from ..render import VIEWS, render_merge, render_plain, render_view

SUPPORTED_EXT = (".hwpx",)
ROLES = ("original", "revision", "final", "archived")


def doc_id_of(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:12]


class Workspace:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.items: Dict[str, Dict[str, Any]] = {}     # id → {id,name,status,error,...}
        self.docs: Dict[str, Document] = {}
        self.order: List[str] = []
        self.order_mode = "modified"                   # modified | name | manual
        self.options = CompareOptions()
        self.logs: deque = deque(maxlen=500)
        self._log_seq = 0
        self._cache: Dict[tuple, Any] = {}
        # (v2.0) 문서 관계·역할 — 프로젝트가 열려 있으면 프로젝트에도 함께 기록
        self.roles: Dict[str, str] = {}
        self.parents: Dict[str, List[str]] = {}
        self.origins: Dict[str, str] = {}
        self.positions: Dict[str, List[float]] = {}
        self.project: Optional[Project] = None
        self._hangul = bridge.hangul_status()
        self._jobs: "queue.Queue[tuple]" = queue.Queue()
        self._worker = threading.Thread(target=self._run, name="hwpx-parser", daemon=True)
        self._worker.start()

    # ── 로그 ────────────────────────────────────────
    def log(self, msg: str, level: str = "info") -> None:
        with self.lock:
            self._log_seq += 1
            self.logs.append({"id": self._log_seq, "time": time.strftime("%H:%M:%S"),
                              "level": level, "msg": msg})

    def _invalidate(self) -> None:
        """문서 목록·관계가 바뀌면 계보·병합 캐시를 비운다 (비교 결과는 문서 쌍마다 그대로 유효)."""
        self._cache = {k: v for k, v in self._cache.items() if k[0] not in ("lineage", "plan", "mrender")}

    # ── 파일 넣기 ────────────────────────────────────
    def submit_bytes(self, name: str, data: bytes, rel_path: str = "") -> str:
        return self._enqueue(name, data, rel_path or name)

    def submit_path(self, path: str, item_id: Optional[str] = None) -> str:
        with open(path, "rb") as f:
            data = f.read()
        return self._enqueue(os.path.basename(path), data, path, item_id, source_path=path)

    def scan_folder(self, folder: str, recursive: bool = False) -> int:
        folder = os.path.expanduser(folder.strip().strip('"'))
        if not os.path.isdir(folder):
            raise FileNotFoundError(f"폴더를 찾을 수 없습니다: {folder}")
        found = []
        for root, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            found += [os.path.join(root, f) for f in sorted(files)
                      if f.lower().endswith(SUPPORTED_EXT) and not f.startswith(("~", "."))]
            if not recursive:
                break
        for p in found:
            self.submit_path(p)
        self.log(f"폴더에서 HWPX {len(found)}개 발견: {folder}")
        return len(found)

    def _enqueue(self, name: str, data: bytes, label: str, item_id: Optional[str] = None,
                 source_path: str = "") -> str:
        item_id = item_id or doc_id_of(data)
        with self.lock:
            if item_id in self.items:
                self.log(f"이미 들어 있는 파일이라 건너뜀: {name} (= {self.items[item_id]['name']})", "warn")
                return item_id
            self.items[item_id] = {"id": item_id, "name": name, "label": label, "status": "queued",
                                   "error": "", "added": time.time(), "duplicate_of": "",
                                   "source_path": source_path}
            self.order.append(item_id)
        self.log(f"대기열 추가: {name}")
        self._jobs.put((item_id, name, data, source_path))
        return item_id

    # ── 백그라운드 해석 ───────────────────────────────
    def _run(self) -> None:
        while True:
            item_id, name, data, source_path = self._jobs.get()
            with self.lock:
                item = self.items.get(item_id)
                if item is None:           # 해석 전에 삭제됨
                    continue
                item["status"] = "parsing"
            t0 = time.time()
            try:
                doc = load_document(data, name=name, doc_id=item_id)
                doc.source_path = source_path
            except (HwpxError, OSError, ValueError) as e:
                self._fail(item_id, name, str(e))
                continue
            except Exception as e:  # 예상 못 한 오류도 화면에 보이게
                self._fail(item_id, name, f"{type(e).__name__}: {e}")
                continue
            self._register(doc)
            s = doc.stats
            self.log(f"해석 완료: {name} — 문단 {s.get('paragraphs', 0)}, 표 {s.get('tables', 0)}, "
                     f"셀 {s.get('cells', 0)} ({time.time() - t0:.2f}초)", "ok")
            for w in doc.warnings:
                self.log(f"{name}: {w}", "warn")

    def _fail(self, item_id: str, name: str, msg: str) -> None:
        with self.lock:
            if item_id in self.items:
                self.items[item_id].update(status="error", error=msg)
        self.log(f"해석 실패: {name} — {msg}", "error")

    def _register(self, doc: Document, origin: str = "import", parents: Optional[List[str]] = None,
                  role: Optional[str] = None) -> None:
        with self.lock:
            if doc.id not in self.items:
                self.items[doc.id] = {"id": doc.id, "name": doc.name, "label": doc.name, "status": "ready",
                                      "error": "", "added": time.time(), "duplicate_of": "", "source_path": ""}
                self.order.append(doc.id)
            self.docs[doc.id] = doc
            self.items[doc.id]["status"] = "ready"
            if parents:
                self.parents[doc.id] = list(parents)
            if origin != "import":
                self.origins[doc.id] = origin
            if role:
                self._set_role_local(doc.id, role)
            if self.project and not self.project.doc(doc.id):
                self.project.add(doc.id, doc.name, doc.raw, doc.sha1, role or self.roles.get(doc.id, "revision"),
                                 parents=self.parents.get(doc.id), origin=origin, meta=doc.meta)
                self._sync_from_project()
            if self.order_mode != "manual":
                self._sort(self.order_mode)
            self._invalidate()

    def add_generated(self, name: str, data: bytes, origin: str, parents: List[str], role: str = "revision") -> Document:
        """병합·고치기로 만든 새 문서를 바로 등록 (해석을 기다리지 않음)."""
        doc_id = doc_id_of(data)
        with self.lock:
            if doc_id in self.docs:
                return self.docs[doc_id]
        doc = load_document(data, name=name, doc_id=doc_id)
        self._register(doc, origin=origin, parents=parents, role=role)
        self.log(f"새 문서 만듦: {name} ({ {'merge': '병합', 'edit': '직접 고침'}.get(origin, origin)})", "ok")
        return doc

    def wait(self, timeout: float = 60) -> None:
        """모든 해석이 끝날 때까지 기다림 (테스트·명령줄용)."""
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                if all(i["status"] in ("ready", "error") for i in self.items.values()) and self._jobs.empty():
                    return
            time.sleep(0.05)

    # ── 목록 관리 ────────────────────────────────────
    def remove(self, item_id: str) -> None:
        with self.lock:
            item = self.items.pop(item_id, None)
            self.docs.pop(item_id, None)
            if item_id in self.order:
                self.order.remove(item_id)
            self.roles.pop(item_id, None)
            self.parents.pop(item_id, None)
            for k in self.parents:
                self.parents[k] = [p for p in self.parents[k] if p != item_id]
            self._cache = {k: v for k, v in self._cache.items() if item_id not in str(k)}
            if self.project:
                self.project.remove(item_id)
        if item:
            self.log(f"목록에서 뺌: {item['name']}" + (" (파일은 프로젝트 4_보관 에 남김)" if self.project else ""))

    def reset(self) -> None:
        with self.lock:
            self.items.clear()
            self.docs.clear()
            self.order.clear()
            self._cache.clear()
            self.roles.clear()
            self.parents.clear()
            self.origins.clear()
            self.positions.clear()
        self.log("작업공간을 비웠습니다")

    def set_order(self, ids: List[str]) -> None:
        with self.lock:
            known = [i for i in ids if i in self.items]
            rest = [i for i in self.order if i not in known]
            self.order = known + rest
            self.order_mode = "manual"
        self.log("버전 순서를 직접 지정했습니다")

    def sort(self, mode: str) -> None:
        with self.lock:
            self.order_mode = mode if mode in ("modified", "name") else "modified"
            self._sort(self.order_mode)
        self.log("버전 순서: " + ("문서 수정일 순" if self.order_mode == "modified" else "파일 이름 순"))

    def _sort(self, mode: str) -> None:
        ready = order_documents([self.docs[i] for i in self.order if i in self.docs], mode)
        pending = [i for i in self.order if i not in self.docs]
        self.order = [d.id for d in ready] + pending

    def set_options(self, d: Optional[Dict[str, Any]]) -> CompareOptions:
        with self.lock:
            self.options = CompareOptions.from_dict({**self.options.to_dict(), **(d or {})})
            self._invalidate()
            return self.options

    # ── 역할·관계 ────────────────────────────────────
    def _set_role_local(self, doc_id: str, role: str) -> None:
        if role in ("original", "final"):
            for k, r in list(self.roles.items()):
                if r == role and k != doc_id:
                    self.roles[k] = "archived" if role == "final" else "revision"
        self.roles[doc_id] = role

    def set_role(self, doc_id: str, role: str) -> List[str]:
        if role not in ROLES:
            raise ValueError(f"알 수 없는 역할: {role}")
        self.document(doc_id)
        with self.lock:
            if self.project:
                msgs = self.project.set_role(doc_id, role)
                self._sync_from_project()
            else:
                self._set_role_local(doc_id, role)
                msgs = [f"{self.docs[doc_id].name} → {ROLE_LABELS[role]}"]
            self._invalidate()
        for m in msgs:
            self.log("역할 지정: " + m, "ok")
        return msgs

    def set_parents(self, doc_id: str, parents: List[str]) -> None:
        self.document(doc_id)
        with self.lock:
            self.parents[doc_id] = [p for p in parents if p in self.docs and p != doc_id]
            if self.project:
                self.project.set_parents(doc_id, self.parents[doc_id])
            self._invalidate()
        self.log(f"부모 문서 지정: {self.docs[doc_id].name}", "ok")

    def set_positions(self, positions: Dict[str, List[float]]) -> None:
        with self.lock:
            self.positions.update(positions)
            if self.project:
                self.project.set_positions(positions)

    def lineage(self) -> Dict[str, Any]:
        docs = self.ready_docs()
        key = ("lineage", tuple(d.id for d in docs), json.dumps(self.roles, sort_keys=True),
               json.dumps(self.parents, sort_keys=True), self.options.cache_key())
        with self.lock:
            if key in self._cache:
                out = dict(self._cache[key])
                out["positions"] = dict(self.positions)
                return out
        res = analyze(docs, lambda a, b: self.compare(a.id, b.id), self.parents, self.roles)
        for n in res["nodes"]:
            n["origin"] = self.origins.get(n["id"], "import")
        with self.lock:
            self._cache[key] = res
        out = dict(res)
        out["positions"] = dict(self.positions)
        return out

    # ── 조회 ────────────────────────────────────────
    def status(self, since_log: int = 0) -> Dict[str, Any]:
        with self.lock:
            items = []
            for no, i in enumerate(self.order, 1):
                it = dict(self.items[i])
                doc = self.docs.get(i)
                if doc:
                    it.update(meta=doc.meta, stats=doc.stats, size=doc.size, sha1=doc.sha1,
                              warnings=doc.warnings)
                it["no"] = no
                it["role"] = self.roles.get(i, "")
                it["origin"] = self.origins.get(i, "import")
                items.append(it)
            total = len(items)
            done = sum(1 for i in items if i["status"] in ("ready", "error"))
            return {
                "items": items, "order_mode": self.order_mode, "options": self.options.to_dict(),
                "progress": {"total": total, "done": done,
                             "busy": done < total,
                             "parsing": next((i["name"] for i in items if i["status"] == "parsing"), "")},
                "logs": [l for l in self.logs if l["id"] > since_log],
                "project": ({"name": self.project.data["name"], "folder": self.project.folder}
                            if self.project else None),
                "hangul": self._hangul,
            }

    def ready_docs(self) -> List[Document]:
        with self.lock:
            return [self.docs[i] for i in self.order if i in self.docs]

    def document(self, item_id: str) -> Document:
        with self.lock:
            if item_id not in self.docs:
                raise KeyError(f"문서가 없거나 아직 해석 중입니다: {item_id}")
            return self.docs[item_id]

    # ── 비교 ────────────────────────────────────────
    def compare(self, a: str, b: str, opts: Optional[CompareOptions] = None) -> Dict[str, Any]:
        opts = opts or self.options
        key = ("cmp", a, b, opts.cache_key())
        with self.lock:
            if key in self._cache:
                return self._cache[key]
        da, db = self.document(a), self.document(b)
        t0 = time.time()
        res = compare_documents(da, db, opts)
        res["elapsed"] = round(time.time() - t0, 3)
        with self.lock:
            self._cache[key] = res
        self.log(f"비교: {da.name} → {db.name} : {res['headline']} ({res['elapsed']}초)")
        return res

    def render(self, a: str, b: Optional[str] = None, view: str = "merged",
               opts: Optional[CompareOptions] = None) -> Dict[str, Any]:
        """(v1.1) 원본 문서 모양 HTML. b 가 없으면 a 문서만 표시 없이 그린다."""
        opts = opts or self.options
        view = view if view in VIEWS else "merged"
        key = ("render", a, b or "", view, opts.cache_key())
        with self.lock:
            if key in self._cache:
                return self._cache[key]
        t0 = time.time()
        if not b:
            doc = self.document(a)
            out = render_plain(doc)
            out["changes"] = []
        else:
            res = self.compare(a, b, opts)
            out = render_view(self.document(a), self.document(b), res, view)
            by_id = {c["id"]: c for c in res["changes"]}
            out["changes"] = [{k: by_id[cid][k] for k in ("id", "type", "label", "location", "summary", "tags")}
                              for cid in out["order"] if cid in by_id]
            out["headline"] = res["headline"]
        out["elapsed"] = round(time.time() - t0, 3)
        with self.lock:
            self._cache[key] = out
        return out

    def history(self, opts: Optional[CompareOptions] = None, ids: Optional[List[str]] = None) -> Dict[str, Any]:
        opts = opts or self.options
        docs = [self.document(i) for i in ids] if ids else self.ready_docs()
        return build_history(docs, lambda x, y: self.compare(x.id, y.id, opts))

    # ── (v2.0) 병합 ─────────────────────────────────
    def merge_plan(self, base: str, versions: List[str]) -> Dict[str, Any]:
        versions = [v for v in versions if v != base]
        if not versions:
            raise ValueError("합칠 버전을 하나 이상 고르세요")
        key = ("plan", base, tuple(versions), self.options.cache_key())
        with self.lock:
            if key in self._cache:
                return self._cache[key]
        b = self.document(base)
        plan = plan_merge(b, [self.document(v) for v in versions], lambda x, y: self.compare(x.id, y.id))
        view = render_merge(b, plan)
        plan["html"] = view["html"]
        with self.lock:
            self._cache[key] = plan
        c = plan["counts"]
        self.log(f"병합 계획: 기준 {b.name} + {len(versions)}개 버전 → 항목 {c['items']}개, 충돌 {c['conflicts']}개")
        return plan

    def _merge_bytes(self, base: str, versions: List[str], choices: Dict[str, Any]):
        plan = self.merge_plan(base, versions)
        docs = {d: self.document(d) for d in [base] + versions}
        return apply_merge(self.document(base), docs, plan, choices or {})

    def merge_preview(self, base: str, versions: List[str], choices: Dict[str, Any]) -> Dict[str, Any]:
        data, report = self._merge_bytes(base, versions, choices)
        b = self.document(base)
        merged = load_document(data, name="병합 미리보기.hwpx", doc_id="preview")
        res = compare_documents(b, merged, self.options)
        view = render_view(b, merged, res, "merged")
        by_id = {c["id"]: c for c in res["changes"]}
        return {"html": view["html"], "headline": res["headline"], "report": report,
                "changes": [{k: by_id[cid][k] for k in ("id", "type", "label", "location", "summary", "tags")}
                            for cid in view["order"] if cid in by_id]}

    def merge_save(self, base: str, versions: List[str], choices: Dict[str, Any], name: str = "",
                   role: str = "final") -> Dict[str, Any]:
        data, report = self._merge_bytes(base, versions, choices)
        if not report["applied"]:
            raise ValueError("적용할 변경을 하나도 고르지 않았습니다")
        b = self.document(base)
        name = _hwpx_name(name or f"{os.path.splitext(b.name)[0]}_병합_{time.strftime('%m%d_%H%M')}")
        used = sorted({a["op_id"].split(":")[0] for a in report["applied"]})
        doc = self.add_generated(name, data, "merge", used or [base], role)
        if self.project:
            self.project.record_merge({"base": base, "versions": versions, "result": doc.id,
                                       "applied": len(report["applied"]), "skipped": len(report["skipped"])})
        self.log(f"병합 저장: {name} — 적용 {len(report['applied'])}건, 건너뜀 {len(report['skipped'])}건", "ok")
        return {"id": doc.id, "name": doc.name, "report": report, "path": self._project_path(doc.id)}

    # ── (v2.0) 직접 고치기 ───────────────────────────
    def edit_save(self, doc_id: str, edits: Dict[str, str], mark_color: Optional[str] = None,
                  name: str = "") -> Dict[str, Any]:
        d = self.document(doc_id)
        name = _hwpx_name(name or f"{os.path.splitext(d.name)[0]}_수정_{time.strftime('%m%d_%H%M')}")
        data, report = edit_document(d, {int(k): v for k, v in edits.items()}, mark_color, name)
        # 최종본을 고치면 새 문서가 최종본이 되고 이전 최종본은 보관으로 (프로젝트 폴더에서도 교체)
        role = "final" if self.roles.get(doc_id) == "final" else "revision"
        doc = self.add_generated(name, data, "edit", [doc_id], role)
        self.log(f"직접 고친 수정본 저장: {name} — {len(report['edited'])}곳", "ok")
        if report["check_failed"]:
            self.log("확인 필요: " + ", ".join(report["check_failed"]), "warn")
        return {"id": doc.id, "name": doc.name, "report": report, "path": self._project_path(doc.id)}

    # ── (v2.0) 파일·한글 ─────────────────────────────
    def file_bytes(self, doc_id: str) -> Tuple[bytes, str]:
        d = self.document(doc_id)
        return d.raw, d.name

    def _project_path(self, doc_id: str) -> str:
        if self.project and self.project.doc(doc_id):
            return self.project.path_of(doc_id)
        return ""

    def path_for(self, doc_id: str) -> str:
        """실제 파일 경로 (프로젝트 > 원래 위치 > 임시 폴더에 써서)."""
        p = self._project_path(doc_id)
        if p and os.path.exists(p):
            return p
        d = self.document(doc_id)
        if d.source_path and os.path.exists(d.source_path):
            with open(d.source_path, "rb") as f:
                if hashlib.sha1(f.read()).hexdigest() == d.sha1:
                    return d.source_path
        folder = os.path.join(tempfile.gettempdir(), "HWPX비교기")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{doc_id}_{d.name}")
        with open(path, "wb") as f:
            f.write(d.raw)
        return path

    def open_in_hangul(self, doc_id: str) -> str:
        path = self.path_for(doc_id)
        bridge.open_with_system(path)
        self.log(f"한글에서 열기: {path}")
        return path

    def hangul_resave(self, doc_id: str) -> Dict[str, Any]:
        """한글로 다시 저장 → 내용이 바뀌므로 새 문서로 다시 읽어 들인다 (원래 것은 그대로 둠)."""
        d = self.document(doc_id)
        folder = os.path.join(tempfile.gettempdir(), "HWPX비교기")
        os.makedirs(folder, exist_ok=True)
        tmp = os.path.join(folder, f"resave_{doc_id}.hwpx")
        with open(tmp, "wb") as f:
            f.write(d.raw)
        bridge.hangul_resave(tmp)
        with open(tmp, "rb") as f:
            data = f.read()
        name = _hwpx_name(f"{os.path.splitext(d.name)[0]}_한글저장")
        doc = self.add_generated(name, data, "edit", [doc_id], self.roles.get(doc_id, "revision"))
        return {"id": doc.id, "name": doc.name}

    def hangul_pdf(self, doc_id: str) -> str:
        d = self.document(doc_id)
        src = self.path_for(doc_id)
        stem = os.path.splitext(d.name)[0] + ".pdf"
        out = self.project.report_path(stem) if self.project else os.path.join(os.path.dirname(src), stem)
        bridge.hangul_pdf(src, out)
        self.log(f"PDF 저장: {out}", "ok")
        return out

    # ── (v2.0) 프로젝트 ─────────────────────────────
    def _sync_from_project(self) -> None:
        if not self.project:
            return
        self.roles = self.project.roles()
        self.parents = {**self.parents, **self.project.parents()}
        self.origins.update({d["id"]: d.get("origin", "import") for d in self.project.documents})
        self.positions = dict(self.project.data["graph"]["positions"])

    def project_create(self, folder: str, name: str = "") -> Dict[str, Any]:
        proj = Project.create(folder, name)
        with self.lock:
            self.project = proj
            docs = self.ready_docs()
        lin = self.lineage() if len(docs) > 1 else {"original": docs[0].id if docs else None, "final": None,
                                                   "nodes": []}
        parent_of = {n["id"]: n["parents"] for n in lin["nodes"]}
        for d in docs:
            role = self.roles.get(d.id) or ("original" if d.id == lin["original"]
                                            else "final" if d.id == lin.get("final") else "revision")
            proj.add(d.id, d.name, d.raw, d.sha1, role, parents=self.parents.get(d.id) or parent_of.get(d.id),
                     origin=self.origins.get(d.id, "import"), meta=d.meta)
        if self.positions:
            proj.set_positions(self.positions)
        with self.lock:
            self._sync_from_project()
            self._invalidate()
        self.log(f"프로젝트 만듦: {proj.folder} (문서 {len(docs)}개)", "ok")
        return proj.summary()

    def project_open(self, folder: str) -> Dict[str, Any]:
        proj = Project.open(folder)
        self.reset()
        with self.lock:
            self.project = proj
            self._sync_from_project()
        missing = []
        for e in proj.documents:
            path = os.path.join(proj.folder, e["file"])
            if os.path.exists(path):
                self.submit_path(path, item_id=e["id"])
                with self.lock:
                    self.items[e["id"]]["name"] = e["name"]
            else:
                missing.append(e["name"])
        self.log(f"프로젝트 열기: {proj.folder} (문서 {len(proj.documents)}개)", "ok")
        if missing:
            self.log("파일이 없는 문서: " + ", ".join(missing), "warn")
        return proj.summary()

    def project_close(self) -> None:
        with self.lock:
            self.project = None
        self.log("프로젝트를 닫았습니다 (불러온 문서는 그대로)")

    def project_info(self) -> Optional[Dict[str, Any]]:
        return self.project.summary() if self.project else None

    def save_report(self, filename: str, data: bytes) -> str:
        if not self.project:
            raise ValueError("프로젝트가 열려 있지 않습니다")
        path = self.project.report_path(filename)
        with open(path, "wb") as f:
            f.write(data)
        self.project.log("report", f"보고서 저장: {os.path.basename(path)}")
        return path


def _hwpx_name(name: str) -> str:
    name = "".join(c for c in name if c not in '\\/:*?"<>|').strip() or "문서"
    return name if name.lower().endswith(".hwpx") else name + ".hwpx"
