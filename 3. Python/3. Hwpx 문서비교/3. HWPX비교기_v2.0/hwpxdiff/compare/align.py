"""블록 짝짓기 — 이전 버전의 어느 문단/셀이 새 버전의 어느 것에 해당하는지 찾는다.

1단계: 블록 글자 전체를 한 줄로 보고 difflib 로 '같은 줄' 을 맞춘다 (빠르고 순서 유지).
2단계: 서로 다른 구간(replace)은 글자 유사도로 다시 짝을 지어
       비슷하면 '수정', 아니면 '삭제'/'추가' 로 나눈다.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import List, Optional, Sequence, Tuple

from ..hwpx.model import Block
from .options import CompareOptions
from .textutil import normalize, similarity

Pair = Tuple[Optional[int], Optional[int]]   # (A 블록 순번 | None, B 블록 순번 | None)

REGION_LIMIT = 400      # 이보다 큰 replace 구간은 유사도 짝짓기를 생략 (속도 보호)


def _key(b: Block, opts: CompareOptions) -> str:
    # 종류가 다르면(문단↔표 셀) 같은 글자라도 짝짓지 않도록 종류를 붙인다
    return f"{b.kind}|{normalize(b.text, opts.ignore_whitespace)}"


def filter_blocks(blocks: Sequence[Block], opts: CompareOptions) -> List[Block]:
    if opts.include_tables:
        return list(blocks)
    return [b for b in blocks if b.kind != "cell" and "표 " not in b.location]


def align_blocks(a: Sequence[Block], b: Sequence[Block], opts: CompareOptions) -> List[Pair]:
    ka = [_key(x, opts) for x in a]
    kb = [_key(x, opts) for x in b]
    sm = SequenceMatcher(None, ka, kb, autojunk=False)
    pairs: List[Pair] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            pairs.extend(zip(range(i1, i2), range(j1, j2)))
        elif op == "delete":
            pairs.extend((i, None) for i in range(i1, i2))
        elif op == "insert":
            pairs.extend((None, j) for j in range(j1, j2))
        else:
            pairs.extend(_pair_region(a, b, i1, i2, j1, j2, opts))
    return pairs


def _score(x: Block, y: Block, opts: CompareOptions) -> float:
    if x.kind != y.kind:
        return 0.0
    s = similarity(normalize(x.text, opts.ignore_whitespace), normalize(y.text, opts.ignore_whitespace))
    if x.kind == "cell" and (x.row, x.col) == (y.row, y.col):
        s += 0.15      # 같은 행·열 위치의 셀이면 가산점
    return s


def _pair_region(a, b, i1, i2, j1, j2, opts) -> List[Pair]:
    """순서를 지키며 가장 점수가 높은 짝을 고르는 동적계획법 (작은 구간 전용)."""
    n, m = i2 - i1, j2 - j1
    if n * m > REGION_LIMIT * REGION_LIMIT // 4:
        return [(i, None) for i in range(i1, i2)] + [(None, j) for j in range(j1, j2)]
    th = opts.similarity
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    sim = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            sim[i][j] = _score(a[i1 + i], b[j1 + j], opts)
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            best = max(score[i + 1][j], score[i][j + 1])
            if sim[i][j] >= th:
                best = max(best, sim[i][j] + score[i + 1][j + 1])
            score[i][j] = best
    out: List[Pair] = []
    i = j = 0
    while i < n and j < m:
        if sim[i][j] >= th and abs(score[i][j] - (sim[i][j] + score[i + 1][j + 1])) < 1e-9:
            out.append((i1 + i, j1 + j))
            i += 1
            j += 1
        elif score[i + 1][j] >= score[i][j + 1]:
            out.append((i1 + i, None))
            i += 1
        else:
            out.append((None, j1 + j))
            j += 1
    out.extend((i1 + k, None) for k in range(i, n))
    out.extend((None, j1 + k) for k in range(j, m))
    return out
