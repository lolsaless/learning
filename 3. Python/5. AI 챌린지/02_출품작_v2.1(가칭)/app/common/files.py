# -*- coding: utf-8 -*-
"""파일·경로·숫자 표시에 쓰는 작은 도구 모음(어느 파트에도 의존하지 않음)."""
import os
import hashlib
from decimal import Decimal, ROUND_HALF_UP

from app.common import numbers as N


def sha256(path):
    """파일 내용의 고유값(SHA-256). 내용이 한 글자라도 바뀌면 값이 달라진다."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def norm(p):
    """경로 비교용 표준형(대소문자·상대경로 차이 제거)."""
    return os.path.normcase(os.path.abspath(p))


def is_inside(path, folder):
    return norm(path).startswith(norm(folder) + os.sep)


def fmt_value(x, dec=None, scale=1.0, comma=True):
    """숫자를 문서에 넣을 글자로 바꾼다. dec=소수 자릿수(None이면 자동), scale=배율."""
    if x is None:
        return ""
    v = x * scale
    if dec is None:
        return N.fmt_auto(v) if comma else N.fmt_auto(v).replace(",", "")
    q = Decimal(1).scaleb(-dec)
    d = Decimal(repr(v)).quantize(q, rounding=ROUND_HALF_UP)
    return f"{d:,.{dec}f}" if comma else f"{d:.{dec}f}"
