# -*- coding: utf-8 -*-
"""[AI 파트 ④] AI 없이 읽는 '규칙 읽기'와, 시험용 모의 AI 의 읽기 흉내.

rule_read(문장)  → 검산식 목록. 정해진 문형만 읽는다(틀리게 읽을 위험이 낮아 결과를 빨강으로 단정할 수 있음).
mock_read(문장)  → 모의 AI 가 쓰는 느슨한 읽기(실제 AI 대신 시험용). 결과는 AI 읽기와 같은 취급(노랑).
'대비 C% 증가' 증감률 문형은 검증 엔진(numbers.change_claims)이 이미 처리하므로 여기서는 읽지 않는다.
"""
import re

_N = r"\d[\d,]*(?:\.\d+)?"
_U = r"(?P<u>건|명|천원|백만원|억원|원|대|곳|개소|개|회|톤|일)"

DIFF = re.compile(rf"(?P<a>{_N})\s*{_U}[^()（）]{{0,40}}?[(（]\s*[^()（）0-9]{{0,12}}?(?P<b>{_N})\s*(?P=u)\s*[)）]\s*보다\s*"
                  rf"(?P<c>{_N})\s*(?P=u)\s*(?:이|가)?\s*(?:더\s*)?(?P<d>많|적|증가|감소|늘|줄)")
SHARE1 = re.compile(rf"(?P<whole>{_N})\s*{_U}\s*중\s*[^()（）0-9]{{0,30}}?(?P<part>{_N})\s*(?P=u)\s*[(（]\s*(?P<c>{_N})\s*%\s*[)）]")
SHARE2 = re.compile(rf"(?P<part>{_N})\s*{_U}[^()（）0-9]{{0,20}}?전체\s*[(（]\s*(?P<whole>{_N})\s*(?P=u)\s*[)）]\s*의\s*(?P<c>{_N})\s*%")
TIMES = re.compile(rf"[(（]\s*(?P<a>{_N})\s*{_U}\s*[)）][^()（）0-9]{{0,30}}?[(（]\s*(?P<b>{_N})\s*(?P=u)\s*[)）]\s*의\s*(?P<c>{_N})\s*배")
SUM_KEY = re.compile(rf"(?:을|를)?\s*(?:합하여|합하면|합한|합쳐|합계)\s*(?:총\s*)?(?P<t>{_N})\s*{_U}")
PART = re.compile(rf"(?<![\d,.])(?P<n>{_N})\s*{_U}")


def _ck(m, t, roles, d=None):
    ck = {"type": t, "_pos": [m.start(r) for r in roles]}
    for r in roles:
        ck[r] = m.group(r)
    if d is not None:
        ck["dir"] = "증가" if m.group(d) in ("많", "증가", "늘") else "감소"
    return ck


def rule_read(text):
    out = []
    for m in DIFF.finditer(text):
        out.append(_ck(m, "diff", ("a", "b", "c"), "d"))
    for rx in (SHARE1, SHARE2):
        for m in rx.finditer(text):
            out.append(_ck(m, "share", ("part", "whole", "c")))
    for m in TIMES.finditer(text):
        out.append(_ck(m, "times", ("a", "b", "c")))
    for m in SUM_KEY.finditer(text):
        # 같은 문장(마침표·세미콜론 뒤부터) 안, 괄호 밖, 같은 단위인 앞 숫자들 = 더하는 값
        head = text[:m.start()]
        cut = max(head.rfind(". "), head.rfind("; "), head.rfind("다 "), head.rfind("음 "))
        seg_start = cut + 1 if cut >= 0 else 0
        seg = head[seg_start:]
        depth, parts = 0, []
        opened = [i for i, ch in enumerate(seg) if ch in "(（"]
        closed = [i for i, ch in enumerate(seg) if ch in ")）"]
        for p in PART.finditer(seg):
            depth = sum(1 for i in opened if i < p.start()) - sum(1 for i in closed if i < p.start())
            if depth == 0 and p.group("u") == m.group("u"):
                parts.append(p)
        if len(parts) >= 2:
            out.append({"type": "sum", "parts": [p.group("n") for p in parts], "total": m.group("t"),
                        "_pos": [seg_start + p.start("n") for p in parts] + [m.start("t")]})
    return out


# ── 시험용 모의 AI ─────────────────────────────────────
_NUM_U = re.compile(rf"(?<![\d,.])({_N})\s*(%|배|건|명|천원|백만원|원|대|곳|개소|개|회|톤|일)")


def mock_read(text):
    nums = [(m.group(1), m.group(2)) for m in _NUM_U.finditer(text)]
    plain = [n for n, u in nums if u not in ("%", "배")]
    pct = [n for n, u in nums if u == "%"]
    bae = [n for n, u in nums if u == "배"]
    f = lambda s: float(s.replace(",", ""))
    if bae and len(plain) >= 2:
        x, y = plain[0], plain[1]
        a, b = (x, y) if f(x) >= f(y) else (y, x)
        return [{"type": "times", "a": a, "b": b, "c": bae[0]}]
    if pct and len(plain) >= 2 and ("전체" in text or "가운데" in text or "중" in text):
        x, y = plain[0], plain[1]
        part, whole = (x, y) if f(x) <= f(y) else (y, x)
        return [{"type": "share", "part": part, "whole": whole, "c": pct[0]}]
    if re.search(r"더한|더하|합하|합친|합쳐|모두 더", text) and len(plain) >= 3:
        return [{"type": "sum", "parts": plain[1:], "total": plain[0]}]
    if re.search(r"앞섰|많|적|차이|늘|줄", text) and len(plain) >= 3:
        d = "감소" if re.search(r"뒤졌|적|줄", text) else "증가"
        return [{"type": "diff", "a": plain[0], "b": plain[1], "c": plain[2], "dir": d}]
    return []
