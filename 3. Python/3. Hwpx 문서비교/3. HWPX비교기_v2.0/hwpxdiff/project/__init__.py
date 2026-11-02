"""프로젝트(이력 관리) (v2.0) — 비교한 문서 여러 개를 한 폴더에 역할별로 모으고, 관계·작업 기록을 JSON 으로 남긴다.

폴더 구조 (사용자가 고른 폴더 아래)
    project.json      이력 기록 (문서 목록·역할·부모 관계·관계도 위치·작업 기록·병합 기록)
    1_원본/            원본 1개
    2_수정본/          수정본들 (직접 고친 수정본 포함)
    3_최종본/          최종본 1개 — 새 최종본이 생기면 이전 것은 4_보관 으로 옮겨지고 교체됨
    4_보관/            예전 최종본 (지우지 않음 — 이름 앞에 보관 시각)
    5_보고서/          저장한 보고서

project.json (schema "hwpx-project/1")
    {"schema", "name", "created", "updated",
     "documents": [{"id", "name", "file"(폴더 기준 상대경로), "sha1", "size", "role", "origin"(import|merge|edit),
                    "parents": [id...], "added", "modified", "author", "note"}],
     "graph": {"positions": {id: [x, y]}},
     "events": [{"time", "type", "detail"}],
     "merges": [{"time", "base", "versions", "result", "applied", "skipped"}]}
"""
from __future__ import annotations

import json
import os
import shutil
import time
from typing import Any, Dict, List, Optional

SCHEMA = "hwpx-project/1"
FILE = "project.json"
FOLDERS = {"original": "1_원본", "revision": "2_수정본", "final": "3_최종본", "archived": "4_보관"}
REPORTS = "5_보고서"
ROLE_LABELS = {"original": "원본", "revision": "수정본", "final": "최종본", "archived": "보관"}


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


class ProjectError(Exception):
    pass


class Project:
    def __init__(self, folder: str, data: Dict[str, Any]):
        self.folder = os.path.abspath(folder)
        self.data = data

    # ── 만들기·열기·저장 ─────────────────────────────
    @staticmethod
    def exists(folder: str) -> bool:
        return os.path.isfile(os.path.join(folder, FILE))

    @classmethod
    def create(cls, folder: str, name: str = "") -> "Project":
        folder = os.path.abspath(os.path.expanduser(folder.strip().strip('"')))
        if cls.exists(folder):
            raise ProjectError(f"이미 프로젝트가 있는 폴더입니다 (열기를 쓰세요): {folder}")
        os.makedirs(folder, exist_ok=True)
        for sub in list(FOLDERS.values()) + [REPORTS]:
            os.makedirs(os.path.join(folder, sub), exist_ok=True)
        p = cls(folder, {"schema": SCHEMA, "name": name or os.path.basename(folder), "created": now(),
                         "updated": now(), "documents": [], "graph": {"positions": {}}, "events": [], "merges": []})
        p.log("create", f"프로젝트 만듦: {p.data['name']}")
        return p

    @classmethod
    def open(cls, folder: str) -> "Project":
        folder = os.path.abspath(os.path.expanduser(folder.strip().strip('"')))
        path = os.path.join(folder, FILE)
        if not os.path.isfile(path):
            raise ProjectError(f"project.json 이 없는 폴더입니다: {folder}")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("schema") != SCHEMA:
            raise ProjectError(f"알 수 없는 프로젝트 형식: {data.get('schema')}")
        data.setdefault("graph", {"positions": {}})
        data.setdefault("events", [])
        data.setdefault("merges", [])
        for sub in list(FOLDERS.values()) + [REPORTS]:
            os.makedirs(os.path.join(folder, sub), exist_ok=True)
        return cls(folder, data)

    def save(self) -> None:
        self.data["updated"] = now()
        path = os.path.join(self.folder, FILE)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)                  # 쓰는 도중 꺼져도 project.json 이 깨지지 않게

    def log(self, typ: str, detail: str) -> None:
        self.data["events"].append({"time": now(), "type": typ, "detail": detail})
        self.save()

    # ── 조회 ───────────────────────────────────────
    @property
    def documents(self) -> List[Dict[str, Any]]:
        return self.data["documents"]

    def doc(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return next((d for d in self.documents if d["id"] == doc_id), None)

    def path_of(self, doc_id: str) -> str:
        d = self.doc(doc_id)
        if not d:
            raise ProjectError(f"프로젝트에 없는 문서: {doc_id}")
        return os.path.join(self.folder, d["file"])

    def roles(self) -> Dict[str, str]:
        return {d["id"]: d["role"] for d in self.documents}

    def parents(self) -> Dict[str, List[str]]:
        return {d["id"]: d.get("parents", []) for d in self.documents if d.get("parents")}

    def summary(self) -> Dict[str, Any]:
        return {"folder": self.folder, "name": self.data["name"], "created": self.data["created"],
                "updated": self.data["updated"], "documents": self.documents,
                "events": self.data["events"][-50:], "merges": self.data["merges"][-20:],
                "folders": {k: os.path.join(self.folder, v) for k, v in FOLDERS.items()},
                "reports": os.path.join(self.folder, REPORTS)}

    # ── 문서 넣기·역할 바꾸기 ───────────────────────────
    def add(self, doc_id: str, name: str, data: bytes, sha1: str, role: str = "revision",
            parents: Optional[List[str]] = None, origin: str = "import", meta: Optional[Dict[str, str]] = None,
            note: str = "") -> Dict[str, Any]:
        old = self.doc(doc_id) or next((d for d in self.documents if d["sha1"] == sha1), None)
        if old:
            return old
        role = role if role in FOLDERS else "revision"
        meta = meta or {}
        entry = {"id": doc_id, "name": name, "file": "", "sha1": sha1, "size": len(data), "role": "revision",
                 "origin": origin, "parents": list(parents or []), "added": now(),
                 "modified": meta.get("ModifiedDate", ""), "author": meta.get("lastsaveby", ""), "note": note}
        rel = self._free_name(FOLDERS["revision"], name)
        with open(os.path.join(self.folder, rel), "wb") as f:
            f.write(data)
        entry["file"] = rel
        self.documents.append(entry)
        self.log("add", f"{name} 추가 ({ {'import': '가져옴', 'merge': '병합으로 만듦', 'edit': '직접 고침'}.get(origin, origin)})")
        if role != "revision":
            self.set_role(doc_id, role)
        else:
            self.save()
        return entry

    def set_role(self, doc_id: str, role: str) -> List[str]:
        """역할 바꾸기 + 파일을 해당 폴더로 옮김. 원본·최종본은 하나뿐이라 기존 것은 밀려난다. 돌려줌: 바뀐 내용 문장들."""
        if role not in FOLDERS:
            raise ProjectError(f"알 수 없는 역할: {role}")
        d = self.doc(doc_id)
        if not d:
            raise ProjectError(f"프로젝트에 없는 문서: {doc_id}")
        msgs = []
        if role in ("original", "final"):
            for other in self.documents:
                if other is not d and other["role"] == role:
                    demote = "archived" if role == "final" else "revision"
                    self._move(other, demote)
                    msgs.append(f"이전 {ROLE_LABELS[role]} {other['name']} → {ROLE_LABELS[demote]}")
        self._move(d, role)
        msgs.append(f"{d['name']} → {ROLE_LABELS[role]}")
        self.log("role", " / ".join(msgs))
        return msgs

    def set_parents(self, doc_id: str, parents: List[str]) -> None:
        d = self.doc(doc_id)
        if not d:
            raise ProjectError(f"프로젝트에 없는 문서: {doc_id}")
        d["parents"] = [p for p in parents if p != doc_id and self.doc(p)]
        names = ", ".join(self.doc(p)["name"] for p in d["parents"]) or "없음"
        self.log("parents", f"{d['name']} 의 부모 문서를 {names} 로 지정")

    def set_positions(self, positions: Dict[str, List[float]]) -> None:
        self.data["graph"]["positions"].update(positions)
        self.save()

    def record_merge(self, info: Dict[str, Any]) -> None:
        self.data["merges"].append({"time": now(), **info})
        self.save()

    def remove(self, doc_id: str) -> None:
        """목록에서만 뺀다 (파일은 4_보관 으로 옮겨 남김)."""
        d = self.doc(doc_id)
        if not d:
            return
        self._move(d, "archived")
        self.documents.remove(d)
        self.data["graph"]["positions"].pop(doc_id, None)
        self.log("remove", f"{d['name']} 을(를) 목록에서 뺌 (파일은 4_보관 에 남김)")

    # ── 내부 ───────────────────────────────────────
    def _move(self, d: Dict[str, Any], role: str) -> None:
        target_dir = FOLDERS[role]
        src = os.path.join(self.folder, d["file"])
        if os.path.dirname(d["file"]) != target_dir or not os.path.exists(src):
            base = os.path.basename(d["file"]) or d["name"]
            if role == "archived" and d["role"] == "final":
                base = time.strftime("%Y%m%d_%H%M%S_") + base
            rel = self._free_name(target_dir, base)
            if os.path.exists(src):
                shutil.move(src, os.path.join(self.folder, rel))
            d["file"] = rel
        d["role"] = role

    def _free_name(self, sub: str, name: str) -> str:
        stem, ext = os.path.splitext(os.path.basename(name) or "문서.hwpx")
        ext = ext or ".hwpx"
        k = 0
        while True:
            cand = f"{stem}{'' if k == 0 else f'_{k}'}{ext}"
            rel = os.path.join(sub, cand)
            if not os.path.exists(os.path.join(self.folder, rel)):
                return rel
            k += 1

    def report_path(self, filename: str) -> str:
        return os.path.join(self.folder, self._free_name(REPORTS, filename))
