# -*- coding: utf-8 -*-
"""[수정·입력 파트] 문서 칸에 넣을 값을 '대기 목록'에 올리고, 출처를 확정하고, 저장 결과를 이력에 남긴다.

값은 바로 문서에 쓰지 않는다. 대기 목록에 모았다가 [저장]을 누르면 문서 파트가 새 버전을 만든다.

입구: set_pending(doc, 칸, 새 값, 방법, 원본정보, 위치, 이유), drop_pending(칸)
      input_values(doc, 시작 칸, 고른 셀들, …), confirm(doc, 칸, 원본정보, 위치), unconfirm(칸)
      after_save(버전, 반영된 변경들)
출구: 장부(db)의 pending·confirms·events 표
"""
from app.common.errors import WorkError

MAX_INPUT_CELLS = 400


class EditPart:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db

    def pending(self):
        return self.db.pending()

    def set_pending(self, doc, slot, new, method, src=None, ref=None, reason=""):
        it = doc.item(slot)
        if not it:
            raise WorkError("칸을 찾을 수 없습니다")
        if not it.editable:
            raise WorkError("이 숫자는 한글 문서 구조상 직접 고칠 수 없습니다(누름틀이 아닌 복잡한 글자 묶음). 한글에서 고쳐 주세요")
        if (new or "") == (it.raw or ""):
            self.db.drop_pending(slot)
            return {"ok": True, "same": True}
        self.db.set_pending(slot=slot, label=it.label, old=it.raw, new=new, method=method,
                            sid=src["sid"] if src else None,
                            source_path=src["path"] if src else None, source_ref=ref,
                            source_sha=src["sha"] if src else None, reason=reason)
        return {"ok": True}

    def drop_pending(self, slot=None):
        self.db.drop_pending(slot)
        return {"ok": True}

    @staticmethod
    def targets(doc, start, r0, c0, r1, c1):
        """고른 셀 범위를 문서 칸들에 같은 모양으로 짝짓는다 → [(칸, 셀행, 셀열)]."""
        if start.kind != "cell":
            return [(start, r0, c0)]
        pos = {(it.row, it.col): it for it in doc.items if it.kind == "cell" and it.table == start.table and it.k == 0}
        out = []
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                it = pos.get((start.row + r - r0, start.col + c - c0))
                if it:
                    out.append((it, r, c))
        return out

    def input_values(self, doc, start_slot, src, cells, ref_of, r0, c0, r1, c1, reason=""):
        """원본에서 고른 셀 값(cells)을 문서 칸들에 넣는다(대기 목록에 올림).
        값이 이미 같으면 바꾸지 않고 출처만 확정해 기록한다."""
        start = doc.item(start_slot)
        if not start:
            raise WorkError("넣을 칸을 먼저 고르세요")
        if (r1 - r0 + 1) * (c1 - c0 + 1) > MAX_INPUT_CELLS:
            raise WorkError(f"한 번에 {MAX_INPUT_CELLS}칸까지만 넣을 수 있습니다")
        n = same = 0
        skipped = []
        for it, r, c in self.targets(doc, start, r0, c0, r1, c1):
            text, _ = cells[(r, c)]
            if not it.editable:
                skipped.append(it.label)
                continue
            ref_txt = ref_of(r, c)
            res = self.set_pending(doc, it.key, text, "입력하기", src, ref_txt, reason=reason)
            if res.get("same"):
                self.confirm(doc, it.key, src, ref_txt)
                same += 1
            else:
                n += 1
        return {"ok": True, "count": n, "same": same, "skipped": skipped}

    def confirm(self, doc, slot, src, ref_text):
        it = doc.item(slot)
        if not it or not src:
            raise WorkError("칸 또는 원본을 찾을 수 없습니다")
        self.db.confirm(slot, it.raw, src["sid"], src["path"], ref_text, src["sha"], self.ctx.user)
        v = self.db.last_version()
        self.db.add_event(ver=v["ver"], slot=slot, label=it.label, old=it.raw, new=it.raw, method="출처 확정",
                          sid=src["sid"], source_path=src["path"], source_ref=ref_text, source_sha=src["sha"],
                          reason="담당자가 출처를 확인함", user=self.ctx.user)
        return {"ok": True}

    def unconfirm(self, slot):
        self.db.unconfirm(slot)
        return {"ok": True}

    def after_save(self, ver, done):
        """새 버전에 반영된 변경을 값 이력에 남기고, 원본에서 온 값은 출처를 확정한다."""
        for p in done:
            self.db.add_event(ver=ver, slot=p["slot"], label=p["label"], old=p["old"], new=p["new"],
                              method=p["method"], sid=p["sid"], source_path=p["source_path"],
                              source_ref=p["source_ref"], source_sha=p["source_sha"], reason=p["reason"],
                              user=self.ctx.user)
            if p["sid"]:
                self.db.confirm(p["slot"], p["new"], p["sid"], p["source_path"], p["source_ref"],
                                p["source_sha"], self.ctx.user)
        self.db.drop_pending()
