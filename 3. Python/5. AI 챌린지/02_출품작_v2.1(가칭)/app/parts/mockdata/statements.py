# -*- coding: utf-8 -*-
"""[가상자료 ⑬] 본문 '계산 문장' 만들기: 차이·비중·배수·합계를 표 값으로 적은 문장.

  규칙 문형(rule) : 프로그램 규칙 읽기로 검산할 수 있는 정해진 문형 → 틀리면 빨강(calc) 기대
  자유 문형(free) : 사람이 쓰는 듯한 자유로운 문형 → AI 읽기가 있어야 검산 가능(정답표에 'AI필요' 표시)
make(t, rng, free) → 문단 블록(stmt 정보 포함) 또는 None.  render(stmt) → 문장 글자.
"""
import re

from app.parts.mockdata.model import rhalf

NAMES = {"diff": "차이", "share": "비중", "times": "배수", "sum": "합계"}
UNIT_IN_PAREN = re.compile(r"\((천원|백만원|건|명|곳|개소|회|일|대)\)")
UNIT_WORDS = [("건수", "건"), ("접수", "건"), ("처리", "건"), ("완료", "건"), ("검사", "건"), ("민원", "건"),
              ("현원", "명"), ("정원", "명"), ("인원", "명"), ("일수", "일"), ("지점", "곳")]

RULE = {
    "diff": "{pre}{ra}은 {a}{u}으로 {rb}({b}{u})보다 {c}{u} {way}",
    "share": "{pre}전체 {whole}{u} 중 {ra}이 {part}{u}({c}%)를 차지함",
    "times": "{pre}{ra}({a}{u})은 {rb}({b}{u})의 {c}배 수준임",
    "sum": "{pre}{list_plain}을 합하여 총 {total}{u}임",
}
FREE = {
    "diff": "{pre}{ra}은 {a}{u}을 기록해 {b}{u}에 그친 {rb}을 {c}{u} 앞섰음",
    "share": "{pre}{whole}{u}에 이르는 전체 가운데 {c}%에 해당하는 {part}{u}가 {ra}에서 나왔음",
    "times": "{pre}{rb}이 {b}{u}이었던 데 비해 {ra}은 {a}{u}으로 {c}배가량 많았음",
    "sum": "{pre}{total}{u}은 {list_paren}을 모두 더한 값임",
}


def unit_of(t, col):
    m = UNIT_IN_PAREN.search(col)
    if m:
        return m.group(1)
    m = re.search(r"단위\s*:\s*(천원|백만원|건|명|곳|개소|회|일|대)\s*[,)]", t.unit or "")
    if m:
        return m.group(1)
    for w, u in UNIT_WORDS:
        if w in col:
            return u
    return None


def _ok_name(s):
    return s and not re.search(r"\d", re.sub(r"\d{4}년", "", s)) and "(" not in s


def _fmt(v, d=0):
    return f"{rhalf(v, d):,.{d}f}"


def _has_final(w):
    ch = w[-1] if w else ""
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    return ch in "013678"            # 숫자 끝: 일·삼·육·칠·팔·영(공)은 받침 있음


def fix_josa(text, names):
    """'미리군은/이/을' 처럼 낱말 받침에 맞춰 조사를 고친다(은/는, 이/가, 을/를, 으로/로)."""
    pairs = {"은": "는", "이": "가", "을": "를"}
    for w in sorted(set(n for n in names if n), key=len, reverse=True):
        fin = _has_final(w)
        for a, b in pairs.items():
            text = re.sub(re.escape(w) + "(" + a + "|" + b + ")(?=[\\s(])", w + (a if fin else b), text)
    text = re.sub(r"([가-힣\d])으로", lambda m: m.group(1) + ("으로" if _has_final(m.group(1)) and m.group(1) != "일" else "로"), text)
    return text


def _render(st, ctext):
    v = dict(st["vals"])
    v["c"] = ctext
    v["total"] = ctext
    tpl = (FREE if st["free"] else RULE)[st["type"]]
    return fix_josa(tpl.format(**v), [v.get("ra"), v.get("rb"), v.get("u")])


def render(st):
    return _render(st, st["c_text"])


def c_pos(st):
    """결과 숫자가 문장의 몇 번째 글자에서 시작하는지(같은 숫자가 둘 있어도 정확히 가리키게)."""
    return _render(st, "\x00").index("\x00")


def make(t, rng, free=False):
    if rng.random() < 0.35:
        return None
    rc = t.ratio[0] if t.ratio else None
    cols = [c for c in t.cols if c != rc and t.decs.get(c, 0) == 0 and unit_of(t, c)]
    rows = [r for r in t.body_rows() if _ok_name(r)]
    if not cols or len(rows) < 2:
        return None
    col = rng.choice(cols)
    u = unit_of(t, col)
    pre_name = re.sub(r"\(.*?\)", "", col).strip()
    pre = f"{pre_name} 기준으로 " if _ok_name(pre_name) else ""
    val = {r: rhalf(t.values[(r, col)], 0) for r in rows}
    kinds = ["diff", "times", "sum"] + (["share"] if t.total else [])
    typ = rng.choice(kinds)
    ra, rb = rng.sample(rows, 2)
    if val[ra] < val[rb]:
        ra, rb = rb, ra
    a, b = val[ra], val[rb]
    vals = {"pre": pre, "u": u, "ra": ra, "rb": rb, "a": _fmt(a), "b": _fmt(b)}
    if typ == "diff":
        if a == b:
            return None
        c, d = a - b, 0
        vals["way"] = "많음"
    elif typ == "times":
        if b <= 0 or not 1.3 <= a / b <= 30:
            return None
        c, d = a / b, 1
    elif typ == "share":
        whole = rhalf(t.values[(t.TOTAL, col)], 0)
        top = max(rows, key=lambda r: val[r])
        if whole <= 0:
            return None
        vals.update(ra=top, part=_fmt(val[top]), whole=_fmt(whole))
        c, d = val[top] / whole * 100, 1
    else:
        parts = rows[:min(len(rows), rng.choice([2, 3, 3, 4]))]
        if len(parts) < 2:
            return None
        c, d = sum(val[r] for r in parts), 0
        vals["list_plain"] = ", ".join(f"{r} {_fmt(val[r])}{u}" for r in parts)
        vals["list_paren"] = "·".join(f"{r}({_fmt(val[r])}{u})" for r in parts)
    st = {"type": typ, "free": bool(free), "vals": vals, "c": c, "dec": d, "c_text": _fmt(c, d), "table": t.key}
    return {"kind": "p", "style": "body", "text": render(st), "stmt": st}


def wrong_value(rng, st):
    """틀린 결과 숫자(글자)."""
    c, d = st["c"], st["dec"]
    for _ in range(10):
        if d == 0:
            delta = max(1, int(abs(c) * rng.uniform(0.03, 0.15)))
            new = c + rng.choice([1, -1]) * delta
        else:
            new = c + rng.choice([1, -1]) * rng.uniform(0.4, 2.5) * (1 if st["type"] == "times" else 2)
        if new > 0 and _fmt(new, d) != st["c_text"]:
            return _fmt(new, d)
    return None


def before_text(st, n=14):
    """결과 숫자 바로 앞 글자(띄어쓰기 뺌) — PDF 줄바꿈으로 띄어쓰기가 달라져도 위치를 찾게."""
    return re.sub(r"\s+", "", _render(st, "\x00").split("\x00")[0])[-n:]
