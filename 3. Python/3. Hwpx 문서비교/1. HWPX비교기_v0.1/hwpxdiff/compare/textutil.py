"""글자 다루기 도구 — 정규화, 단어 쪼개기, 숫자 판별, 유사도."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List

_WS = re.compile(r"\s+")
# 숫자(소수점·천단위 쉼표 포함) | 한글·영문 단어 | 공백 덩어리 | 그 밖의 글자 1개
_TOKEN = re.compile(r"\d+(?:[.,]\d+)*|[가-힣ㄱ-ㅎㅏ-ㅣA-Za-z]+|\s+|.", re.S)
_NUMBER = re.compile(r"\d")


def normalize(text: str, ignore_whitespace: bool) -> str:
    return _WS.sub(" ", text).strip() if ignore_whitespace else text


def tokenize(text: str, granularity: str = "word") -> List[str]:
    if granularity == "char":
        return list(text)
    return _TOKEN.findall(text)


def has_number(text: str) -> bool:
    return bool(_NUMBER.search(text or ""))


def similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    sm = SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < 0.2:
        return sm.real_quick_ratio()
    return sm.ratio()


def clip(text: str, n: int = 40) -> str:
    text = text.replace("\n", " ⏎ ").replace("\t", " ")
    return text if len(text) <= n else text[: n - 1] + "…"
