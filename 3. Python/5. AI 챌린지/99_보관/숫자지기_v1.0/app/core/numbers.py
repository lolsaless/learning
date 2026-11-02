# -*- coding: utf-8 -*-
"""숫자 읽기·비교 규칙 (화면·엔진 공통)."""
import re
import datetime
import math

from app import config

_NUM = r"(?:(?P<sign>[△▲▽\-−])\s?)?(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<frac>\d+))?"
NUM_RE = re.compile(r"(?<![A-Za-z0-9.,])" + _NUM)
CELL_RE = re.compile(r"^\s*" + _NUM + r"\s*(?P<unit>%p|%|[가-힣A-Za-z㎍㎎/㎥㎡]{0,4})\s*$")
_SKIP = [re.compile(p) for p in config.SKIP_PATTERNS]
_LIST = re.compile(config.LIST_MARK)
_UNITS = sorted(config.UNITS, key=len, reverse=True)


def _token(m, text):
    sign = m.group("sign") or ""
    ip = m.group("int").replace(",", "")
    fp = m.group("frac") or ""
    val = float(ip + ("." + fp if fp else ""))
    if sign in ("△", "▽", "-", "−"):
        val = -val
    dec = len(fp)
    end = m.end()
    rest = text[end:end + 8].lstrip()
    unit = ""
    for u in _UNITS:
        if rest.startswith(u):
            unit = u
            break
    return {
        "start": m.start(), "end": end,
        "raw": text[m.start():end],
        "value": val, "dec": dec, "unit": unit,
        "comma": "," in m.group("int"),
    }


def parse_cell(text):
    """표 칸 글자가 '숫자 하나(+단위)'이면 숫자 정보를, 아니면 None."""
    if text is None:
        return None
    t = text.strip()
    if not t:
        return None
    m = CELL_RE.match(t)
    if not m:
        return None
    # 연도 머리글(2025, 2026년)은 숫자로 보지 않음
    unit = m.group("unit") or ""
    if unit in ("년", "월", "일", "분기"):
        return None
    lead = len(text) - len(text.lstrip())
    m2 = NUM_RE.search(text, lead)
    tok = _token(m2, text)
    tok["unit"] = unit
    return tok


def _skip_spans(text):
    spans = []
    for rx in _SKIP:
        for m in rx.finditer(text):
            spans.append((m.start(), m.end()))
    lm = _LIST.match(text)
    if lm:
        spans.append((lm.start(), lm.end()))
    return spans


def extract_numbers(text):
    """본문 문장에서 데이터 숫자를 찾는다(날짜·조문·연도·항목기호 제외)."""
    out = []
    if not text:
        return out
    spans = _skip_spans(text)
    for m in NUM_RE.finditer(text):
        s, e = m.start(), m.end()
        if any(not (e <= a or s >= b) for a, b in spans):
            continue
        tok = _token(m, text)
        # 단위가 없고 쉼표·소수점도 없는 한 자리 숫자는 의미 없는 경우가 많음 → 제외
        if not tok["unit"] and not tok["comma"] and tok["dec"] == 0 and abs(tok["value"]) < 10:
            continue
        out.append(tok)
    return out


def find_placeholders(text):
    out = []
    for ph in config.PLACEHOLDERS:
        start = 0
        while True:
            i = text.find(ph, start)
            if i < 0:
                break
            out.append({"start": i, "end": i + len(ph), "raw": ph, "value": None, "dec": 0,
                        "unit": "", "comma": False, "placeholder": True})
            start = i + len(ph)
    return sorted(out, key=lambda x: x["start"])


def tol(dec):
    return 0.5 * (10 ** -dec) + config.CALC_SLACK


def close(x, v, dec):
    """원본 값 x를 표시 자릿수 dec로 반올림했을 때 v가 되는가."""
    if x is None or v is None:
        return False
    return abs(x - v) <= tol(dec) + 1e-12 * max(1.0, abs(v))


def exact(x, v):
    return x is not None and v is not None and abs(x - v) <= 1e-9 * max(1.0, abs(v))


def fmt(x, dec=0, comma=True):
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    s = f"{x:,.{dec}f}" if comma else f"{x:.{dec}f}"
    return s


def fmt_auto(x):
    if x is None:
        return ""
    if isinstance(x, (int,)) or (isinstance(x, float) and x.is_integer() and abs(x) < 1e15):
        return f"{int(x):,}"
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    ip, _, fp = s.partition(".")
    try:
        ip = f"{int(ip):,}"
    except ValueError:
        pass
    return ip + ("." + fp if fp else "")


# ── 날짜·요일 ─────────────────────────────────────────
WD = "월화수목금토일"
DATE_WD = re.compile(r"(?:(?P<y>\d{4})\s*\.\s*)?(?P<m>\d{1,2})\s*\.\s*(?P<d>\d{1,2})\s*\.?\s*[\(（]\s*(?P<w>[월화수목금토일])\s*[\)）]")


def weekday_issues(text, default_year):
    out = []
    for m in DATE_WD.finditer(text or ""):
        y = int(m.group("y")) if m.group("y") else default_year
        if not y:
            continue
        try:
            dt = datetime.date(y, int(m.group("m")), int(m.group("d")))
        except ValueError:
            out.append({"start": m.start(), "end": m.end(), "raw": m.group(0),
                        "msg": "없는 날짜입니다"})
            continue
        real = WD[dt.weekday()]
        if real != m.group("w"):
            out.append({"start": m.start(), "end": m.end(), "raw": m.group(0),
                        "msg": f"{dt.year}. {dt.month}. {dt.day}.은 {real}요일입니다(문서: {m.group('w')})",
                        "expected": real})
    return out


# ── 증감률 문장 ───────────────────────────────────────
_N = r"\d[\d,]*(?:\.\d+)?"
CLAIM = re.compile(
    r"(?P<a>" + _N + r")\s*(?P<u>건|명|천원|백만원|원|대|곳|개소|개|회|%)"
    r"[^()]{0,40}?[\(（]\s*(?:전년(?:도)?(?:\s*동기)?|'?\d{2}년)?\s*(?P<b>" + _N + r")\s*(?P=u)?\s*[\)）]"
    r"\s*대비\s*(?P<c>" + _N + r")\s*(?P<cu>%p|%)\s*(?P<d>증가|감소|상승|하락|늘|줄)"
)


def _f(s):
    return float(s.replace(",", ""))


def change_claims(text):
    """'A건으로 전년(B건) 대비 C% 증가' 형태를 찾아 다시 계산한다."""
    out = []
    for m in CLAIM.finditer(text or ""):
        a, b, c = _f(m.group("a")), _f(m.group("b")), _f(m.group("c"))
        cdec = len(m.group("c").split(".")[1]) if "." in m.group("c") else 0
        up = m.group("d") in ("증가", "상승", "늘")
        if m.group("cu") == "%p":
            exp = abs(a - b)
            how = f"{fmt_auto(a)} − {fmt_auto(b)}"
        else:
            if b == 0:
                continue
            exp = abs(a - b) / b * 100
            how = f"({fmt_auto(a)} − {fmt_auto(b)}) ÷ {fmt_auto(b)} × 100"
        dir_ok = (a >= b) == up
        ok = close(exp, c, cdec) and dir_ok
        out.append({
            "start": m.start("c"), "end": m.end("c"), "raw": m.group(0),
            "ok": ok, "expected": round(exp, max(cdec, 1)),
            "expected_text": fmt(exp, cdec) + m.group("cu"),
            "direction_ok": dir_ok,
            "msg": ("증감률 확인" if ok else
                    f"다시 계산하면 {fmt(exp, cdec)}{m.group('cu')} {'증가' if a >= b else '감소'}입니다"
                    f" [{how}]"),
        })
    return out


def guess_year(texts):
    cnt = {}
    for t in texts:
        for m in re.finditer(r"(20\d{2})\s*[\.년]", t or ""):
            y = int(m.group(1))
            cnt[y] = cnt.get(y, 0) + 1
    if not cnt:
        return datetime.date.today().year
    return max(cnt.items(), key=lambda kv: kv[1])[0]


def is_total_label(s):
    t = (s or "").replace(" ", "")
    return t in [w.replace(" ", "") for w in config.TOTAL_WORDS] or t.endswith("합계") or t.endswith("소계")


def is_ratio_label(s):
    t = s or ""
    return any(w in t for w in config.RATIO_WORDS)


def is_average_label(s):
    t = s or ""
    return any(w in t for w in config.AVERAGE_WORDS)
