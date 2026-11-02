"""문단 안 글자 비교 — 어느 글자가 지워지고(삭제) 들어왔는지(추가) 조각으로 나눈다.

결과 조각(segment): {"op": "equal"|"delete"|"insert", "text": "..."}
  · equal 조각의 text 는 새 버전(B) 글자. 공백 무시로 A 쪽 글자가 다르면 "a" 에 A 글자를 함께 둔다
    (v1.1 문서 보기에서 A 문서 글자 위치를 정확히 맞추기 위해).
화면에서는 delete=빨간 취소선, insert=초록 밑줄로 그린다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

from .options import CompareOptions
from .textutil import clip, has_number, tokenize

Segment = Dict[str, str]


@dataclass
class InlineResult:
    segments: List[Segment] = field(default_factory=list)
    equal_chars: List[Tuple[int, int]] = field(default_factory=list)   # (A 글자 위치, B 글자 위치)
    inserted_ranges: List[Tuple[int, int]] = field(default_factory=list)  # B 글자 [시작, 끝)
    edits: List[Tuple[str, str]] = field(default_factory=list)          # (지운 글자, 넣은 글자)

    @property
    def text_changed(self) -> bool:
        return bool(self.edits)

    @property
    def numeric(self) -> bool:
        return any(has_number(a) or has_number(b) for a, b in self.edits)

    def describe(self, limit: int = 3) -> str:
        parts = []
        for old, new in self.edits[:limit]:
            old, new = (old.strip() or old), (new.strip() or new)   # 앞뒤 공백은 표시에서 뺌
            if old and new:
                parts.append(f"‘{clip(old, 24)}’ → ‘{clip(new, 24)}’")
            elif new:
                parts.append(f"‘{clip(new, 24)}’ 추가")
            else:
                parts.append(f"‘{clip(old, 24)}’ 삭제")
        if len(self.edits) > limit:
            parts.append(f"외 {len(self.edits) - limit}곳")
        return ", ".join(parts)


def _offsets(tokens: List[str]) -> List[int]:
    out, pos = [], 0
    for t in tokens:
        out.append(pos)
        pos += len(t)
    out.append(pos)
    return out


def _refinable(sa: str, sb: str, n_old: int, n_new: int) -> bool:
    if has_number(sa) or has_number(sb) or not sa.strip() or not sb.strip():
        return False
    return (n_old == 1 and len(sa) >= 2 and n_new <= 8) or (n_new == 1 and len(sb) >= 2 and n_old <= 8)


def inline_diff(a: str, b: str, opts: CompareOptions) -> InlineResult:
    res = InlineResult()
    ta, tb = tokenize(a, opts.granularity), tokenize(b, opts.granularity)
    oa, ob = _offsets(ta), _offsets(tb)

    def key(t: str) -> str:
        return " " if opts.ignore_whitespace and t.isspace() else t

    sm = SequenceMatcher(None, [key(t) for t in ta], [key(t) for t in tb], autojunk=False)
    raw: List[Segment] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        sa, sb = a[oa[i1]:oa[i2]], b[ob[j1]:ob[j2]]
        if op == "equal":
            raw.append({"op": "equal", "text": sb, "a": sa})
            for i, j in zip(range(i1, i2), range(j1, j2)):
                if len(ta[i]) == len(tb[j]):           # 길이가 같은 토큰만 글자 단위 대응
                    res.equal_chars.extend(zip(range(oa[i], oa[i + 1]), range(ob[j], ob[j + 1])))
            continue
        # 교체 구간을 글자 단위로 한 번 더 쪼갠다
        #   경기북부 → 경기남부   : ‘북’ → ‘남’
        #   개소 → 개소에서 직접  : ‘에서 직접’ 추가
        # (숫자는 3.2 → 2.2 처럼 통째로 보여 주는 편이 읽기 쉬워 제외)
        if op == "replace" and _refinable(sa, sb, i2 - i1, j2 - j1):
            sub = SequenceMatcher(None, sa, sb, autojunk=False)
            if sub.ratio() >= 0.5 or sb.startswith(sa) or sb.endswith(sa) \
                    or sa.startswith(sb) or sa.endswith(sb):
                for sop, x1, x2, y1, y2 in sub.get_opcodes():
                    if sop == "equal":
                        raw.append({"op": "equal", "text": sb[y1:y2], "a": sa[x1:x2]})
                        res.equal_chars.extend(zip(range(oa[i1] + x1, oa[i1] + x2),
                                                   range(ob[j1] + y1, ob[j1] + y2)))
                    else:
                        _push_edit(res, raw, sa[x1:x2], sb[y1:y2], ob[j1] + y1, opts)
                continue
        _push_edit(res, raw, sa, sb, ob[j1], opts)

    # 같은 종류 조각 합치기
    for seg in raw:
        if not seg["text"] and not seg.get("a"):
            continue
        if res.segments and res.segments[-1]["op"] == seg["op"]:
            last = res.segments[-1]
            last["text"] += seg["text"]
            if "a" in last or "a" in seg:
                last["a"] = last.get("a", "") + seg.get("a", "")
        else:
            res.segments.append(dict(seg))
    for seg in res.segments:          # A 글자가 B 와 같으면 "a" 는 생략 (JSON 크기 절약)
        if seg.get("a") == seg["text"]:
            del seg["a"]
    return res


def _push_edit(res: InlineResult, raw: List[Segment], old: str, new: str, b_start: int,
               opts: CompareOptions) -> None:
    if old:
        raw.append({"op": "delete", "text": old})
    if new:
        raw.append({"op": "insert", "text": new})
        res.inserted_ranges.append((b_start, b_start + len(new)))
    # 공백만 바뀐 경우는 '공백 무시' 옵션이면 변경으로 세지 않는다
    if opts.ignore_whitespace and not old.strip() and not new.strip():
        return
    res.edits.append((old, new))
