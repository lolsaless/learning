# -*- coding: utf-8 -*-
"""[AI 파트 ③] 검산식 검사와 계산 — 'AI 출력은 프로그램이 검증한다'의 핵심.

검산식(check) 하나 = {"type": "diff"|"rate"|"share"|"times"|"sum"|"avg", 숫자 칸들…}
  1) validate(check, 문장)  형식이 맞는가? 모든 숫자가 문장에 글자 그대로 있는가?(지어낸 숫자 차단)
  2) compute(check)         프로그램이 직접 계산해 맞는지 정한다(AI 판단을 쓰지 않음)
"""
import re

from app.common import numbers as N

ROLES = {
    "diff": ("a", "b", "c"),
    "rate": ("a", "b", "c"),
    "share": ("part", "whole", "c"),
    "times": ("a", "b", "c"),
    "sum": ("parts", "total"),
    "avg": ("parts", "c"),
}
NAMES = {"diff": "차이", "rate": "증감률", "share": "비중", "times": "배수", "sum": "합계", "avg": "평균"}
UP = ("증가", "상승", "많", "늘", "앞")
DOWN = ("감소", "하락", "적", "줄", "뒤")


def result_role(t):
    return "total" if t == "sum" else "c"


def tokens(text):
    """문장 속 모든 숫자(날짜 등도 포함 — 위치 확인용)."""
    out = []
    for m in N.NUM_RE.finditer(text or ""):
        raw = text[m.start("int"):m.end()]
        out.append({"start": m.start("int"), "end": m.end(), "raw": raw, "key": raw.replace(",", "")})
    return out


def _num(s):
    s = str(s).strip().replace(" ", "")
    if not re.fullmatch(r"\d[\d,]*(?:\.\d+)?", s):
        return None
    return float(s.replace(",", ""))


def _dec(s):
    s = str(s)
    return len(s.split(".")[1]) if "." in s else 0


def validate(check, text):
    """→ (정리된 검산식, None) 또는 (None, 탈락 이유)."""
    if not isinstance(check, dict):
        return None, "검산식이 객체(JSON)가 아님"
    t = check.get("type")
    if t not in ROLES:
        return None, f"모르는 계산 종류: {t}"
    toks = tokens(text)
    used = set()
    out = {"type": t}
    pos_hint = list(check.get("_pos") or [])       # 역할 순서대로의 시작 위치(규칙 읽기만)

    def place(s, role):
        if not isinstance(s, (str, int, float)):
            return f"{role} 값이 글자가 아님"
        s = str(s).strip()
        v = _num(s)
        if v is None:
            return f"{role} 값 '{s}'이(가) 숫자가 아님"
        hits = [i for i, tk in enumerate(toks) if tk["key"] == s.replace(",", "") and i not in used]
        if not hits:
            return f"문장에 없는 숫자 '{s}'(지어낸 숫자로 보고 버림)"
        pos = pos_hint.pop(0) if pos_hint else None          # 규칙 읽기는 정확한 위치를 함께 준다
        i = next((h for h in hits if toks[h]["start"] == pos), hits[0])
        used.add(i)
        return {"raw": toks[i]["raw"], "value": v, "dec": _dec(toks[i]["raw"]),
                "start": toks[i]["start"], "end": toks[i]["end"]}

    for role in ROLES[t]:
        if role not in check:
            return None, f"'{role}' 칸이 빠짐"
        if role == "parts":
            ps = check["parts"]
            if not isinstance(ps, list) or len(ps) < 2:
                return None, "parts 는 숫자 2개 이상의 목록이어야 함"
            out["parts"] = []
            for s in ps:
                r = place(s, "parts")
                if isinstance(r, str):
                    return None, r
                out["parts"].append(r)
        else:
            r = place(check[role], role)
            if isinstance(r, str):
                return None, r
            out[role] = r
    d = str(check.get("dir") or "")
    out["dir"] = "증가" if d.startswith(UP) else ("감소" if d.startswith(DOWN) else "")
    if t == "rate" and not out["dir"]:
        return None, "증감률은 증가·감소 방향(dir)이 필요함"
    return out, None


def compute(ck):
    """프로그램 계산 → {"ok", "expected", "expected_text", "formula", "msg"}."""
    t = ck["type"]
    f = N.fmt_auto
    rr = ck[result_role(t)]
    cdec = rr["dec"]
    dir_ok = True
    if t in ("diff", "rate"):
        a, b = ck["a"]["value"], ck["b"]["value"]
        if t == "diff":
            exp = abs(a - b)
            how = f"{f(a)} − {f(b)}" if a >= b else f"{f(b)} − {f(a)}"
        else:
            if b == 0:
                return None
            exp = abs(a - b) / b * 100
            how = f"({f(a)} − {f(b)}) ÷ {f(b)} × 100"
        if ck.get("dir"):
            dir_ok = (a >= b) == (ck["dir"] == "증가")
    elif t == "share":
        p, w = ck["part"]["value"], ck["whole"]["value"]
        if w == 0:
            return None
        exp = p / w * 100
        how = f"{f(p)} ÷ {f(w)} × 100"
    elif t == "times":
        a, b = ck["a"]["value"], ck["b"]["value"]
        if b == 0:
            return None
        exp = a / b
        how = f"{f(a)} ÷ {f(b)}"
    elif t == "sum":
        exp = sum(p["value"] for p in ck["parts"])
        how = " + ".join(f(p["value"]) for p in ck["parts"])
    else:
        vs = [p["value"] for p in ck["parts"]]
        exp = sum(vs) / len(vs)
        how = f"({' + '.join(f(v) for v in vs)}) ÷ {len(vs)}"
    ok = N.close(exp, rr["value"], cdec) and dir_ok
    exp_text = N.fmt(exp, cdec, comma=abs(exp) >= 1000)
    if ok:
        msg = f"{NAMES[t]} 확인: {how} = {exp_text}"
    elif not dir_ok:
        msg = f"방향이 반대입니다: {f(ck['a']['value'])} {'>' if ck['a']['value'] >= ck['b']['value'] else '<'} {f(ck['b']['value'])}"
    else:
        msg = f"다시 계산하면 {how} = {exp_text} 입니다(문장에는 {rr['raw']})"
    return {"ok": ok, "expected": exp, "expected_text": exp_text, "formula": how, "msg": msg, "direction_ok": dir_ok}


def check_text(ck):
    """사람이 읽는 검산식 한 줄."""
    t = ck["type"]
    if t == "sum":
        return " + ".join(p["raw"] for p in ck["parts"]) + " = " + ck["total"]["raw"]
    if t == "avg":
        return "평균(" + ", ".join(p["raw"] for p in ck["parts"]) + ") = " + ck["c"]["raw"]
    if t == "share":
        return f"{ck['part']['raw']} ÷ {ck['whole']['raw']} × 100 = {ck['c']['raw']}%"
    if t == "times":
        return f"{ck['a']['raw']} ÷ {ck['b']['raw']} = {ck['c']['raw']}배"
    if t == "rate":
        return f"{ck['a']['raw']} vs {ck['b']['raw']} → {ck['c']['raw']}% {ck['dir']}"
    return f"{ck['a']['raw']} − {ck['b']['raw']} = {ck['c']['raw']}" + (f" ({ck['dir']})" if ck.get("dir") else "")
