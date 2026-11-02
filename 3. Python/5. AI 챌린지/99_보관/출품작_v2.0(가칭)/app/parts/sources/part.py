# -*- coding: utf-8 -*-
"""[원본 파트] 원본 자료(엑셀·팀 제출 hwpx)를 등록하고, 읽고, 바뀌었는지 확인한다.

입구: add(경로들), remove(sid), set_role(sid, 역할), check(), cells(...), grid(...)
출구: books(sid → 읽은 내용), errors(sid → 오류 문구), rows()(화면 목록용)
알림: 원본을 새로 읽거나 뺄 때 on_load(sid, book) / on_unload(sid) 를 부른다
      (조립부가 검증 파트의 색인에 연결해 둔다).
"""
import os
import datetime

from app.common.errors import WorkError
from app.common.files import sha256, norm, is_inside, fmt_value
from app.formats.hwpx import HwpxDoc, table_grids
from app.formats.xlsx import read_xlsx, ref as a1ref

SUPPORTED = (".xlsx", ".hwpx", ".xlsm")
TEMP_PREFIX = ("~$", ".~", "._")


class SourcesPart:
    def __init__(self, ctx, on_load=None, on_unload=None):
        self.ctx = ctx
        self.db = ctx.db
        self.on_load = on_load or (lambda sid, book: None)
        self.on_unload = on_unload or (lambda sid: None)
        self.books = {}         # sid -> {"kind": "xlsx", "wb": Workbook} | {"kind": "hwpx", "grids": [...]}
        self.errors = {}        # sid -> 오류 문구

    # ── 조회 ──────────────────────────────────────────
    def all(self):
        return self.db.sources()

    def info(self, sid):
        for s in self.db.sources():
            if s["sid"] == sid:
                return s
        return None

    def names(self):
        return {s["sid"]: s["name"] for s in self.db.sources()}

    def paths(self):
        return {s["sid"]: s["path"] for s in self.db.sources()}

    def roles(self):
        return {s["sid"]: s["role"] for s in self.db.sources()}

    def rows(self):
        """화면 '원본 자료' 목록에 쓸 줄들."""
        out = []
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
            out.append(d)
        return out

    def base_folder(self):
        paths = [s["path"] for s in self.db.sources()]
        if not paths:
            return ""
        try:
            return os.path.commonpath(paths)
        except ValueError:
            return ""

    # ── 등록 ──────────────────────────────────────────
    def load_all(self):
        for s in self.db.sources():
            self._load(s)

    def guess_role(self, path):
        return "팀제출" if path.lower().endswith(".hwpx") else "원본"

    def skip_reason(self, path):
        b = os.path.basename(path)
        if b.startswith(TEMP_PREFIX):
            return "임시 파일"
        if is_inside(path, self.ctx.folder):
            return "작업 폴더 안의 파일"
        tp = self.db.meta("target_path")
        if tp and norm(tp) == norm(path):
            return "검증 대상 문서 자신"
        if not b.lower().endswith(SUPPORTED):
            return "지원하지 않는 형식"
        return None

    @staticmethod
    def _expand(paths):
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
        return files

    def add(self, paths, role=None):
        added, skipped, failed = [], [], []
        for f in self._expand(paths):
            why = self.skip_reason(f)
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
                self.db.add_source(sid, f, os.path.basename(f), role or self.guess_role(f), sha256(f),
                                   st.st_size, st.st_mtime)
                ok = self._load(self.info(sid))
                (added if ok else failed).append({"sid": sid, "path": f, "error": self.errors.get(sid)})
            except OSError as e:
                failed.append({"path": f, "error": str(e)})
        return {"added": added, "skipped": skipped, "failed": failed}

    def _load(self, s):
        sid = s["sid"]
        self.on_unload(sid)
        self.books.pop(sid, None)
        self.errors.pop(sid, None)
        try:
            if not os.path.exists(s["path"]):
                raise OSError("파일이 없습니다(이동·삭제됨)")
            if s["path"].lower().endswith((".xlsx", ".xlsm")):
                wb = read_xlsx(s["path"])
                book = {"kind": "xlsx", "wb": wb}
                if wb.warnings:
                    self.errors[sid] = "; ".join(wb.warnings)
            else:
                book = {"kind": "hwpx", "grids": table_grids(HwpxDoc(s["path"]))}
            self.books[sid] = book
            self.on_load(sid, book)
            return True
        except Exception as e:     # 한 파일 실패가 전체를 멈추지 않게
            self.errors[sid] = f"읽기 실패: {e}"
            self.db.source_status(sid, "fail")
            return False

    def remove(self, sid):
        self.db.deactivate_source(sid)
        self.on_unload(sid)
        self.books.pop(sid, None)

    def set_role(self, sid, role):
        self.db.x("UPDATE sources SET role=? WHERE sid=?", (role, sid))

    # ── 변경 확인 ─────────────────────────────────────
    def check(self, affected_by=None):
        """등록한 원본이 바뀌었는지(내용 고유값 비교) 확인한다. 바뀐 원본은 다시 읽는다.
        affected_by: sid → [영향받는 칸 이름] (검증 파트가 만든 것, 없으면 빈 목록)"""
        affected_by = affected_by or {}
        changed, missing = [], []
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
            self._load(self.info(s["sid"]))
            changed.append({"sid": s["sid"], "name": s["name"], "path": s["path"],
                            "affected": affected_by.get(s["sid"], [])})
        return {"changed": changed, "missing": missing}

    # ── 셀 읽기(입력하기용) ───────────────────────────
    def _book(self, sid):
        b = self.books.get(sid)
        if not b:
            raise WorkError(self.errors.get(sid) or "원본을 읽을 수 없습니다")
        return b

    def ref_text(self, sid, sheet, r, c):
        b = self._book(sid)
        return f"{sheet}!{a1ref(r, c)}" if b["kind"] == "xlsx" else f"{sheet} {r + 1}행 {c + 1}열"

    def cells(self, sid, sheet, r0, c0, r1, c1, dec=None, scale=1.0, comma=True):
        """고른 범위의 셀을 {(r,c): (넣을 글자, 숫자값)} 로 돌려준다."""
        b = self._book(sid)
        out = {}
        if b["kind"] == "xlsx":
            sh = b["wb"].sheet(sheet)
            if not sh:
                raise WorkError("시트를 찾을 수 없습니다")
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    cell = sh.get(r, c)
                    if cell is None:
                        out[(r, c)] = ("", None)
                    elif cell.kind == "n":
                        out[(r, c)] = (fmt_value(cell.v, dec, scale, comma) if (dec is not None or scale != 1.0) else
                                       (cell.text if comma else cell.text.replace(",", "")), cell.v)
                    else:
                        out[(r, c)] = (cell.text, None)
            return out
        g = [x for x in b["grids"] if x["name"] == sheet]
        if not g:
            raise WorkError("표를 찾을 수 없습니다")
        g = g[0]
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                v = g["cells"].get((r, c))
                t = g["texts"].get((r, c), "")
                out[(r, c)] = (fmt_value(v[0], dec, scale, comma) if v and (dec is not None or scale != 1.0) else t,
                               v[0] if v else None)
        return out

    def grid(self, sid, sheet, r0=0, c0=0, nr=60, nc=26):
        """입력하기 화면의 원본 격자."""
        b = self._book(sid)
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
