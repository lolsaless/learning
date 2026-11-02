"""(v1.1) 원본 문서 모양 보기 — 문서를 HTML 로 그리고 비교 결과의 바뀐 곳을 표시한다.

    render_view(A문서, B문서, 비교결과, view) → {"html"…, "order": [화면 순서대로 변경 번호]}
    view: 'merged'(B 위에 추가·삭제 함께) | 'pair'(A 원본 | B 원본 나란히)
    render_plain(문서) → 표시 없는 원본 모양
"""
from __future__ import annotations

import os
from typing import Any, Dict

from ..hwpx.model import Document
from .document_view import DocRenderer
from .marks import build_ghosts, build_marks

CSS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docview.css")
VIEWS = ("merged", "pair")


def doc_css() -> str:
    with open(CSS_PATH, encoding="utf-8") as f:
        return f.read()


def render_plain(doc: Document) -> Dict[str, Any]:
    return {"view": "plain", "html": DocRenderer(doc).render(), "order": []}


def render_view(da: Document, db: Document, res: Dict[str, Any], view: str = "merged") -> Dict[str, Any]:
    if view == "pair":
        ra = DocRenderer(da, build_marks(res, "a"), side="a")
        rb = DocRenderer(db, build_marks(res, "b"), side="b")
        html_a, html_b = ra.render(), rb.render()
        order = list(dict.fromkeys(rb.order + ra.order))
        order.sort(key=lambda cid: cid)          # 변경 번호 = 문서 순서
        return {"view": "pair", "html_a": html_a, "html_b": html_b, "order": order}
    ghosts, tail = build_ghosts(res)
    r = DocRenderer(db, build_marks(res, "b"), ghosts, tail, side="b", inline_ghost=True)
    return {"view": "merged", "html": r.render(), "order": r.order}


def render_merge(base: Document, plan: Dict[str, Any]) -> Dict[str, Any]:
    """(v2.0) 병합 화면: 원본을 그리고 병합 항목(번호 = 항목 순서 1부터)을 표시. 끼울 글은 초록 상자."""
    marks: Dict[int, Dict[str, Any]] = {}
    ghosts: Dict[int, list] = {}
    tail: list = []
    for n, it in enumerate(plan["items"], 1):
        usable = [o for o in it["options"] if not o["unsupported"]] or it["options"]
        first = usable[0]
        typ = "conflict" if it["conflict"] else first["type"]
        label = "충돌" if it["conflict"] else first["label"]
        summary = " / ".join(f"{o['vname']}: {o['summary']}" for o in it["options"])
        if it["base_index"] is not None:
            marks[it["base_index"]] = {"cid": n, "type": typ, "label": label, "summary": summary,
                                       "segs": None, "fmt": []}
        else:
            g = {"cid": n, "text": first["new_text"], "location": it["location"], "kind": "added",
                 "label": "추가 예정" if not it["conflict"] else "충돌"}
            if it["ghost_before"] is None:
                tail.append(g)
            else:
                ghosts.setdefault(it["ghost_before"], []).append(g)
    r = DocRenderer(base, marks, ghosts, tail, side="b", inline_ghost=False)
    return {"view": "merge", "html": r.render(), "order": r.order}


__all__ = ["render_view", "render_plain", "render_merge", "doc_css", "VIEWS"]
