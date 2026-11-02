# -*- coding: utf-8 -*-
"""작업 하나(작업 폴더 하나)를 다루는 중심 모듈.

작업 폴더 구성
  <작업 폴더>/숫자지기작업.db   ← 이력 장부(값 이력·출처·원본 변경·검증 기록)
  <작업 폴더>/작업본/           ← 누름틀을 씌운 문서 버전(v001, v002 …). 원본 문서는 건드리지 않음
  <작업 폴더>/내보내기/         ← 출처대장(xlsx)·검증표시본(hwpx)·검증보고(html)
  <작업 폴더>/백업/             ← 이력 장부 하루 1회 자동 백업
"""
import os
import re
import json
import getpass
import hashlib
import datetime
import threading

from app import config
from app.core import numbers as N
from app.core.hwpx_io import HwpxDoc, HwpxError, table_grids
from app.core.xlsx_io import read_xlsx, ref as a1ref
from app.core.matcher import SourceIndex, Verifier
from app.core.ledger import Ledger, now


class WorkError(Exception):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _norm(p):
    return os.path.normcase(os.path.abspath(p))


def fmt_value(x, dec=None, scale=1.0, comma=True):
    if x is None:
        return ""
    v = x * scale
    if dec is None:
        return N.fmt_auto(v) if comma else N.fmt_auto(v).replace(",", "")
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(1).scaleb(-dec)
    d = Decimal(repr(v)).quantize(q, rounding=ROUND_HALF_UP)
    return f"{d:,.{dec}f}" if comma else f"{d:.{dec}f}"


class Workspace:
    def __init__(self, folder, user=None):
        self.folder = os.path.abspath(folder)
        os.makedirs(self.folder, exist_ok=True)
        for d in (config.DIR_WORKCOPY, config.DIR_EXPORT, config.DIR_BACKUP):
            os.makedirs(os.path.join(self.folder, d), exist_ok=True)
        self.db = Ledger(os.path.join(self.folder, config.DB_NAME))
        try:
            default_user = getpass.getuser()
        except Exception:
            default_user = "사용자"
        self.user = user or self.db.meta("user") or default_user
        self.lock = threading.RLock()
        self.index = SourceIndex()
        self.books = {}         # sid -> {"kind":..., "wb":Workbook | "grids":[...]}
        self.errors = {}        # sid -> 오류 문구
        self._doc = None
        self._doc_key = None
        self.last = None        # 마지막 검증 결과
        for s in self.db.sources():
            self._load_source(s)
        self.db.backup(os.path.join(self.folder, config.DIR_BACKUP))

    # ── 상태 ──────────────────────────────────────────
    def state(self):
        v = self.db.last_version()
        srcs = []
        for s in self.db.sources():
            d = dict(s)
            d["error"] = self.errors.get(s["sid"])
            d["exists"] = os.path.exists(s["path"])
            b = self.books.get(s["sid"])
            if b and b["kind"] == "xlsx":
                d["sheets"] = [sh.name for sh in b["wb"].sheets]
            elif b:
                d["sheets"] = [g["name"] for g in b["grids"]]
            else:
                d["sheets"] = []
            srcs.append(d)
        return {
            "folder": self.folder, "user": self.user,
            "target": self.db.meta("target_path"), "target_name": self.db.meta("target_name"),
            "version": v, "versions": self.db.versions(),
            "sources": srcs, "pending": self.db.pending(),
            "last_run": self.last["summary"] if self.last else None,
            "base_folder": self._base_folder(),
        }

    def _base_folder(self):
        paths = [s["path"] for s in self.db.sources()]
        if not paths:
            return ""
        try:
            return os.path.commonpath(paths)
        except ValueError:
            return ""

    def set_user(self, name):
        self.user = (name or "").strip() or self.user
        self.db.set_meta("user", self.user)

    # ── 대상 문서 ─────────────────────────────────────
    def set_target(self, path):
        with self.lock:
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
            out = os.path.join(self.folder, config.DIR_WORKCOPY, f"{stem}_v001.hwpx")
            doc.save(out)
            sh = sha256(out)
            self.db.set_meta("target_path", path)
            self.db.set_meta("target_name", os.path.basename(path))
            self.db.set_meta("target_sha", sha256(path))
            self.db.set_meta("stem", stem)
            self.db.add_version(1, out, sh, f"작업본 생성(누름틀 {n}개)", self.user)
            doc2 = HwpxDoc(out)
            for it in doc2.items:
                self.db.add_event(ver=1, slot=it.key, label=it.label, old=None, new=it.raw, method="작업본 생성",
                                  source_path=path, reason="원본 문서의 처음 값", user=self.user)
            self._doc, self._doc_key = doc2, (out, sh)
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
                                  method="한글에서 직접 수정", reason="작업본 파일이 프로그램 밖에서 바뀜", user=self.user)
                changed.append({"slot": it.key, "label": it.label, "old": last[it.key], "new": it.raw})
            elif it.key not in last:
                self.db.add_event(ver=v["ver"], slot=it.key, label=it.label, old=None, new=it.raw,
                                  method="한글에서 직접 수정", reason="새로 생긴 칸", user=self.user)
        self.db.update_version_sha(v["ver"], sh)
        return changed

    # ── 원본 ──────────────────────────────────────────
    def _guess_role(self, path):
        return "팀제출" if path.lower().endswith(".hwpx") else "원본"

    def _skip(self, path):
        b = os.path.basename(path)
        if b.startswith("~$") or b.startswith(".~") or b.startswith("._"):
            return "임시 파일"
        if _norm(path).startswith(_norm(self.folder) + os.sep):
            return "작업 폴더 안의 파일"
        tp = self.db.meta("target_path")
        if tp and _norm(tp) == _norm(path):
            return "검증 대상 문서 자신"
        if not b.lower().endswith((".xlsx", ".hwpx", ".xlsm")):
            return "지원하지 않는 형식"
        return None

    def add_sources(self, paths, role=None):
        with self.lock:
            files = []
            for p in paths:
                p = os.path.abspath(p)
                if os.path.isdir(p):
                    for dp, dns, fs in os.walk(p):
                        dns[:] = [d for d in dns if not d.startswith(".")]
                        for f in sorted(fs):
                            files.append(os.path.join(dp, f))
                elif os.path.isfile(p):
                    files.append(p)
            added, skipped, failed = [], [], []
            for f in files:
                why = self._skip(f)
                if why:
                    if why != "지원하지 않는 형식" or os.path.isfile(f) and len(paths) == 1:
                        skipped.append({"path": f, "why": why})
                    continue
                if self.db.source_by_path(f):
                    skipped.append({"path": f, "why": "이미 등록됨"})
                    continue
                try:
                    st = os.stat(f)
                    sid = self.db.next_sid()
                    self.db.add_source(sid, f, os.path.basename(f), role or self._guess_role(f), sha256(f),
                                       st.st_size, st.st_mtime)
                    src = [s for s in self.db.sources() if s["sid"] == sid][0]
                    ok = self._load_source(src)
                    (added if ok else failed).append({"sid": sid, "path": f, "error": self.errors.get(sid)})
                except OSError as e:
                    failed.append({"path": f, "error": str(e)})
            return {"added": added, "skipped": skipped, "failed": failed}

    def _load_source(self, s):
        sid = s["sid"]
        self.index.remove_source(sid)
        self.books.pop(sid, None)
        self.errors.pop(sid, None)
        try:
            if not os.path.exists(s["path"]):
                raise OSError("파일이 없습니다(이동·삭제됨)")
            if s["path"].lower().endswith((".xlsx", ".xlsm")):
                wb = read_xlsx(s["path"])
                self.index.add_workbook(sid, wb)
                self.books[sid] = {"kind": "xlsx", "wb": wb}
                if wb.warnings:
                    self.errors[sid] = "; ".join(wb.warnings)
            else:
                doc = HwpxDoc(s["path"])
                grids = table_grids(doc)
                self.index.add_grids(sid, grids)
                self.books[sid] = {"kind": "hwpx", "grids": grids}
            return True
        except Exception as e:     # 한 파일 실패가 전체를 멈추지 않게
            self.errors[sid] = f"읽기 실패: {e}"
            self.db.source_status(sid, "fail")
            return False

    def remove_source(self, sid):
        with self.lock:
            self.db.deactivate_source(sid)
            self.index.remove_source(sid)
            self.books.pop(sid, None)

    def set_role(self, sid, role):
        self.db.x("UPDATE sources SET role=? WHERE sid=?", (role, sid))

    def check_sources(self):
        """등록한 원본 파일이 바뀌었는지(내용 고유값 비교) 확인한다."""
        with self.lock:
            changed, missing = [], []
            affected_by = self._last_run_sources()
            for s in self.db.sources():
                if not os.path.exists(s["path"]):
                    self.db.source_status(s["sid"], "missing")
                    missing.append({"sid": s["sid"], "name": s["name"], "path": s["path"]})
                    continue
                st = os.stat(s["path"])
                if st.st_size == s["size"] and abs(st.st_mtime - (s["mtime"] or 0)) < 1e-6:
                    continue
                new = sha256(s["path"])
                if new == s["sha"]:
                    self.db.x("UPDATE sources SET mtime=?, size=? WHERE sid=?", (st.st_mtime, st.st_size, s["sid"]))
                    continue
                self.db.source_changed(s["sid"], s["sha"], new, st.st_size, st.st_mtime,
                                       f"수정 시각 {datetime.datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M}")
                s2 = [x for x in self.db.sources() if x["sid"] == s["sid"]][0]
                self._load_source(s2)
                aff = affected_by.get(s["sid"], [])
                changed.append({"sid": s["sid"], "name": s["name"], "path": s["path"], "affected": aff})
            return {"changed": changed, "missing": missing}

    def _last_run_sources(self):
        out = {}
        if not self.last:
            return out
        for k, r in self.last["items"].items():
            for o in r.get("opinions", []) + r.get("candidates", [])[:1]:
                lab = self.last["labels"].get(k, k)
                if lab not in out.setdefault(o["sid"], []):
                    out[o["sid"]].append(lab)
        return out

    # ── 검증 ──────────────────────────────────────────
    def verify(self):
        with self.lock:
            edits = self.detect_manual_edits()
            doc = self.doc()
            names = {s["sid"]: s["name"] for s in self.db.sources()}
            paths = {s["sid"]: s["path"] for s in self.db.sources()}
            roles = {s["sid"]: s["role"] for s in self.db.sources()}
            V = Verifier(self.index, names, roles)
            clips = self.db.clips()
            out = V.verify(doc, clips)
            confirms = self.db.confirms()
            pend = {p["slot"]: p for p in self.db.pending()}
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
                r["status_text"] = config.STATUS.get(r["status"], (r["status"], ""))[0]
            summary = {}
            for r in out["items"].values():
                summary[r["status"]] = summary.get(r["status"], 0) + 1
            summary["text_issues"] = len(out["text_issues"])
            summary["total"] = len(out["items"])
            summary["at"] = now()
            summary["manual_edits"] = len(edits)
            labels = {it.key: it.label for it in doc.items}
            changed = []
            if self.last:
                for k, r in out["items"].items():
                    b = self.last["items"].get(k)
                    if b and b["status"] != r["status"]:
                        changed.append({"key": k, "label": labels.get(k, k), "before": b["status"], "after": r["status"],
                                        "before_text": config.STATUS.get(b["status"], ("",))[0],
                                        "after_text": r["status_text"]})
            summary["changed"] = len(changed)
            v = self.db.last_version()
            items_rows = []
            for k, r in out["items"].items():
                srcs = [{"sid": o["sid"], "ref": o["ref"], "rel": o["relation"]} for o in r.get("opinions", [])] or \
                       [{"sid": o["sid"], "ref": o["ref"], "rel": o["relation"]} for o in r.get("candidates", [])[:3]]
                items_rows.append((k, labels.get(k, k), r.get("raw"), r["status"], r.get("fix"),
                                   json.dumps(srcs, ensure_ascii=False), (r.get("calc") or {}).get("msg")))
            self.db.add_run(v["ver"] if v else 0, v["sha"] if v else "", summary, items_rows)
            self.last = {"items": out["items"], "text_issues": out["text_issues"], "tables": out["tables"],
                         "summary": summary, "labels": labels, "edits": edits,
                         "changed": changed}
            return self.view()

    def view(self):
        doc = self.doc()
        res = self.last["items"] if self.last else {}
        pend = {p["slot"]: p for p in self.db.pending()}
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
        names = {s["sid"]: s["name"] for s in self.db.sources()}
        tables = {}
        if self.last:
            for ti, maps in self.last["tables"].items():
                tables[str(ti)] = [dict(m, name=names.get(m["sid"], m["sid"])) for m in maps]
        return {"blocks": doc.blocks, "items": items, "text_issues": self.last["text_issues"] if self.last else [],
                "summary": self.last["summary"] if self.last else None, "tables": tables,
                "edits": self.last.get("edits", []) if self.last else [],
                "changed": self.last.get("changed", []) if self.last else [],
                "version": self.db.last_version(), "status_names": config.STATUS}

    def slot_detail(self, key):
        doc = self.doc()
        it = doc.item(key)
        if not it:
            raise WorkError("칸을 찾을 수 없습니다")
        r = (self.last or {}).get("items", {}).get(key, {})
        prev = []
        for o in (r.get("opinions") or []) + (r.get("candidates") or [])[:6]:
            pv = self.index.preview(o["gid"], o["r"], o["c"])
            prev.append(dict(o, preview=pv))
        clips = r.get("clips", [])
        return {"item": it.public(), "result": {k: v for k, v in r.items() if k not in ("opinions", "candidates")},
                "sources": prev, "events": self.db.events(key), "clips": clips,
                "confirmed": self.db.confirms().get(key), "pending": next((p for p in self.db.pending() if p["slot"] == key), None)}

    # ── 수정·입력 ─────────────────────────────────────
    def _src_info(self, sid):
        for s in self.db.sources():
            if s["sid"] == sid:
                return s
        return None

    def set_pending(self, slot, new, method, sid=None, ref=None, reason=""):
        with self.lock:
            doc = self.doc()
            it = doc.item(slot)
            if not it:
                raise WorkError("칸을 찾을 수 없습니다")
            if not it.editable:
                raise WorkError("이 숫자는 한글 문서 구조상 직접 고칠 수 없습니다(누름틀이 아닌 복잡한 글자 묶음). 한글에서 고쳐 주세요")
            s = self._src_info(sid) if sid else None
            if (new or "") == (it.raw or ""):
                self.db.drop_pending(slot)
                return {"ok": True, "same": True}
            self.db.set_pending(slot=slot, label=it.label, old=it.raw, new=new, method=method, sid=sid,
                                source_path=s["path"] if s else None, source_ref=ref,
                                source_sha=s["sha"] if s else None, reason=reason)
            return {"ok": True}

    def drop_pending(self, slot=None):
        self.db.drop_pending(slot)
        return {"ok": True}

    def fix_from_source(self, slot, sid, ref_text, value_text, reason="원본 값으로 수정"):
        return self.set_pending(slot, value_text, "원본 값으로 수정", sid, ref_text, reason)

    def input_values(self, sid, sheet, r0, c0, r1, c1, start_slot, dec=None, scale=1.0, comma=True):
        """원본에서 고른 칸(들)을 문서 칸(들)에 넣는다(대기 목록에 올림). 여러 칸이면 같은 모양으로 채운다."""
        with self.lock:
            doc = self.doc()
            start = doc.item(start_slot)
            if not start:
                raise WorkError("넣을 칸을 먼저 고르세요")
            b = self.books.get(sid)
            if not b:
                raise WorkError("원본을 읽을 수 없습니다")
            r0, r1 = sorted((r0, r1))
            c0, c1 = sorted((c0, c1))
            if (r1 - r0 + 1) * (c1 - c0 + 1) > 400:
                raise WorkError("한 번에 400칸까지만 넣을 수 있습니다")
            grid = {}
            if b["kind"] == "xlsx":
                sh = b["wb"].sheet(sheet)
                if not sh:
                    raise WorkError("시트를 찾을 수 없습니다")
                for r in range(r0, r1 + 1):
                    for c in range(c0, c1 + 1):
                        cell = sh.get(r, c)
                        if cell is None:
                            grid[(r, c)] = ("", None)
                        elif cell.kind == "n":
                            grid[(r, c)] = (fmt_value(cell.v, dec, scale, comma) if (dec is not None or scale != 1.0) else
                                            (cell.text if comma else cell.text.replace(",", "")), cell.v)
                        else:
                            grid[(r, c)] = (cell.text, None)
            else:
                g = [x for x in b["grids"] if x["name"] == sheet]
                if not g:
                    raise WorkError("표를 찾을 수 없습니다")
                g = g[0]
                for r in range(r0, r1 + 1):
                    for c in range(c0, c1 + 1):
                        v = g["cells"].get((r, c))
                        t = g["texts"].get((r, c), "")
                        grid[(r, c)] = (fmt_value(v[0], dec, scale, comma) if v and (dec is not None or scale != 1.0) else t,
                                        v[0] if v else None)
            targets = []
            if start.kind == "cell":
                pos = {(it.row, it.col): it for it in doc.items if it.kind == "cell" and it.table == start.table and it.k == 0}
                for r in range(r0, r1 + 1):
                    for c in range(c0, c1 + 1):
                        it = pos.get((start.row + r - r0, start.col + c - c0))
                        if it:
                            targets.append((it, r, c))
            else:
                targets.append((start, r0, c0))
            n = same = 0
            skipped = []
            for it, r, c in targets:
                text, val = grid[(r, c)]
                if not it.editable:
                    skipped.append(it.label)
                    continue
                ref_txt = f"{sheet}!{a1ref(r, c)}" if b["kind"] == "xlsx" else f"{sheet} {r + 1}행 {c + 1}열"
                res = self.set_pending(it.key, text, "입력하기", sid, ref_txt,
                                       reason=(f"배율 {scale:g}" if scale != 1.0 else "") + (f" 소수 {dec}자리" if dec is not None else ""))
                if res.get("same"):
                    # 값은 이미 같음 → 값은 그대로 두고 출처만 확정해 기록
                    self.confirm(it.key, sid, ref_txt)
                    same += 1
                else:
                    n += 1
            return {"ok": True, "count": n, "same": same, "skipped": skipped}

    def confirm(self, slot, sid, ref_text):
        with self.lock:
            doc = self.doc()
            it = doc.item(slot)
            s = self._src_info(sid)
            if not it or not s:
                raise WorkError("칸 또는 원본을 찾을 수 없습니다")
            self.db.confirm(slot, it.raw, sid, s["path"], ref_text, s["sha"], self.user)
            v = self.db.last_version()
            self.db.add_event(ver=v["ver"], slot=slot, label=it.label, old=it.raw, new=it.raw, method="출처 확정",
                              sid=sid, source_path=s["path"], source_ref=ref_text, source_sha=s["sha"],
                              reason="담당자가 출처를 확인함", user=self.user)
            if self.last and slot in self.last["items"]:
                self.last["items"][slot]["status"] = "ok_user"
                self.last["items"][slot]["status_text"] = config.STATUS["ok_user"][0]
            return {"ok": True}

    def unconfirm(self, slot):
        self.db.unconfirm(slot)
        return {"ok": True}

    def save_version(self, note=""):
        with self.lock:
            pend = self.db.pending()
            if not pend:
                raise WorkError("저장할 변경이 없습니다")
            self.detect_manual_edits()
            doc = self.doc(fresh=True)
            v = self.db.last_version()
            ver = v["ver"] + 1
            done = []
            for p in pend:
                it = doc.item(p["slot"])
                if not it:
                    continue
                ok = doc.set_field(it.key, p["new"]) if it.field else doc.set_text_at(it, p["new"])
                if ok:
                    done.append(p)
            stem = self.db.meta("stem") or "문서"
            out = os.path.join(self.folder, config.DIR_WORKCOPY, f"{stem}_v{ver:03d}.hwpx")
            doc.save(out)
            # 저장한 파일을 다시 읽어 값이 제대로 들어갔는지 확인
            chk = HwpxDoc(out)
            bad = [p["slot"] for p in done if (chk.item(p["slot"]).raw if chk.item(p["slot"]) else None) != p["new"]]
            if bad:
                os.remove(out)
                raise WorkError(f"저장 확인 실패({len(bad)}칸). 작업본을 바꾸지 않았습니다: {', '.join(bad[:5])}")
            self.db.add_version(ver, out, sha256(out), note or f"{len(done)}칸 수정", self.user)
            for p in done:
                self.db.add_event(ver=ver, slot=p["slot"], label=p["label"], old=p["old"], new=p["new"],
                                  method=p["method"], sid=p["sid"], source_path=p["source_path"],
                                  source_ref=p["source_ref"], source_sha=p["source_sha"], reason=p["reason"],
                                  user=self.user)
                if p["sid"]:
                    self.db.confirm(p["slot"], p["new"], p["sid"], p["source_path"], p["source_ref"], p["source_sha"], self.user)
            self.db.drop_pending()
            self._doc = None
            self.db.backup(os.path.join(self.folder, config.DIR_BACKUP))
            return {"ok": True, "ver": ver, "path": out, "count": len(done)}

    # ── 원본 격자(입력하기 화면) ───────────────────────
    def grid(self, sid, sheet, r0=0, c0=0, nr=60, nc=26):
        b = self.books.get(sid)
        if not b:
            raise WorkError(self.errors.get(sid) or "원본을 읽을 수 없습니다")
        rows = []
        if b["kind"] == "xlsx":
            sh = b["wb"].sheet(sheet) or b["wb"].sheets[0]
            maxr, maxc = sh.maxr, sh.maxc
            for r in range(r0, min(r0 + nr, maxr + 1)):
                row = []
                for c in range(c0, min(c0 + nc, maxc + 1)):
                    cell = sh.get(r, c)
                    row.append({"t": cell.text if cell else "", "n": bool(cell and cell.kind == "n"),
                                "v": cell.v if cell and cell.kind == "n" else None})
                rows.append(row)
            cols = [a1ref(0, c)[:-1] for c in range(c0, min(c0 + nc, maxc + 1))]
            return {"sid": sid, "sheet": sh.name, "r0": r0, "c0": c0, "rows": rows, "cols": cols,
                    "maxr": maxr, "maxc": maxc, "kind": "xlsx"}
        g = [x for x in b["grids"] if x["name"] == sheet] or b["grids"][:1]
        if not g:
            raise WorkError("표가 없습니다")
        g = g[0]
        for r in range(0, g["nrow"]):
            row = []
            for c in range(0, g["ncol"]):
                v = g["cells"].get((r, c))
                row.append({"t": g["texts"].get((r, c), ""), "n": v is not None, "v": v[0] if v else None})
            rows.append(row)
        return {"sid": sid, "sheet": g["name"], "r0": 0, "c0": 0, "rows": rows,
                "cols": [str(c + 1) for c in range(g["ncol"])], "maxr": g["nrow"] - 1, "maxc": g["ncol"] - 1,
                "kind": "hwpx", "title": g.get("title", "")}

    # ── 이력 ──────────────────────────────────────────
    def history(self, slot=None):
        return {"events": self.db.events(slot), "versions": self.db.versions(),
                "source_events": self.db.source_events(), "runs": self.db.runs()[:30]}

    # ── 내보내기 ──────────────────────────────────────
    def export(self):
        from app.core import report
        with self.lock:
            if not self.last:
                self.verify()
            return report.export_all(self)

    # ── 클립보드 기록 ─────────────────────────────────
    def record_clip(self, clip):
        return self.db.add_clip(clip["path"], clip["sheet"], clip["r0"], clip["c0"], clip["nrows"], clip["ncols"],
                                {f"{r},{c}": t for (r, c), t in clip["cells"].items()})
