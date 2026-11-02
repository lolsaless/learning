# -*- coding: utf-8 -*-
"""[문서 파트] 검증할 한글 문서(hwpx)와 그 작업본 버전(v001, v002 …)을 관리한다.

원본 문서는 절대 고치지 않는다. 처음 선택할 때 숫자마다 누름틀을 씌운 '작업본 v001'을
작업 폴더에 만들고, 저장할 때마다 새 버전 파일을 하나씩 더 만든다.

입구: set_target(경로), doc(), detect_manual_edits(), write_version(바꿀 값들, 메모)
출구: 작업본 HwpxDoc, 버전 정보
"""
import os

from app import config
from app.common.errors import WorkError
from app.common.files import sha256
from app.formats.hwpx import HwpxDoc, HwpxError


class DocumentPart:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self._doc = None
        self._doc_key = None

    def _workcopy(self, ver):
        stem = self.db.meta("stem") or "문서"
        return self.ctx.path(config.DIR_WORKCOPY, f"{stem}_v{ver:03d}.hwpx")

    def set_target(self, path):
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            raise WorkError("문서 파일을 찾을 수 없습니다")
        if not path.lower().endswith(".hwpx"):
            raise WorkError("hwpx 파일만 사용할 수 있습니다(구형 hwp는 한글에서 hwpx로 저장해 주세요)")
        if self.db.versions():
            raise WorkError("이 작업 폴더에는 이미 대상 문서가 있습니다. 새 문서는 새 작업 폴더에서 시작하세요")
        try:
            doc = HwpxDoc(path)
        except HwpxError as e:
            raise WorkError(str(e))
        n = doc.make_fields()
        stem = os.path.splitext(os.path.basename(path))[0]
        self.db.set_meta("stem", stem)
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
            self._doc = HwpxDoc(p)
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
