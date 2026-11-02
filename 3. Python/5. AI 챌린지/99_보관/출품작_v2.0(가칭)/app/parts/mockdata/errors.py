# -*- coding: utf-8 -*-
"""[가상자료 ⑤] 오류 심기와 정답표 항목 만들기.

문서 모형(blocks)의 표 글자를 직접 바꾸고, 바꾼 내용을 정답표 항목으로 돌려준다.
오류 하나가 합계·비율을 함께 어긋나게 하면 그 칸도 '연쇄' 항목으로 적는다(어느 상태든 허용).

오류 종류(KINDS)                       기대 판정
  swap     숫자 자리 바뀜(2.3→3.2)      mismatch
  typo     한 자리 오타(1,234→1,244)    mismatch
  total    합계 행 오류                 calc · mismatch
  unit     원 단위 값을 천원 표에        unit
  ratio    비율(%) 잘못 적음            mismatch · calc
  claim    증감률 문장 오류             calc
  weekday  날짜 요일 오류               weekday
  conflict 팀 제출본이 틀리고 취합본이 따라 적음 → 원본끼리 다름   conflict
  unknown  어느 원본에도 없는 숫자      unknown
"""
import datetime

from app.parts.mockdata.model import rhalf

KINDS = ["swap", "typo", "total", "unit", "ratio", "claim", "weekday", "conflict", "unknown"]
KIND_NAMES = {"swap": "자리 바뀜", "typo": "옮겨 적기 오타", "total": "합계 오류", "unit": "단위 혼동", "ratio": "비율 오류",
              "claim": "증감률 오류", "weekday": "요일 오류", "conflict": "출처 간 충돌", "unknown": "출처 없는 숫자"}
EXPECT = {"swap": ["mismatch"], "typo": ["mismatch"], "total": ["calc", "mismatch"], "unit": ["unit"],
          "ratio": ["mismatch", "calc"], "claim": ["calc"], "weekday": ["weekday"], "conflict": ["conflict"],
          "unknown": ["unknown"]}
CHAIN_OK = ["calc", "ok", "single", "ok_calc"]
NORMAL_OK = ["ok", "ok_calc", "single"]
WD = "월화수목금토일"


def _digits(text):
    return [i for i, ch in enumerate(text) if ch.isdigit()]


def swap_digits(rng, text):
    ds = _digits(text)
    pairs = [(a, b) for a, b in zip(ds, ds[1:]) if text[a] != text[b] and (a > 0 or text[b] != "0")]
    if not pairs:
        return None
    a, b = rng.choice(pairs)
    s = list(text)
    s[a], s[b] = s[b], s[a]
    out = "".join(s)
    return out if out.lstrip("0") and out != text else None


def typo_digit(rng, text):
    ds = _digits(text)[1:] or _digits(text)
    if not ds:
        return None
    i = rng.choice(ds)
    d = int(text[i])
    nd = (d + rng.choice([1, 2, -1, 3])) % 10
    out = text[:i] + str(nd) + text[i + 1:]
    return out if out != text else None


def weekday_text(d, wrong=False):
    w = WD[d.weekday()]
    if wrong:
        w = WD[(d.weekday() + 1) % 7]
    return f"{d.year}. {d.month}. {d.day}.({w})"


class Injector:
    """blocks: 취합본 문서 모형, teams: {팀: 팀 문서 모형}, cellmap: {(표키, 행, 열): 출처}"""

    def __init__(self, rng, coll, teams, cellmap):
        self.rng = rng
        self.coll = coll
        self.teams = teams
        self.cellmap = cellmap
        self.answers = []
        self.used = set()          # 오류를 심은 표 키
        self.err_cells = {}        # 표 키 → [(행, 열)] 오류를 심은 칸
        self.n = 0

    # ── 도우미 ──
    def tables(self):
        return [b for b in self.coll if b["kind"] == "table"]

    def ti_of(self, blk):
        return self.tables().index(blk)

    @staticmethod
    def pos(blk, r, c):
        t = blk["t"]
        return 1 + t.rows.index(r), 1 + t.cols.index(c)

    def get(self, blk, r, c):
        i, j = self.pos(blk, r, c)
        return blk["rows"][i][j]

    def put(self, blk, r, c, text):
        i, j = self.pos(blk, r, c)
        blk["rows"][i][j] = text

    def _id(self, kind):
        self.n += 1
        return f"R{self.n:02d}-{kind}"

    def add(self, kind, blk, r, c, new, old, desc, expect=None, extra=None):
        t = blk["t"]
        self.err_cells.setdefault(t.key, []).append((r, c))
        a = {"id": self._id(kind), "구분": KIND_NAMES[kind], "종류": kind, "표": self.ti_of(blk), "행": r, "열": c,
             "문서값": new, "정답": old, "기대": expect or EXPECT[kind], "설명": desc,
             "출처": self.cellmap.get((t.key, r, c))}
        if extra:
            a.update(extra)
        self.answers.append(a)
        self._chain(kind, blk, r, c, a["id"])
        return a

    def _chain(self, kind, blk, r, c, src_id):
        t = blk["t"]
        rc = t.ratio[0] if t.ratio else None
        out = []
        if t.total and r != t.TOTAL and c != rc:
            out.append((t.TOTAL, c))
        if t.ratio and c in (t.ratio[1], t.ratio[2]):
            out.append((r, rc))
        for rr, cc in out:
            self.answers.append({"id": f"{src_id}-연쇄", "구분": "연쇄 표시", "종류": "chain", "표": self.ti_of(blk),
                                 "행": rr, "열": cc, "기대": CHAIN_OK, "연쇄": True,
                                 "설명": f"{src_id} 때문에 다시 계산한 값이 맞지 않을 수 있음(어느 표시든 허용)"})

    def pick_table(self, cond=lambda t: True):
        cands = [b for b in self.tables() if b["t"].key not in self.used and cond(b["t"])]
        if not cands:
            return None
        b = self.rng.choice(cands)
        self.used.add(b["t"].key)
        return b

    def body_cell(self, t, cond=lambda r, c: True):
        rc = t.ratio[0] if t.ratio else None
        cells = [(r, c) for r in t.body_rows() for c in t.cols if c != rc and cond(r, c)]
        return self.rng.choice(cells) if cells else (None, None)

    # ── 오류 종류별 ──
    def e_swap(self):
        b = self.pick_table(lambda t: True)
        if not b:
            return False
        t = b["t"]
        for _ in range(20):
            r, c = self.body_cell(t, lambda r, c: len(set(ch for ch in t.cell_text(r, c) if ch.isdigit())) >= 2)
            if r is None:
                break
            old = self.get(b, r, c)
            new = swap_digits(self.rng, old)
            if new:
                self.put(b, r, c, new)
                self.add("swap", b, r, c, new, old, f"{old}을(를) {new}(으)로 자리를 바꿔 적음")
                return True
        self.used.discard(t.key)
        return False

    def e_typo(self):
        b = self.pick_table()
        if not b:
            return False
        t = b["t"]
        r, c = self.body_cell(t)
        old = self.get(b, r, c)
        new = typo_digit(self.rng, old)
        if not new:
            self.used.discard(t.key)
            return False
        self.put(b, r, c, new)
        self.add("typo", b, r, c, new, old, f"{old}을(를) {new}(으)로 잘못 적음")
        return True

    def e_total(self):
        b = self.pick_table(lambda t: t.total)
        if not b:
            return False
        t = b["t"]
        rc = t.ratio[0] if t.ratio else None
        c = self.rng.choice([x for x in t.cols if x != rc])
        d = t.dec(t.TOTAL, c)
        v = t.displayed(t.TOTAL, c)
        delta = max(10 ** -d * self.rng.randint(2, 9), rhalf(abs(v) * self.rng.uniform(0.01, 0.04), d))
        nv = v + self.rng.choice([1, -1]) * delta
        old = self.get(b, t.TOTAL, c)
        new = f"{rhalf(nv, d):,.{d}f}"
        self.put(b, t.TOTAL, c, new)
        self.add("total", b, t.TOTAL, c, new, old, f"합계를 {old} 대신 {new}(으)로 적음(각 행의 합과 다름)")
        if t.ratio and c in (t.ratio[1], t.ratio[2]):
            self.answers.append({"id": f"{self.answers[-1]['id']}-연쇄", "구분": "연쇄 표시", "종류": "chain",
                                 "표": self.ti_of(b), "행": t.TOTAL, "열": rc, "기대": CHAIN_OK, "연쇄": True,
                                 "설명": "합계 오류 때문에 합계 행 비율이 맞지 않을 수 있음"})
        return True

    def e_unit(self):
        b = self.pick_table(lambda t: bool(t.src_scale))
        if not b:
            return False
        t = b["t"]
        c = self.rng.choice(list(t.src_scale))
        r, _ = self.body_cell(t, lambda r, cc: cc == c)
        old = self.get(b, r, c)
        new = f"{int(round(t.values[(r, c)] * t.src_scale[c])):,}"
        self.put(b, r, c, new)
        self.add("unit", b, r, c, new, old, f"천원 단위 표에 원 단위 값({new})을 그대로 붙여 넣음")
        return True

    def e_ratio(self):
        b = self.pick_table(lambda t: bool(t.ratio))
        if not b:
            return False
        t = b["t"]
        rc = t.ratio[0]
        r = self.rng.choice(t.body_rows())
        d = t.dec(r, rc)
        v = t.displayed(r, rc)
        nv = max(0.1, v + self.rng.choice([1, -1]) * self.rng.uniform(1.5, 4.0))
        old = self.get(b, r, rc)
        new = f"{rhalf(nv, d):,.{d}f}"
        self.put(b, r, rc, new)
        self.add("ratio", b, r, rc, new, old, f"비율을 {old} 대신 {new}(으)로 적음")
        return True

    def e_conflict(self):
        b = self.pick_table(lambda t: t.team in self.teams)
        if not b:
            return False
        t = b["t"]
        r, c = self.body_cell(t, lambda r, c: len(set(ch for ch in t.cell_text(r, c) if ch.isdigit())) >= 2)
        if r is None:
            self.used.discard(t.key)
            return False
        old = self.get(b, r, c)
        new = swap_digits(self.rng, old) or typo_digit(self.rng, old)
        tb = next(x for x in self.teams[t.team] if x["kind"] == "table" and x["t"].key == t.key)
        self.put(tb, r, c, new)          # 팀 제출본이 먼저 틀림
        self.put(b, r, c, new)           # 취합본은 팀 제출본을 그대로 옮김
        self.add("conflict", b, r, c, new, old, f"{t.team} 제출본이 {new}(으)로 잘못 적었고 취합본이 그대로 옮김 → 원본 엑셀({old})과 충돌",
                 extra={"팀": t.team})
        return True

    def e_claim(self):
        cands = [x for x in self.coll if x["kind"] == "p" and x.get("claim") and not x.get("err")]
        if not cands:
            return False
        p = self.rng.choice(cands)
        cl = p["claim"]
        new = f"{rhalf(cl['pct'] + self.rng.choice([1, -1]) * self.rng.uniform(1.2, 5.0), 1):.1f}"
        if new == cl["pct_text"] or float(new) <= 0:
            return False
        p["text"] = p["text"].replace(f"대비 {cl['pct_text']}%", f"대비 {new}%")
        p["err"] = True
        self.answers.append({"id": self._id("claim"), "구분": KIND_NAMES["claim"], "종류": "claim", "본문": cl["what"],
                             "문서값": new, "정답": cl["pct_text"], "기대": EXPECT["claim"],
                             "설명": f"({cl['a']:,}−{cl['b']:,})÷{cl['b']:,}×100 = {cl['pct_text']}%인데 {new}%로 적음"})
        return True

    def e_weekday(self):
        p = next((x for x in self.coll if x["kind"] == "p" and x.get("date") and not x.get("err")), None)
        if not p:
            return False
        d = p["date"]
        right, wrong = weekday_text(d), weekday_text(d, wrong=True)
        p["text"] = p["text"].replace(right, wrong)
        p["err"] = True
        self.answers.append({"id": self._id("weekday"), "구분": KIND_NAMES["weekday"], "종류": "weekday",
                             "요일": wrong.split(". ", 1)[1], "기대": EXPECT["weekday"],
                             "설명": f"{d.year}. {d.month}. {d.day}.은 {WD[d.weekday()]}요일"})
        return True

    def e_unknown(self, fake):
        p = next((x for x in self.coll if x["kind"] == "p" and x.get("fake_slot")), None)
        if not p:
            return False
        p["text"] = p["text"].replace("{FAKE}", str(fake))
        p["fake_slot"] = False
        self.answers.append({"id": self._id("unknown"), "구분": KIND_NAMES["unknown"], "종류": "unknown",
                             "본문": p["fake_word"], "문서값": str(fake), "기대": EXPECT["unknown"],
                             "설명": "어느 원본에도 없는 숫자(지어낸 값)"})
        return True

    # ── 정상 사례 ──
    def normals(self, per_table=2):
        """표마다 정상 칸을 고른다. 오류 칸과 같은 행·열, 합계 행, 비율 열은 피한다(연쇄 영향 없음)."""
        out = []
        for b in self.tables():
            t = b["t"]
            bad = self.err_cells.get(t.key, [])
            rc = t.ratio[0] if t.ratio else None
            cells = [(r, c) for r in t.body_rows() for c in t.cols
                     if c != rc and all(r != er and c != ec for er, ec in bad)
                     and not (t.ratio and bad and c in (t.ratio[1], t.ratio[2]) and any(r == er for er, _ in bad))]
            self.rng.shuffle(cells)
            for r, c in cells[:per_table]:
                why = []
                if getattr(t, "force_transpose", False) or b.get("transposed"):
                    why.append("행·열 뒤바뀜")
                if c in t.src_scale:
                    why.append("원→천원 환산")
                if t.src_cols.get(c, c) != c:
                    why.append("머리글 다름")
                if t.monthly:
                    why.append("월별 평균·반올림")
                out.append({"id": f"N{len(out) + 1:02d}", "구분": "정상(" + (", ".join(why) or "그대로") + ")",
                            "종류": "normal", "표": self.ti_of(b), "행": r, "열": c, "문서값": self.get(b, r, c),
                            "기대": NORMAL_OK, "정상": True, "출처": self.cellmap.get((t.key, r, c)),
                            "설명": "정상 값 — 빨강·노랑이 나오면 오탐"})
        for x in self.coll:
            if x["kind"] == "p" and x.get("claim") and not x.get("err"):
                cl = x["claim"]
                out.append({"id": f"N{len(out) + 1:02d}", "구분": "정상(증감률 문장)", "종류": "normal", "본문": cl["what"],
                            "문서값": cl["pct_text"], "기대": ["ok_calc", "ok", "single"], "정상": True,
                            "설명": "증감률이 맞는 문장"})
        self.answers.extend(out)


def plan(rng, n, kinds):
    """오류 n개를 종류가 고르게 섞이도록 고른다."""
    order = []
    pool = list(kinds)
    while len(order) < n and pool:
        rng.shuffle(pool)
        order.extend(pool)
    return order[:n]


def run(rng, coll, teams, cellmap, n_err, kinds, fake):
    inj = Injector(rng, coll, teams, cellmap)
    done = []
    for kind in plan(rng, n_err * 2, kinds):
        if len(done) >= n_err:
            break
        ok = inj.e_unknown(fake) if kind == "unknown" else getattr(inj, f"e_{kind}")()
        if ok:
            done.append(kind)
    inj.normals()
    return inj.answers, done


def date_after(year, rng, month=None):
    m = month or rng.randint(10, 12)
    return datetime.date(year, m, rng.randint(2, 27))
