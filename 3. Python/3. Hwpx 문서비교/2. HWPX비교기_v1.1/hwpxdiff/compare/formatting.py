"""서식 비교 — 같은 글자인데 글자색·크기·굵게 등이 바뀐 곳을 찾는다."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Sequence, Tuple

from ..hwpx.model import Block
from ..hwpx.styles import describe, describe_delta
from .inline import InlineResult

Styles = Dict[str, Dict[str, Any]]


def format_changes(a: Block, b: Block, inline: InlineResult, sa: Styles, sb: Styles) -> List[Dict[str, Any]]:
    """같은 글자(equal_chars)끼리 서식 키를 비교해 연속 구간으로 묶는다."""
    ca, cb = a.char_styles(), b.char_styles()
    out: List[Dict[str, Any]] = []
    cur = None   # [styleA, styleB, 글자 목록, A 시작, B 시작, A 끝, B 끝]
    last_ib = -2
    for ia, ib in inline.equal_chars:
        ka, kb = ca[ia], cb[ib]
        if ka == kb:
            cur = _flush(cur, out, sa, sb)
            continue
        if cur and cur[0] == ka and cur[1] == kb and ib == last_ib + 1:
            cur[2].append(b.text[ib])
            cur[5], cur[6] = ia + 1, ib + 1
        else:
            cur = _flush(cur, out, sa, sb)
            cur = [ka, kb, [b.text[ib]], ia, ib, ia + 1, ib + 1]
        last_ib = ib
    _flush(cur, out, sa, sb)
    return out


def _flush(cur, out, sa: Styles, sb: Styles):
    if cur:
        ka, kb, chars, a0, b0, a1, b1 = cur
        text = "".join(chars)
        details = describe_delta(sa.get(ka, {}), sb.get(kb, {}))
        if text.strip() and details:
            out.append({"text": text, "before": describe(sa.get(ka, {})),
                        "after": describe(sb.get(kb, {})), "details": list(details),
                        "a_range": [a0, a1], "b_range": [b0, b1]})
    return None


def dominant_style(block: Block) -> str:
    cnt = Counter(s for s, ch in zip(block.char_styles(), block.text) if not ch.isspace())
    return cnt.most_common(1)[0][0] if cnt else ""


def inserted_style_notes(a: Block, b: Block, inline: InlineResult, sa: Styles, sb: Styles) -> List[str]:
    """새로 넣은 글자가 원래 문단과 다른 서식이면 알려 준다 (예: 수정한 곳을 빨간색으로 표시한 경우)."""
    base = sa.get(dominant_style(a), {})
    if not base:
        return []
    cb = b.char_styles()
    notes: List[str] = []
    seen: set = set()
    for s, e in inline.inserted_ranges:
        text = b.text[s:e]
        if not text.strip():
            continue
        for key in dict.fromkeys(cb[s:e]):
            delta = describe_delta(base, sb.get(key, {}))
            if delta and (key, text) not in seen:
                seen.add((key, text))
                notes.append(f"새 글자 ‘{text.strip()[:20]}’ — " + ", ".join(delta))
    return notes


def block_style_summary(block: Block, styles: Styles) -> Sequence[Tuple[str, str]]:
    """블록 안 서식 목록 (추가·삭제된 블록의 서식 안내용)."""
    seen = []
    for r in block.runs:
        if r.text.strip() and r.style not in [s for s, _ in seen]:
            seen.append((r.style, describe(styles.get(r.style, {}))))
    return seen
