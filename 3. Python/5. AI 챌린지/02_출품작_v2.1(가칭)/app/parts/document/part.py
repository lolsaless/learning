# -*- coding: utf-8 -*-
"""[문서 파트] 검증할 한글 문서(hwpx)와 그 작업본 버전(v001, v002 …)을 관리한다.

원본 문서는 절대 고치지 않는다. 처음 선택할 때 숫자마다 누름틀을 씌운 '작업본 v001'을
작업 폴더에 만들고, 저장할 때마다 새 버전 파일을 하나씩 더 만든다.
hwpx 가 아닌 문서(hwp·docx·odt·pdf·txt·md·html)는 '읽기 전용 검증': 사본을 v001 로 두고 대조·재계산만 한다.
글 붙여넣기(set_target_text): AI 가 쓴 초안 등을 작업 폴더에 .md 로 저장해 검증 대상으로 쓴다.

입구: set_target(경로), doc(), detect_manual_edits(), write_version(바꿀 값들, 메모)
출구: 작업본 HwpxDoc, 버전 정보
"""
import os

from app import config
from app.common.errors import WorkError
from app.common.files import sha256
import shutil
import datetime

from app.formats import registry
from app.formats.hwpx import HwpxDoc, HwpxError


class DocumentPart:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self._doc = None
        self._doc_key = None

    def _workcopy(self, ver, ext=None):
        stem = self.db.meta("stem") or "문서"
        ext = ext or self.db.meta("target_ext") or ".hwpx"
        return self.ctx.path(config.DIR_WORKCOPY, f"{stem}_v{ver:03d}{ext}")

    def read_only(self):
        return (self.db.meta("target_ext") or ".hwpx") != ".hwpx"

    def set_target(self, path):
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            raise WorkError("문서 파일을 찾을 수 없습니다")
        if self.db.versions():
            raise WorkError("이 작업 폴더에는 이미 대상 문서가 있습니다. 새 문서는 새 작업 폴더에서 시작하세요")
        ext = registry.ext_of(path)
        if ext != ".hwpx":
            return self._set_target_readonly(path, ext)
        try:
            doc = HwpxDoc(path)
        except HwpxError as e:
            raise WorkError(str(e))
        n = doc.make_fields()
        stem = os.path.splitext(os.path.basename(path))[0]
        self.db.set_meta("stem", stem)
        self.db.set_meta("target_ext", ".hwpx")
        out = self._workcopy(1)
        doc.save(out)
        sh = sha256(out)
        self.db.set_meta("target_path", path)
        self.db.set_meta("target_name", os.path.basename(path))
        self.db.set_meta("target_sha", sha256(path))
        self.db.add_version(1, out, sh, f"작업본 생성(누름틀 {n}개)", self.ctx.user)
        doc2 = HwpxDoc(out)
        for it in doc2.items:
            self.db.add_event(ver=1, slot=it.key, label=it.label, old=None, new=it.raw, method="작업본 생성",
                              source_path=path, reason="원본 문서의 처음 값", user=self.ctx.user)
        self._doc, self._doc_key = doc2, None
        return {"workcopy": out, "fields": n, "items": len(doc2.items)}

    def _set_target_readonly(self, path, ext):
        doc = registry.open_target(path)          # 형식이 안 맞으면 WorkError(이유)
        if not doc.items:
            raise WorkError("문서에서 숫자를 찾지 못했습니다" + (f" — {'; '.join(doc.warnings)}" if doc.warnings else ""))
        stem = os.path.splitext(os.path.basename(path))[0]
        self.db.set_meta("stem", stem)
        self.db.set_meta("target_ext", ext)
        out = self._workcopy(1, ext)
        shutil.copy2(path, out)                   # 원본은 그대로, 사본을 작업본 v001 로
        self.db.set_meta("target_path", path)
        self.db.set_meta("target_name", os.path.basename(path))
        self.db.set_meta("target_sha", sha256(path))
        self.db.add_version(1, out, sha256(out), f"읽기 전용 검증({ext[1:]})", self.ctx.user)
        for it in doc.items:
            self.db.add_event(ver=1, slot=it.key, label=it.label, old=None, new=it.raw, method="작업본 생성",
                              source_path=path, reason="원본 문서의 처음 값", user=self.ctx.user)
        self._doc, self._doc_key = None, None
        return {"workcopy": out, "fields": 0, "items": len(doc.items), "read_only": True,
                "warnings": doc.warnings}

    def set_target_text(self, text, name=""):
        """붙여 넣은 글(AI 초안 등)을 작업 폴더에 저장하고 검증 대상으로 삼는다."""
        if not (text or "").strip():
            raise WorkError("검증할 글을 붙여 넣으세요")
        if self.db.versions():
            raise WorkError("이 작업 폴더에는 이미 대상 문서가 있습니다. 새 글은 새 작업 폴더에서 검증하세요")
        safe = "".join(ch for ch in (name or "") if ch.isalnum() or ch in " _-()가-힣").strip() or "붙여넣은글"
        folder = self.ctx.path("입력글")
        os.makedirs(folder, exist_ok=True)
        p = os.path.join(folder, f"{safe}_{datetime.datetime.now():%Y%m%d_%H%M%S}.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return self.set_target(p)

    def current_path(self):
        v = self.db.last_version()
        return v["path"] if v else None

    def doc(self, fresh=False):
        p = self.current_path()
        if not p:
            raise WorkError("먼저 대상 문서(hwpx)를 선택하세요")
        if not os.path.exists(p):
            raise WorkError(f"작업본 파일이 없습니다: {p}")
        key = (p, os.path.getmtime(p), os.path.getsize(p))
        if fresh or self._doc is None or self._doc_key != key:
            self._doc = HwpxDoc(p) if p.lower().endswith(".hwpx") else registry.open_target(p)
            self._doc_key = key
        return self._doc

    def detect_manual_edits(self):
        """작업본을 한글에서 직접 고쳐 저장했으면 바뀐 칸을 이력에 남긴다."""
        v = self.db.last_version()
        if not v or not os.path.exists(v["path"]):
            return []
        sh = sha256(v["path"])
        if sh == v["sha"]:
            return []
        doc = self.doc(fresh=True)
        last = self.db.last_values()
        changed = []
        for it in doc.items:
            if it.key in last and (last[it.key] or "") != (it.raw or ""):
                self.db.add_event(ver=v["ver"], slot=it.key, label=it.label, old=last[it.key], new=it.raw,
                                  method="한글에서 직접 수정", reason="작업본 파일이 프로그램 밖에서 바뀜", user=self.ctx.user)
                changed.append({"slot": it.key, "label": it.label, "old": last[it.key], "new": it.raw})
            elif it.key not in last:
                self.db.add_event(ver=v["ver"], slot=it.key, label=it.label, old=None, new=it.raw,
                                  method="한글에서 직접 수정", reason="새로 생긴 칸", user=self.ctx.user)
        self.db.update_version_sha(v["ver"], sh)
        return changed

    def write_version(self, changes, note=""):
        """changes: [{"slot":…, "new":…}, …] 를 반영한 새 작업본 버전을 만든다.
        저장한 파일을 다시 읽어 값이 제대로 들어갔는지 확인하고, 틀리면 파일을 지우고 멈춘다."""
        if self.read_only():
            raise WorkError("이 문서는 읽기 전용 형식이라 프로그램에서 고칠 수 없습니다. 원래 프로그램에서 고친 뒤 다시 검증하세요")
        doc = self.doc(fresh=True)
        ver = self.db.last_version()["ver"] + 1
        done = []
        for p in changes:
            it = doc.item(p["slot"])
            if not it:
                continue
            ok = doc.set_field(it.key, p["new"]) if it.field else doc.set_text_at(it, p["new"])
            if ok:
                done.append(p)
        out = self._workcopy(ver)
        doc.save(out)
        chk = HwpxDoc(out)
        bad = [p["slot"] for p in done if (chk.item(p["slot"]).raw if chk.item(p["slot"]) else None) != p["new"]]
        if bad:
            os.remove(out)
            raise WorkError(f"저장 확인 실패({len(bad)}칸). 작업본을 바꾸지 않았습니다: {', '.join(bad[:5])}")
        self.db.add_version(ver, out, sha256(out), note or f"{len(done)}칸 수정", self.ctx.user)
        self._doc = None
        return {"ver": ver, "path": out, "done": done}
