"""두 문서 비교 — 짝짓기(align) → 글자 비교(inline) → 서식 비교(formatting) → 변경 목록.

변경 종류 (Change.type)
    modified  같은 자리 문단/셀의 글자가 바뀜
    added     새 버전에만 있음
    deleted   이전 버전에만 있음
    format    글자는 같고 서식(글자색·크기 등)만 바뀜
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from ..hwpx.model import Block, Document
from ..hwpx.styles import describe
from .align import Pair, align_blocks, filter_blocks
from .formatting import format_changes, inserted_style_notes
from .inline import inline_diff
from .options import CompareOptions
from .textutil import clip, has_number, normalize

TYPE_LABELS = {"modified": "수정", "added": "추가", "deleted": "삭제", "format": "서식"}
META_FIELDS = {"ModifiedDate": "마지막 수정일", "lastsaveby": "마지막 저장자", "creator": "작성자",
               "title": "제목", "subject": "주제", "keyword": "키워드", "application": "프로그램"}


@dataclass
class Change:
    id: int
    type: str
    label: str
    location: str
    context: str
    page_a: Optional[int]
    page_b: Optional[int]
    a_index: Optional[int]
    b_index: Optional[int]
    old_text: str
    new_text: str
    summary: str
    segments: List[Dict[str, str]] = field(default_factory=list)
    format: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


def compare_documents(da: Document, db: Document, opts: Optional[CompareOptions] = None) -> Dict[str, Any]:
    opts = opts or CompareOptions()
    a_blocks = filter_blocks(da.blocks, opts)
    b_blocks = filter_blocks(db.blocks, opts)
    pairs = align_blocks(a_blocks, b_blocks, opts)

    changes: List[Change] = []
    rows: List[Dict[str, Any]] = []
    for ia, ib in pairs:
        ba = a_blocks[ia] if ia is not None else None
        bb = b_blocks[ib] if ib is not None else None
        ch = _compare_pair(ba, bb, da, db, opts, len(changes) + 1)
        if ch:
            changes.append(ch)
        rows.append({
            "status": ch.type if ch else "same",
            "cid": ch.id if ch else None,
            "location": (bb or ba).location,
            "ai": ba.index if ba else None,
            "bi": bb.index if bb else None,
            "a": ba.text if ba else None,
            "b": bb.text if bb else None,
        })

    counts = {k: sum(1 for c in changes if c.type == k) for k in TYPE_LABELS}
    counts["total"] = len(changes)
    counts["numeric"] = sum(1 for c in changes if "숫자" in c.tags)
    return {
        "a": da.summary(), "b": db.summary(),
        "options": opts.to_dict(),
        "counts": counts,
        "headline": headline(counts),
        "meta_changes": meta_changes(da, db),
        "changes": [asdict(c) for c in changes],
        "rows": rows,
        "identical_file": da.sha1 == db.sha1,
    }


def _compare_pair(ba: Optional[Block], bb: Optional[Block], da: Document, db: Document,
                  opts: CompareOptions, cid: int) -> Optional[Change]:
    if ba is None or bb is None:
        blk = bb or ba
        typ = "added" if ba is None else "deleted"
        styles = (db if ba is None else da).styles
        tags = (["표"] if blk.kind == "cell" else []) + (["숫자"] if has_number(blk.text) else [])
        fmts = {describe(styles.get(r.style, {})) for r in blk.runs if r.text.strip()}
        return Change(
            id=cid, type=typ, label=TYPE_LABELS[typ], location=blk.location, context=blk.context,
            page_a=ba.page if ba else None, page_b=bb.page if bb else None,
            a_index=ba.index if ba else None, b_index=bb.index if bb else None,
            old_text=ba.text if ba else "", new_text=bb.text if bb else "",
            summary=f"‘{clip(blk.text.strip(), 50)}’ {TYPE_LABELS[typ]}",
            segments=[{"op": "insert" if ba is None else "delete", "text": blk.text}],
            notes=[f"서식: {', '.join(sorted(fmts))}"] if fmts else [], tags=tags,
        )

    inline = inline_diff(ba.text, bb.text, opts)
    fmt = format_changes(ba, bb, inline, da.styles, db.styles) if opts.include_format else []
    notes = inserted_style_notes(ba, bb, inline, da.styles, db.styles) if opts.include_format else []

    if inline.text_changed:
        typ = "modified"
        summary = inline.describe()
    elif fmt:
        typ = "format"
        summary = "서식 변경: " + "; ".join(f"‘{clip(f['text'], 16)}’ {', '.join(f['details'])}" for f in fmt[:2])
        if len(fmt) > 2:
            summary += f" 외 {len(fmt) - 2}곳"
    else:
        return None

    tags = []
    if bb.kind == "cell":
        tags.append("표")
    if inline.numeric:
        tags.append("숫자")
    if fmt or notes:
        tags.append("서식")
    if typ == "modified" and normalize(ba.text, True) == normalize(bb.text, True):
        tags.append("공백")
    return Change(
        id=cid, type=typ, label=TYPE_LABELS[typ], location=bb.location, context=bb.context,
        page_a=ba.page, page_b=bb.page, a_index=ba.index, b_index=bb.index,
        old_text=ba.text, new_text=bb.text, summary=summary, segments=inline.segments,
        format=fmt, notes=notes, tags=tags,
    )


def meta_changes(da: Document, db: Document) -> List[Dict[str, str]]:
    out = []
    for key, label in META_FIELDS.items():
        va, vb = da.meta.get(key, ""), db.meta.get(key, "")
        if va != vb:
            out.append({"field": label, "a": va, "b": vb})
    return out


def headline(counts: Dict[str, int]) -> str:
    if not counts.get("total"):
        return "내용 차이가 없습니다"
    parts = [f"{TYPE_LABELS[k]} {counts[k]}건" for k in TYPE_LABELS if counts.get(k)]
    s = f"총 {counts['total']}건 변경 — " + ", ".join(parts)
    if counts.get("numeric"):
        s += f" (숫자 관련 {counts['numeric']}건)"
    return s
