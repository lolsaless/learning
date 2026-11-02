# -*- coding: utf-8 -*-
"""[검증 파트] 문서의 모든 숫자를 원본과 대조하고, 합계·비율·요일을 다시 계산한다.

판정은 모두 규칙과 계산으로 한다(engine.py). 이 파일은 엔진을 부르고 결과를 화면용으로 정리한다.

입구: add_book(sid, 원본) / remove_book(sid)   ← 원본 파트가 읽을 때마다 조립부가 연결
      run(doc, 원본 정보, 클립보드 기록, 확정 목록, 대기 목록, 직접 수정 목록)
출구: last(마지막 결과), view(doc, …), slot_detail(…), affected_by_source()
"""
import json
import time

from app import config
from app.store.ledger import now
from app.parts.verify.engine import SourceIndex, Verifier

BAD = ("mismatch", "unit", "calc")
WARN = ("conflict", "unknown", "multi", "claim")


def effect(n_cells, n_claims, seconds):
    """효과 추정: 사람이 손으로 대조·재계산할 때 걸릴 시간(설정값 × 개수) vs 프로그램 시간. '추정'임을 함께 적는다."""
    manual = n_cells * config.EFFECT_SEC_PER_CELL + n_claims * config.EFFECT_SEC_PER_CLAIM
    return {"manual_min": round(manual / 60, 1), "tool_sec": round(seconds, 1),
            "saved_min": round(max(0.0, manual - seconds) / 60, 1),
            "basis": f"숫자 1개 대조 {config.EFFECT_SEC_PER_CELL}초 · 문장 계산 1건 {config.EFFECT_SEC_PER_CLAIM}초 가정(설정에서 변경)",
            "estimate": True}


def apply_claims(items, claims):
    """문장 검산 결과(AI 파트가 만듦 — 조립부가 넘겨 줌)를 칸 판정에 반영한다.
    검증 엔진이 이미 계산한 칸(증감률 문형)은 건드리지 않는다."""
    n = 0
    for c in claims or []:
        r = items.get(c.get("key"))
        if r is None or r.get("calc"):
            continue
        r["calc"] = {"ok": c["ok"], "msg": c["msg"], "expected": c["expected_text"], "by": c["by"], "check": c["check"],
                     "model": c.get("model", "")}
        r["candidates"] = []
        if c["ok"]:
            if r["status"] in ("unknown", "multi", "single") or r.pop("doc_ref", None):
                r["status"] = "ok_calc"
        else:
            r["status"] = c["status"]
            r["fix"] = c["expected_text"]
        r["status_text"] = status_text(r["status"])
        n += 1
    return n


def status_text(st):
    return config.STATUS.get(st, (st, ""))[0]


class VerifyPart:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.index = SourceIndex()
        self.last = None        # 마지막 검증 결과

    # ── 원본 색인 ─────────────────────────────────────
    def add_book(self, sid, book):
        if book["kind"] == "sheet":
            self.index.add_workbook(sid, book["wb"])
        else:
            self.index.add_grids(sid, book["grids"])

    def remove_book(self, sid):
        self.index.remove_source(sid)

    # ── 실행 ──────────────────────────────────────────
    def run(self, doc, names, paths, roles, clips, confirms, pending, edits, claims=None):
        t0 = time.time()
        V = Verifier(self.index, names, roles)
        out = V.verify(doc, clips)
        apply_claims(out["items"], (claims or {}).get("claims"))
        pend = {p["slot"]: p for p in pending}
        for k, r in out["items"].items():
            for o in r.get("opinions", []) + r.get("candidates", []):
                o["path"] = paths.get(o["sid"], "")
            c = confirms.get(k)
            if c and (c["value"] or "") == (r.get("raw") or ""):
                r["confirmed"] = c
                if r["status"] not in ("calc",) or (r.get("calc") or {}).get("ok", True):
                    r["status"] = "ok_user"
            if k in pend:
                r["pending"] = pend[k]
            r["status_text"] = status_text(r["status"])
        labels = {it.key: it.label for it in doc.items}
        summary = self._summary(out, edits)
        summary["effect"] = effect(summary["total"], ((claims or {}).get("stat") or {}).get("checked", 0),
                                   time.time() - t0 + ((claims or {}).get("stat") or {}).get("seconds", 0))
        changed = self._changes_since_last(out, labels)
        summary["changed"] = len(changed)
        self._record(out, labels, summary)
        self.last = {"items": out["items"], "text_issues": out["text_issues"], "tables": out["tables"],
                     "summary": summary, "labels": labels, "edits": edits, "changed": changed, "claims": claims}
        return self.last

    @staticmethod
    def _summary(out, edits):
        s = {}
        for r in out["items"].values():
            s[r["status"]] = s.get(r["status"], 0) + 1
        s["text_issues"] = len(out["text_issues"])
        s["total"] = len(out["items"])
        s["at"] = now()
        s["manual_edits"] = len(edits)
        return s

    def _changes_since_last(self, out, labels):
        changed = []
        if not self.last:
            return changed
        for k, r in out["items"].items():
            b = self.last["items"].get(k)
            if b and b["status"] != r["status"]:
                changed.append({"key": k, "label": labels.get(k, k), "before": b["status"], "after": r["status"],
                                "before_text": status_text(b["status"]), "after_text": r["status_text"]})
        return changed

    def _record(self, out, labels, summary):
        v = self.db.last_version()
        rows = []
        for k, r in out["items"].items():
            srcs = [{"sid": o["sid"], "ref": o["ref"], "rel": o["relation"]} for o in r.get("opinions", [])] or \
                   [{"sid": o["sid"], "ref": o["ref"], "rel": o["relation"]} for o in r.get("candidates", [])[:3]]
            rows.append((k, labels.get(k, k), r.get("raw"), r["status"], r.get("fix"),
                         json.dumps(srcs, ensure_ascii=False), (r.get("calc") or {}).get("msg")))
        self.db.add_run(v["ver"] if v else 0, v["sha"] if v else "", summary, rows)

    def mark_confirmed(self, slot):
        if self.last and slot in self.last["items"]:
            self.last["items"][slot]["status"] = "ok_user"
            self.last["items"][slot]["status_text"] = status_text("ok_user")

    def affected_by_source(self):
        """원본 sid → 그 원본을 출처로 쓴 칸 이름들(원본 변경 확인 때 '영향받는 칸' 안내용)."""
        out = {}
        if not self.last:
            return out
        for k, r in self.last["items"].items():
            for o in r.get("opinions", []) + r.get("candidates", [])[:1]:
                lab = self.last["labels"].get(k, k)
                if lab not in out.setdefault(o["sid"], []):
                    out[o["sid"]].append(lab)
        return out

    def refs_index(self, doc):
        """원본 sid → {원본 칸 주소: [그 칸을 출처로 쓰는 문서 칸]} (재제출 비교의 '영향받는 칸')."""
        out = {}
        if not self.last:
            return out
        for k, r in self.last["items"].items():
            it = doc.item(k)
            if not it:
                continue
            ops = r.get("opinions") or (r.get("candidates") or [])[:1]
            for o in ops:
                out.setdefault(o["sid"], {}).setdefault(o["ref"], []).append(
                    {"key": k, "label": it.label, "raw": it.raw, "scale": o.get("scale", 1.0), "dec": it.dec,
                     "comma": it.comma})
        return out

    # ── 화면용 정리 ───────────────────────────────────
    def view(self, doc, pending, names):
        res = self.last["items"] if self.last else {}
        pend = {p["slot"]: p for p in pending}
        items = {}
        for it in doc.items:
            d = it.public()
            r = res.get(it.key)
            if r:
                d["status"] = r["status"]
                d["status_text"] = r.get("status_text")
                d["fix"] = r.get("fix")
            if it.key in pend:
                d["pending"] = pend[it.key]["new"]
            items[it.key] = d
        tables = {}
        if self.last:
            for ti, maps in self.last["tables"].items():
                tables[str(ti)] = [dict(m, name=names.get(m["sid"], m["sid"])) for m in maps]
        L = self.last or {}
        return {"blocks": doc.blocks, "items": items, "text_issues": L.get("text_issues", []),
                "summary": L.get("summary"), "tables": tables,
                "edits": L.get("edits", []), "changed": L.get("changed", []), "claims": L.get("claims"),
                "version": self.db.last_version(), "status_names": config.STATUS}

    def slot_detail(self, it):
        r = (self.last or {}).get("items", {}).get(it.key, {})
        prev = []
        for o in (r.get("opinions") or []) + (r.get("candidates") or [])[:6]:
            prev.append(dict(o, preview=self.index.preview(o["gid"], o["r"], o["c"])))
        return {"result": {k: v for k, v in r.items() if k not in ("opinions", "candidates")},
                "sources": prev, "clips": r.get("clips", [])}
