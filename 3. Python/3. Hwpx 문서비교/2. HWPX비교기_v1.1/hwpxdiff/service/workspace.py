"""작업공간 — 불러온 문서 목록, 백그라운드 해석 작업, 진행상황, 로그, 비교 결과 캐시.

서버(server/)는 이 클래스의 메서드만 호출한다. 화면 없이 파이썬에서 직접 써도 된다:
    ws = Workspace(); ws.submit_path("a.hwpx"); ws.wait(); ws.history()
"""
from __future__ import annotations

import os
import queue
import threading
import time
import uuid
from collections import deque
from typing import Any, Dict, List, Optional, Union

from ..compare import CompareOptions, build_history, compare_documents, order_documents
from ..hwpx import HwpxError, load_document
from ..hwpx.model import Document
from ..render import VIEWS, render_plain, render_view

SUPPORTED_EXT = (".hwpx",)


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
        self._cache: Dict[tuple, Dict[str, Any]] = {}
        self._jobs: "queue.Queue[tuple]" = queue.Queue()
        self._worker = threading.Thread(target=self._run, name="hwpx-parser", daemon=True)
        self._worker.start()

    # ── 로그 ────────────────────────────────────────
    def log(self, msg: str, level: str = "info") -> None:
        with self.lock:
            self._log_seq += 1
            self.logs.append({"id": self._log_seq, "time": time.strftime("%H:%M:%S"),
                              "level": level, "msg": msg})

    # ── 파일 넣기 ────────────────────────────────────
    def submit_bytes(self, name: str, data: bytes, rel_path: str = "") -> str:
        return self._enqueue(name, data, rel_path or name)

    def submit_path(self, path: str) -> str:
        return self._enqueue(os.path.basename(path), path, path)

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

    def _enqueue(self, name: str, src: Union[str, bytes], label: str) -> str:
        item_id = uuid.uuid4().hex[:10]
        with self.lock:
            self.items[item_id] = {"id": item_id, "name": name, "label": label, "status": "queued",
                                   "error": "", "added": time.time(), "duplicate_of": ""}
            self.order.append(item_id)
        self.log(f"대기열 추가: {name}")
        self._jobs.put((item_id, name, src))
        return item_id

    # ── 백그라운드 해석 ───────────────────────────────
    def _run(self) -> None:
        while True:
            item_id, name, src = self._jobs.get()
            with self.lock:
                item = self.items.get(item_id)
                if item is None:           # 해석 전에 삭제됨
                    continue
                item["status"] = "parsing"
            t0 = time.time()
            try:
                doc = load_document(src, name=name, doc_id=item_id)
            except (HwpxError, OSError, ValueError) as e:
                with self.lock:
                    if item_id in self.items:
                        self.items[item_id].update(status="error", error=str(e))
                self.log(f"해석 실패: {name} — {e}", "error")
                continue
            except Exception as e:  # 예상 못 한 오류도 화면에 보이게
                with self.lock:
                    if item_id in self.items:
                        self.items[item_id].update(status="error", error=f"{type(e).__name__}: {e}")
                self.log(f"해석 실패(예상 밖 오류): {name} — {type(e).__name__}: {e}", "error")
                continue
            with self.lock:
                if item_id not in self.items:
                    continue
                dup = next((d.name for d in self.docs.values() if d.sha1 == doc.sha1), "")
                self.docs[item_id] = doc
                self.items[item_id].update(status="ready", duplicate_of=dup)
                if self.order_mode != "manual":
                    self._sort(self.order_mode)
            s = doc.stats
            self.log(f"해석 완료: {name} — 문단 {s.get('paragraphs', 0)}, 표 {s.get('tables', 0)}, "
                     f"셀 {s.get('cells', 0)} ({time.time() - t0:.2f}초)", "ok")
            if dup:
                self.log(f"주의: {name} 은(는) {dup} 와(과) 내용이 완전히 같은 파일입니다", "warn")
            for w in doc.warnings:
                self.log(f"{name}: {w}", "warn")

    def wait(self, timeout: float = 60) -> None:
        """모든 해석이 끝날 때까지 기다림 (테스트·명령줄용)."""
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                if all(i["status"] in ("ready", "error") for i in self.items.values()):
                    return
            time.sleep(0.05)

    # ── 목록 관리 ────────────────────────────────────
    def remove(self, item_id: str) -> None:
        with self.lock:
            item = self.items.pop(item_id, None)
            self.docs.pop(item_id, None)
            if item_id in self.order:
                self.order.remove(item_id)
            self._cache = {k: v for k, v in self._cache.items() if item_id not in k[:3]}
        if item:
            self.log(f"목록에서 뺌: {item['name']}")

    def reset(self) -> None:
        with self.lock:
            self.items.clear()
            self.docs.clear()
            self.order.clear()
            self._cache.clear()
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
            return self.options

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
                items.append(it)
            total = len(items)
            done = sum(1 for i in items if i["status"] in ("ready", "error"))
            return {
                "items": items, "order_mode": self.order_mode, "options": self.options.to_dict(),
                "progress": {"total": total, "done": done,
                             "busy": done < total,
                             "parsing": next((i["name"] for i in items if i["status"] == "parsing"), "")},
                "logs": [l for l in self.logs if l["id"] > since_log],
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
        key = (a, b, opts.cache_key())
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
