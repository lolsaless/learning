"""비교 결과 → 문서 위 표시(mark) 만들기.

블록 순번(Block.index)마다 어떤 표시를 할지 정한다. 렌더러(document_view.py)는 이 표만 본다.

    Mark = {"cid": 변경번호, "type": modified|added|deleted|format,
            "segs": 글자 차이 조각 | None, "fmt": [(시작, 끝), ...] 서식 바뀐 글자 범위}

보기 방식(view)
    merged  새 버전(B)을 그리고, 지워진 글자·문단은 빨간 취소선으로 끼워 넣는다 (한 화면에 모두)
    a       이전 버전(A) 원본 모양 — 지워지거나 바뀐 곳을 빨강으로
    b       새 버전(B) 원본 모양 — 새로 넣거나 바뀐 곳을 초록으로
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

Mark = Dict[str, Any]


def build_marks(res: Dict[str, Any], side: str) -> Dict[int, Mark]:
    """side='a' → A 블록 기준, 'b'(또는 merged) → B 블록 기준."""
    marks: Dict[int, Mark] = {}
    for c in res["changes"]:
        idx = c["a_index"] if side == "a" else c["b_index"]
        if idx is None:
            continue
        rng_key = "a_range" if side == "a" else "b_range"
        marks[idx] = {
            "cid": c["id"], "type": c["type"], "label": c["label"], "summary": c["summary"],
            "segs": c["segments"] if c["type"] == "modified" else None,
            "fmt": [tuple(f[rng_key]) for f in c.get("format", []) if rng_key in f],
        }
    return marks


def build_ghosts(res: Dict[str, Any]) -> Tuple[Dict[int, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """merged 보기에서 지워진 블록(B 에 없음)을 끼워 넣을 자리: 바로 다음 B 블록 앞.
    돌려줌: ({B 블록 순번: [지워진 블록들]}, 문서 끝에 붙일 목록)."""
    by_id = {c["id"]: c for c in res["changes"]}
    before: Dict[int, List[Dict[str, Any]]] = {}
    pending: List[Dict[str, Any]] = []
    for row in res["rows"]:
        if row["bi"] is None:
            if row["cid"] is not None and by_id[row["cid"]]["type"] == "deleted":
                c = by_id[row["cid"]]
                pending.append({"cid": c["id"], "text": row["a"] or "", "location": c["location"]})
            continue
        if pending:
            before.setdefault(row["bi"], []).extend(pending)
            pending = []
    return before, pending
