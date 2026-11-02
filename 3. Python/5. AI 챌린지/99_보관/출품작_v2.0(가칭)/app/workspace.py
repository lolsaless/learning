# -*- coding: utf-8 -*-
"""조립부: 작업 폴더 하나를 열고, 기능 파트들을 만들어 서로 연결한다.

이 파일에는 계산이 없다. "어떤 파트를 어떤 순서로 부르는지"만 적는다.
기능을 고칠 때는 해당 파트 폴더(app/parts/<이름>/)를 보면 된다.

  파트            하는 일                                   폴더
  ─────────────────────────────────────────────────────────────────
  원본            원본 등록·읽기·변경 확인·셀 읽기           parts/sources
  문서            대상 문서·작업본 버전                      parts/document
  검증            원본 대조·재계산·결과 정리                 parts/verify
  수정·입력       대기 목록·입력하기·출처 확정               parts/edit
  이력            값 이력·버전·원본 변경 기록 조회           parts/history
  내보내기        출처대장·검증표시본·검증보고               parts/export
  클립보드        엑셀 복사 위치 기록(Windows)               parts/clip

작업 폴더 구성
  <작업 폴더>/작업장부.db   ← 이력 장부(값 이력·출처·원본 변경·검증 기록)
  <작업 폴더>/작업본/       ← 누름틀을 씌운 문서 버전(v001, v002 …). 원본 문서는 건드리지 않음
  <작업 폴더>/내보내기/     ← 출처대장(xlsx)·검증표시본(hwpx)·검증보고(html)
  <작업 폴더>/백업/         ← 이력 장부 하루 1회 자동 백업
"""
import os
import getpass

from app import config
from app.common.context import Context
from app.common.errors import WorkError          # noqa: F401  (밖에서 workspace.WorkError 로도 쓰게 함)
from app.store.ledger import Ledger

from app.parts.sources.part import SourcesPart
from app.parts.document.part import DocumentPart
from app.parts.verify.part import VerifyPart
from app.parts.edit.part import EditPart
from app.parts.history.part import HistoryPart
from app.parts.export.part import ExportPart
from app.parts.clip.part import ClipPart


def _default_user():
    try:
        return getpass.getuser()
    except Exception:
        return "사용자"


class Workspace:
    def __init__(self, folder, user=None):
        folder = os.path.abspath(folder)
        for d in ("", config.DIR_WORKCOPY, config.DIR_EXPORT, config.DIR_BACKUP):
            os.makedirs(os.path.join(folder, d), exist_ok=True)
        db = Ledger(os.path.join(folder, config.DB_NAME))
        self.ctx = Context(folder, db, user or db.meta("user") or _default_user())

        # 파트 만들기 + 연결(원본을 읽을 때마다 검증 파트 색인에 넣는다)
        self.verifier = VerifyPart(self.ctx)
        self.sources = SourcesPart(self.ctx, on_load=self.verifier.add_book, on_unload=self.verifier.remove_book)
        self.document = DocumentPart(self.ctx)
        self.edit = EditPart(self.ctx)
        self.hist = HistoryPart(self.ctx)
        self.exporter = ExportPart(self.ctx)
        self.clip = ClipPart(self.ctx)

        self.sources.load_all()
        db.backup(self.ctx.path(config.DIR_BACKUP))

    # ── 자주 쓰는 값(다른 곳에서 ws.db, ws.folder … 로 읽음) ──
    @property
    def db(self):
        return self.ctx.db

    @property
    def folder(self):
        return self.ctx.folder

    @property
    def user(self):
        return self.ctx.user

    @property
    def lock(self):
        return self.ctx.lock

    @property
    def last(self):
        return self.verifier.last

    # ── 상태 ──────────────────────────────────────────
    def state(self):
        db = self.db
        L = self.verifier.last
        return {"folder": self.folder, "user": self.user,
                "target": db.meta("target_path"), "target_name": db.meta("target_name"),
                "version": db.last_version(), "versions": db.versions(),
                "sources": self.sources.rows(), "pending": db.pending(),
                "last_run": L["summary"] if L else None,
                "base_folder": self.sources.base_folder()}

    def set_user(self, name):
        self.ctx.user = (name or "").strip() or self.ctx.user
        self.db.set_meta("user", self.ctx.user)

    # ── 문서 ──────────────────────────────────────────
    def set_target(self, path):
        with self.lock:
            return self.document.set_target(path)

    def current_path(self):
        return self.document.current_path()

    def doc(self, fresh=False):
        return self.document.doc(fresh)

    def detect_manual_edits(self):
        return self.document.detect_manual_edits()

    # ── 원본 ──────────────────────────────────────────
    def add_sources(self, paths, role=None):
        with self.lock:
            return self.sources.add(paths, role)

    def remove_source(self, sid):
        with self.lock:
            self.sources.remove(sid)

    def set_role(self, sid, role):
        self.sources.set_role(sid, role)

    def check_sources(self):
        with self.lock:
            return self.sources.check(self.verifier.affected_by_source())

    def grid(self, sid, sheet, r0=0, c0=0, nr=60, nc=26):
        return self.sources.grid(sid, sheet, r0, c0, nr, nc)

    # ── 검증 ──────────────────────────────────────────
    def verify(self):
        with self.lock:
            edits = self.document.detect_manual_edits()
            doc = self.document.doc()
            s = self.sources
            self.verifier.run(doc, s.names(), s.paths(), s.roles(), self.clip.clips(),
                              self.db.confirms(), self.edit.pending(), edits)
            return self.view()

    def view(self):
        return self.verifier.view(self.document.doc(), self.edit.pending(), self.sources.names())

    def slot_detail(self, key):
        it = self.document.doc().item(key)
        if not it:
            raise WorkError("칸을 찾을 수 없습니다")
        d = self.verifier.slot_detail(it)
        d.update(item=it.public(), events=self.hist.slot_events(key),
                 confirmed=self.db.confirms().get(key),
                 pending=next((p for p in self.edit.pending() if p["slot"] == key), None))
        return d

    # ── 수정·입력 ─────────────────────────────────────
    def set_pending(self, slot, new, method, sid=None, ref=None, reason=""):
        with self.lock:
            src = self.sources.info(sid) if sid else None
            return self.edit.set_pending(self.document.doc(), slot, new, method, src, ref, reason)

    def drop_pending(self, slot=None):
        return self.edit.drop_pending(slot)

    def fix_from_source(self, slot, sid, ref_text, value_text, reason="원본 값으로 수정"):
        return self.set_pending(slot, value_text, "원본 값으로 수정", sid, ref_text, reason)

    def input_values(self, sid, sheet, r0, c0, r1, c1, start_slot, dec=None, scale=1.0, comma=True):
        with self.lock:
            r0, r1 = sorted((r0, r1))
            c0, c1 = sorted((c0, c1))
            src = self.sources.info(sid)
            if not src or sid not in self.sources.books:
                raise WorkError("원본을 읽을 수 없습니다")
            cells = self.sources.cells(sid, sheet, r0, c0, r1, c1, dec, scale, comma)
            reason = (f"배율 {scale:g}" if scale != 1.0 else "") + (f" 소수 {dec}자리" if dec is not None else "")
            return self.edit.input_values(self.document.doc(), start_slot, src, cells,
                                          lambda r, c: self.sources.ref_text(sid, sheet, r, c),
                                          r0, c0, r1, c1, reason)

    def confirm(self, slot, sid, ref_text):
        with self.lock:
            r = self.edit.confirm(self.document.doc(), slot, self.sources.info(sid), ref_text)
            self.verifier.mark_confirmed(slot)
            return r

    def unconfirm(self, slot):
        return self.edit.unconfirm(slot)

    def save_version(self, note=""):
        with self.lock:
            pend = self.edit.pending()
            if not pend:
                raise WorkError("저장할 변경이 없습니다")
            self.document.detect_manual_edits()
            r = self.document.write_version(pend, note)
            self.edit.after_save(r["ver"], r["done"])
            self.db.backup(self.ctx.path(config.DIR_BACKUP))
            return {"ok": True, "ver": r["ver"], "path": r["path"], "count": len(r["done"])}

    # ── 이력·내보내기·클립보드 ────────────────────────
    def history(self, slot=None):
        return self.hist.history(slot)

    def export(self):
        with self.lock:
            if not self.last:
                self.verify()
            return self.exporter.export(self)

    def record_clip(self, clip):
        return self.clip.record(clip)
