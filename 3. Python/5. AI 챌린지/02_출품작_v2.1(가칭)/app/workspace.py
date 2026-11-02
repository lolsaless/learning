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
  AI              문장 검산(규칙+선택 AI)·요약 초안           parts/ai
  재제출 비교     새로 받은 원본과 이전 원본 칸 비교          parts/compare

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
from app.formats import registry
from app.store.ledger import Ledger

from app.parts.sources.part import SourcesPart
from app.parts.document.part import DocumentPart
from app.parts.verify.part import VerifyPart
from app.parts.edit.part import EditPart
from app.parts.history.part import HistoryPart
from app.parts.export.part import ExportPart
from app.parts.clip.part import ClipPart
from app.parts.ai.part import AiPart
from app.parts.compare.part import ComparePart


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
        self.ai = AiPart(self.ctx)
        self.compare = ComparePart(self.ctx)
        self.use_ai = False             # [AI 로 문장 읽기]를 누르면 다음 검증부터 AI 도 사용

        self.sources.load_all()
        for src in db.sources():                       # 지금 판을 보관(재제출 비교의 '이전 판')
            self.compare.archive(src["sid"], src["path"], src["sha"])
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
                "base_folder": self.sources.base_folder(),
                "read_only": bool(db.versions()) and self.document.read_only(),
                "target_ext": db.meta("target_ext")}

    def set_user(self, name):
        self.ctx.user = (name or "").strip() or self.ctx.user
        self.db.set_meta("user", self.ctx.user)

    # ── 문서 ──────────────────────────────────────────
    def set_target(self, path):
        with self.lock:
            return self.document.set_target(path)

    def set_target_text(self, text, name=""):
        with self.lock:
            return self.document.set_target_text(text, name)

    def current_path(self):
        return self.document.current_path()

    def doc(self, fresh=False):
        return self.document.doc(fresh)

    def detect_manual_edits(self):
        return self.document.detect_manual_edits()

    # ── 원본 ──────────────────────────────────────────
    def add_sources(self, paths, role=None):
        with self.lock:
            r = self.sources.add(paths, role)
            for a in r["added"]:
                s = self.sources.info(a["sid"])
                self.compare.archive(s["sid"], s["path"], s["sha"])
            return r

    def remove_source(self, sid):
        with self.lock:
            self.sources.remove(sid)

    def set_role(self, sid, role):
        self.sources.set_role(sid, role)

    def check_sources(self):
        """원본이 바뀌었는지 확인 → 바뀐 것은 이전 판(보관본)과 칸 단위로 비교하고 영향받는 문서 칸을 붙인다."""
        with self.lock:
            refs = self._refs()
            r = self.sources.check(self.verifier.affected_by_source())
            for ch in r["changed"]:
                old = self.compare.archived(ch["sid"], ch["old_sha"])
                self.compare.archive(ch["sid"], ch["path"], ch["new_sha"])
                if old:
                    try:
                        d = self.compare.compare_paths(old, ch["path"])
                        ch["diff"] = d
                        ch["impact"] = self.compare.affected(d, refs.get(ch["sid"], {}))
                    except WorkError as e:
                        ch["diff_error"] = str(e)
            return r

    def _refs(self):
        try:
            return self.verifier.refs_index(self.document.doc()) if self.db.versions() else {}
        except WorkError:
            return {}

    # ── 재제출 비교(이름이 바뀐 새 파일) ─────────────
    def resubmit_check(self, path):
        """새로 받은 파일이 어느 원본의 새 판인지 찾고, 그 원본과 비교한 결과를 돌려준다(아직 바꾸지 않음)."""
        if not registry.supported(path):
            raise WorkError("지원하지 않는 형식입니다")
        cands = self.compare.match(path, self.db.sources(), self.sources.books)
        out = {"path": path, "name": os.path.basename(path), "candidates": cands}
        if cands:
            best = self.sources.info(cands[0]["sid"])
            d = self.compare.compare_paths(best["path"], path)
            out.update(sid=best["sid"], diff=d, impact=self.compare.affected(d, self._refs().get(best["sid"], {})))
        return out

    def resubmit_apply(self, sid, path):
        """비교를 확인한 뒤 원본을 새 파일로 바꾼다(이전 판은 원본보관에 남음) → 다시 검증하면 바뀐 칸이 빨강으로 보인다."""
        with self.lock:
            s = self.sources.info(sid)
            self.compare.archive(sid, s["path"], s["sha"])
            r = self.sources.replace(sid, path)
            self.compare.archive(sid, path, r["new_sha"])
            return r

    def grid(self, sid, sheet, r0=0, c0=0, nr=60, nc=26):
        return self.sources.grid(sid, sheet, r0, c0, nr, nc)

    # ── 검증 ──────────────────────────────────────────
    def verify(self):
        with self.lock:
            edits = self.document.detect_manual_edits()
            doc = self.document.doc()
            s = self.sources
            claims = self.ai.read_doc(doc, use_ai=self.use_ai and self.ai.enabled())
            self.verifier.run(doc, s.names(), s.paths(), s.roles(), self.clip.clips(),
                              self.db.confirms(), self.edit.pending(), edits, claims)
            return self.view()

    def ai_read(self, on=True):
        """AI 로 문장 읽기를 켜고(끄고) 다시 검증한다."""
        self.use_ai = bool(on)
        return self.verify()

    def ai_summary(self, use_ai=False):
        if not self.last:
            self.verify()
        L = self.last
        return self.ai.summarize(L["summary"], (L.get("claims") or {}).get("stat"), use_ai)

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
            if self.document.read_only():
                raise WorkError("읽기 전용 형식(한글 hwpx 가 아닌 문서)이라 고칠 수 없습니다. 원래 프로그램에서 고친 뒤 다시 검증하세요")
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
