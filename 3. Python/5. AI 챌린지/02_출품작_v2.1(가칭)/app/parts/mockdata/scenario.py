# -*- coding: utf-8 -*-
"""[가상자료 ⑪] 시나리오 조립: 무작위 가상 기관 하나의 요구자료 작성 상황 전체를 만든다.

만드는 것(폴더 구조)
  <시나리오>/공유폴더(가상)/<연도> 행정사무감사/
      00_공문함/      요구 공문·검사 의뢰·결과 알림·협조 요청(hwpx·odt)
      01_원본자료/    팀별 원본 엑셀(머리글·배치·단위가 문서와 다름)
      02_팀제출/      팀 답변서 hwpx
      03_취합/        취합본(오류 심음)·작성틀
      04_참고자료/    시험법 요약본·장비 점검 매뉴얼·작성 지침
  <시나리오>/나중에_받은_자료/   재제출본(같은 이름·바뀐 이름)
  <시나리오>/정답표.json         자동 채점용(대조 오류·재제출 변경·양식 판정)
  <시나리오>/시나리오_안내.md    사람이 읽는 요약
"""
import os
import json
import random
import shutil
import datetime

from app.parts.mockdata import vocab as V
from app.parts.mockdata import domains, sources, reports, errors, render, gongmun, guides, resubmit, formats_out

SIZES = {"작게": 5, "보통": 8, "크게": 12}
PRIORITY = ["perf", "river", "air", "budget"]          # 오류 종류(증감률·월평균·뒤집기·단위)가 고루 나오게 먼저 넣는 영역
DEFAULTS = {"seed": None, "size": "보통", "errors": 10, "kinds": list(errors.KINDS), "gongmun": True, "guides": True,
            "form": True, "resubmit": True, "fmt": "both", "year": 2026,
            "src_mix": False,          # 원본 형식 섞기(xlsx·ods·csv·pdf·docx)
            "stmt_free": False,        # 자유 문형 계산 문장 섞기(AI 읽기 시험용 — 정답표에 'AI필요' 표시)
            "target_fmt": "hwpx"}      # 취합본 형식: hwpx·docx·pdf·odt·md 또는 mix(무작위)
TARGET_FORMATS = ("hwpx", "docx", "pdf", "odt", "md")


def _date(y, m, d):
    return datetime.date(y, m, d)


def make_ctx(rng, year):
    org = V.org(rng)
    audit = _date(year, 11, rng.randint(16, 27))
    due = audit - datetime.timedelta(days=rng.randint(10, 16))
    return {"year": year, "org": org, "cities": V.cities(rng, 8), "rivers": V.rivers(rng, 6),
            "stations": V.stations(rng, 6), "teams": dict(V.TEAMS), "code": org["province"][:1] + rng.choice("ABCDEHK"),
            "audit_date": audit, "due_date": due, "team_due": due - datetime.timedelta(days=7),
            "coll_due": due - datetime.timedelta(days=3)}


class Scenario:
    def __init__(self, out_root, **opts):
        self.o = dict(DEFAULTS)
        self.o.update({k: v for k, v in opts.items() if v is not None})
        if self.o["seed"] in (None, "", 0):
            self.o["seed"] = random.randint(1000, 99999)
        self.o["seed"] = int(self.o["seed"])
        self.rng = random.Random(self.o["seed"])
        self.ctx = make_ctx(self.rng, int(self.o["year"]))
        self.ctx["stmt_free"] = bool(self.o.get("stmt_free"))
        self.name = f"{self.ctx['org']['province']}_{self.o['seed']}"
        self.out = os.path.join(os.path.abspath(out_root), self.name)
        y = self.ctx["year"]
        self.base = os.path.join(self.out, "공유폴더(가상)", f"{y} 행정사무감사")
        self.files = []

    def p(self, *parts):
        path = os.path.join(*parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def rel(self, path):
        return os.path.relpath(path, self.out).replace(os.sep, "/")

    # ── 단계 ──
    def choose_domains(self):
        n = SIZES.get(self.o["size"], 8)
        rest = [d for d, _ in domains.DOMAINS if d not in PRIORITY]
        self.rng.shuffle(rest)
        return (PRIORITY + rest)[:n] if n >= len(PRIORITY) else self.rng.sample(PRIORITY, n)

    def build_sources(self, tables):
        cellmap, numbers, built = {}, set(), {}
        for t in tables:
            variant = {"transpose": self.rng.random() < 0.3, "shuffle": self.rng.random() < 0.6,
                       "extra_cols": self.rng.choice([0, 0, 1, 2]), "extra_rows": self.rng.choice([0, 0, 1]),
                       "with_total": self.rng.random() < 0.85, "filler": self.rng.random() < 0.4}
            src = sources.build_source(t, self.rng, variant, self.ctx["year"])
            fmt = formats_out.choose(self.rng, t, self.o["src_mix"])
            path0 = self.p(self.base, "01_원본자료", self.ctx["teams"][t.team], t.src_file)
            path, conv = formats_out.write_source(path0, src["sheets"], fmt, t.src_sheet)
            self.files.append(path)
            built[t.key] = dict(src, path=path, variant=variant, fmt=fmt)
            numbers |= src["numbers"] | self._sheet_numbers(src["sheets"])
            fname = os.path.basename(path)
            for (r, c), ref in src["cellmap"].items():
                nref = conv(ref)
                cellmap[(t.key, r, c)] = f"{fname} {nref}" if nref else None
        return built, cellmap, numbers

    @staticmethod
    def _sheet_numbers(sheets):
        """시트에 들어간 모든 숫자(세부기록·코드표 포함)."""
        out = set()
        for sh in sheets:
            for row in sh["rows"]:
                for cell in row:
                    v = cell.get("v") if isinstance(cell, dict) else cell
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        out.add(round(float(v), 6))
        return out

    @staticmethod
    def _doc_numbers(blocks):
        from app.common import numbers as N
        out = set()
        for b in blocks:
            if b["kind"] == "table":
                for row in b["rows"]:
                    for cell in row:
                        tok = N.parse_cell(cell if isinstance(cell, str) else cell.get("t", ""))
                        if tok:
                            out.add(round(tok["value"], 6))
            elif "text" in b:
                for tk in N.extract_numbers(b["text"]):
                    out.add(round(tk["value"], 6))
        return out

    def pick_fake(self, used):
        for _ in range(500):
            x = self.rng.randint(23, 480)
            # 엔진이 쓰는 배율(그대로·÷1,000·÷1,000,000·×1,000·×100)로 환산해도 겹치지 않는 값
            if not any(abs(x - u * sc) < 0.6 for u in used for sc in (1, 0.001, 0.000001, 1000, 100)):
                return x
        return 997

    def run(self):
        if os.path.exists(self.out):
            shutil.rmtree(self.out)
        os.makedirs(self.out)
        rng, ctx, y = self.rng, self.ctx, self.ctx["year"]
        names = self.choose_domains()
        tables = domains.make_tables(rng, ctx, names)
        order = list(range(1, len(tables) + 1))
        rng.shuffle(order)
        nums = {t.key: n for t, n in zip(tables, order)}
        built, cellmap, numbers = self.build_sources(tables)
        for key, b in built.items():
            t = next(x for x in tables if x.key == key)
            if getattr(t, "force_transpose", False) or b["variant"]["transpose"] and t.allow_transpose:
                b["transposed"] = True

        teams = reports.team_docs(tables, nums, y, ctx["teams"])
        coll = reports.collected(tables, nums, ctx, rng)
        for blk in coll:
            if blk["kind"] == "table" and built[blk["t"].key].get("transposed"):
                blk["transposed"] = True
        used = numbers | self._doc_numbers(coll)
        fake = lambda extra: self.pick_fake(used | extra)      # 심은 오류 값과도 겹치지 않게(오류를 심은 뒤 고름)
        answers, done = errors.run(rng, coll, teams, cellmap, int(self.o["errors"]), self.o["kinds"], fake)
        coll = reports.finish_fake(coll, fake)

        for team, blocks in teams.items():
            tf = rng.choice(["hwpx", "hwpx", "docx", "pdf"]) if self.o["src_mix"] else "hwpx"
            self.files.append(render.WRITERS[tf](blocks, self.p(self.base, "02_팀제출", f"{ctx['teams'][team]}_요구자료_답변.{tf}"),
                                                 f"{ctx['teams'][team]} 요구자료 답변"))
        tfmt = self.o["target_fmt"]
        if tfmt == "mix":
            tfmt = rng.choice(TARGET_FORMATS)
        if tfmt not in TARGET_FORMATS:
            tfmt = "hwpx"
        self.target_fmt = tfmt
        target = render.WRITERS[tfmt](coll, self.p(self.base, "03_취합", f"{y}_행정사무감사_요구자료_취합본.{tfmt}"), "취합본")
        self.files.append(target)
        forms = []
        if self.o["form"]:
            pick = rng.sample(tables, min(3, len(tables)))
            fb, blanks = reports.form_blocks(pick, nums, y)
            fp = render.to_hwpx(fb, self.p(self.base, "03_취합", f"{y}_요구자료_작성틀.hwpx"), "작성틀")
            self.files.append(fp)
            forms.append({"파일": self.rel(fp), "판정": "작성제출", "빈칸": blanks})
        if self.o["gongmun"]:
            forms += self.build_gongmun(tables, nums)
        if self.o["guides"]:
            forms += self.build_guides()
        resub = self.build_resubmit(tables, built, nums) if self.o["resubmit"] else []

        key = {"설명": "무작위 시나리오 정답표. 표 번호는 취합본 안 순서(0부터). 기대 = 허용하는 판정 목록.",
               "대상": self.rel(target),
               "시나리오": {"이름": self.name, "씨앗값": self.o["seed"], "크기": self.o["size"], "기관": ctx["org"]["name"],
                         "자료영역": [domains.DOMAIN_TITLES[n] for n in names], "심은오류": done,
                         "대상형식": self.target_fmt,
                         "원본형식": {os.path.basename(b["path"]): b["fmt"] for b in built.values()}},
               "항목": answers, "재제출": resub, "양식": forms}
        with open(os.path.join(self.out, "정답표.json"), "w", encoding="utf-8") as f:
            json.dump(key, f, ensure_ascii=False, indent=1, default=str)
        self.write_guide(key)
        return self.summary(key)

    def build_gongmun(self, tables, nums):
        rng, ctx = self.rng, self.ctx
        fmt = self.o["fmt"]
        d = os.path.join(self.base, "00_공문함")
        out = []

        def put(blocks, name, kind):
            ps = render.save(blocks, self.p(d, name), fmt, name)
            self.files += ps
            out.extend({"파일": self.rel(p), "판정": kind} for p in ps)

        put(gongmun.request_letter(rng, ctx, tables, nums), f"{ctx['year']}년도 행정사무감사 요구자료 제출 요청", "공문(요청)")
        for i, city in enumerate(rng.sample(ctx["cities"], 2)):
            seq = rng.randint(2, 15)
            put(gongmun.test_request(rng, ctx, city, seq), f"폐수오염도 검사 의뢰({city}-{i + 1})", "공문(의뢰)")
            put(gongmun.result_notice(rng, ctx, city, seq), f"수질오염도 검사 결과 알림[{city}-{i + 1}]", "공문(결과 통보)")
        put(gongmun.coop_request(rng, ctx, rng.sample(ctx["rivers"], 3)), "생태하천복원사업 현장점검 협조 요청", "공문(협조 요청)")
        return out

    def build_guides(self):
        rng, ctx = self.rng, self.ctx
        d = os.path.join(self.base, "04_참고자료")
        out = []
        items = [(guides.method_summary(rng, m), f"{m} 시험법 요약본") for m in rng.sample(list(guides.METHODS), 2)]
        items.append((guides.equipment_manual(rng, rng.choice(list(guides.EQUIP))), "장비 일상 점검 매뉴얼"))
        items.append((guides.writing_guideline(rng, ctx), "요구자료 작성 지침"))
        for blocks, name in items:
            fmt = rng.choice(["hwpx", "odt"]) if self.o["fmt"] == "both" else self.o["fmt"]
            ps = render.save(blocks, self.p(d, name), fmt, name)
            self.files += ps
            out.extend({"파일": self.rel(p), "판정": "참고"} for p in ps)
        return out

    def build_resubmit(self, tables, built, nums):
        """원본 2개를 골라 고친 판을 만든다: 하나는 같은 이름, 하나는 '(수정)' 붙은 이름."""
        rng = self.rng
        coll_order = [t.key for t in sorted(tables, key=lambda x: nums[x.key])]   # 취합본 표 순서
        cand = [t for t in tables if built[t.key]["cellmap"]]
        rng.shuffle(cand)
        out = []
        for i, t in enumerate(cand[:2]):
            sheets, ans = resubmit.make(rng, built[t.key], t, coll_order)
            orig = os.path.basename(built[t.key]["path"])
            stem, ext = os.path.splitext(orig)
            name = orig if i == 0 else f"{stem}(수정){ext}"
            path, _ = formats_out.write_source(self.p(self.out, "나중에_받은_자료", os.path.splitext(name)[0] + ".xlsx"),
                                               sheets, built[t.key]["fmt"], t.src_sheet)
            self.files.append(path)
            ans.update({"원본": self.rel(built[t.key]["path"]), "수정본": self.rel(path), "같은이름": i == 0})
            out.append(ans)
        return out

    def write_guide(self, key):
        s = key["시나리오"]
        lines = [f"# 시나리오 안내 — {s['이름']}", "",
                 f"- 가상 기관: {s['기관']} (모든 이름·수치는 가상)", f"- 씨앗값: {s['씨앗값']} (같은 값이면 같은 자료가 다시 만들어짐)",
                 f"- 크기: {s['크기']} · 요구자료 {len(s['자료영역'])}개: {', '.join(s['자료영역'])}", "",
                 "## 심은 오류", "", "| 번호 | 종류 | 위치 | 문서 값 | 정답 | 설명 |", "|---|---|---|---|---|---|"]
        for a in key["항목"]:
            if a.get("정상") or a.get("연쇄"):
                continue
            where = f"표{a['표'] + 1} {a['행']} › {a['열']}" if "표" in a else (a.get("본문") or a.get("요일") or "")
            lines.append(f"| {a['id']} | {a['구분']} | {where} | {a.get('문서값', '')} | {a.get('정답', '')} | {a['설명']} |")
        lines += ["", f"정상 사례 {sum(1 for a in key['항목'] if a.get('정상'))}개, 연쇄 표시 {sum(1 for a in key['항목'] if a.get('연쇄'))}개",
                  "", "## 재제출본", ""]
        for r in key["재제출"]:
            lines.append(f"- {r['수정본']} ← {r['원본']} : 바뀐 칸 {len(r['변경'])}개, 취합본 영향 {len(r['영향'])}칸")
        lines += ["", "## 문서 판정(양식 분석용)", ""]
        for f in key["양식"]:
            lines.append(f"- {f['판정']}: {f['파일']}" + (f" (빈칸 {f['빈칸']}개)" if "빈칸" in f else ""))
        with open(os.path.join(self.out, "시나리오_안내.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def summary(self, key):
        n_err = sum(1 for a in key["항목"] if not a.get("정상") and not a.get("연쇄"))
        return {"name": self.name, "folder": self.out, "seed": self.o["seed"], "org": key["시나리오"]["기관"],
                "size": self.o["size"], "tables": len(key["시나리오"]["자료영역"]), "errors": n_err,
                "kinds": key["시나리오"]["심은오류"], "files": len(self.files), "target": key["대상"]}
