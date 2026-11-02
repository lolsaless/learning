"""여러 버전 이력 — 원본을 정하지 않고, 저장 시각 순서로 줄을 세워 단계별 변화를 추적한다.

    v1 ─비교→ v2 ─비교→ v3 ...
각 단계의 짝짓기 결과를 이어 붙여 '같은 문단/셀이 버전마다 어떻게 바뀌었는지' 줄(chain)을 만든다.
→ 대시보드 '이력 추적표': 행 = 위치, 열 = 버전, 칸 = 그 버전의 글자.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from ..hwpx.model import Document
from .differ import TYPE_LABELS
from .textutil import clip

CompareFn = Callable[[Document, Document], Dict[str, Any]]

CHAIN_LABELS = {"changed": "변경", "reverted": "되돌림", "added": "추가됨", "deleted": "삭제됨",
                "format": "서식만", "flip": "추가 후 삭제"}


def order_documents(docs: Sequence[Document], mode: str = "modified") -> List[Document]:
    """mode: 'modified'(문서 속 마지막 수정일) | 'name'(파일 이름)."""
    if mode == "name":
        return sorted(docs, key=lambda d: d.name)
    return sorted(docs, key=lambda d: (d.modified or "9999", d.name))


def build_history(docs: Sequence[Document], compare: CompareFn) -> Dict[str, Any]:
    """docs 는 이미 정렬된 버전 목록. compare 는 (A, B) → compare_documents 결과 (캐시 사용 가능)."""
    versions = [{"no": i + 1, "id": d.id, "name": d.name, "modified": d.modified,
                 "author": d.meta.get("lastsaveby", ""), "stats": d.stats} for i, d in enumerate(docs)]
    if len(docs) < 2:
        return {"versions": versions, "steps": [], "chains": [], "counts": {}}

    comps = [compare(docs[k], docs[k + 1]) for k in range(len(docs) - 1)]
    steps = []
    for k, c in enumerate(comps):
        steps.append({
            "from": k + 1, "to": k + 2, "a": docs[k].id, "b": docs[k + 1].id,
            "counts": c["counts"], "headline": c["headline"], "identical_file": c["identical_file"],
            "meta_changes": c["meta_changes"],
            "highlights": [{"id": x["id"], "type": x["type"], "label": x["label"],
                            "location": x["location"], "summary": x["summary"]} for x in c["changes"][:8]],
        })

    chains = _link_chains(comps, len(docs))
    by_cid = [{x["id"]: x for x in c["changes"]} for c in comps]
    total_blocks = [max(1, len(d.blocks)) for d in docs]
    changed = []
    for ch in chains:
        if all(s == "same" for s in ch["steps"]):
            continue
        ch["kind"] = _classify(ch)
        ch["kind_label"] = CHAIN_LABELS[ch["kind"]]
        ch["n_changes"] = sum(1 for s in ch["steps"] if s not in ("same", ""))
        ch["texts_short"] = [None if t is None else clip(t, 60) for t in ch["texts"]]
        ch["steps_label"] = [TYPE_LABELS.get(s, "") for s in ch["steps"]]
        # 단계별 글자 차이 조각 (화면에서 바뀐 글자 강조용)
        ch["diffs"] = [by_cid[k][cid]["segments"] if cid else None for k, cid in enumerate(ch["cids"])]
        ch["summaries"] = [by_cid[k][cid]["summary"] if cid else "" for k, cid in enumerate(ch["cids"])]
        # 정렬 기준: 가장 최근 버전에서의 위치 비율
        for v in range(len(docs) - 1, -1, -1):
            if ch["idx"][v] is not None:
                ch["_order"] = (ch["idx"][v] / total_blocks[v], v)
                break
        changed.append(ch)
    changed.sort(key=lambda c: c["_order"])
    for c in changed:
        c.pop("_order", None)

    counts: Dict[str, int] = {}
    for c in changed:
        counts[c["kind"]] = counts.get(c["kind"], 0) + 1
    counts["total"] = len(changed)
    return {"versions": versions, "steps": steps, "chains": changed, "counts": counts,
            "kind_labels": CHAIN_LABELS}


def _link_chains(comps: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    chains: List[Dict[str, Any]] = []
    by_b: Dict[int, Dict[str, Any]] = {}
    for k, comp in enumerate(comps):
        new_by_b: Dict[int, Dict[str, Any]] = {}
        for row in comp["rows"]:
            c = by_b.get(row["ai"]) if (k > 0 and row["ai"] is not None) else None
            if c is None:
                c = {"location": row["location"], "idx": [None] * k, "texts": [None] * k,
                     "steps": [""] * k, "cids": [None] * k}
                c["idx"].append(row["ai"])
                c["texts"].append(row["a"])
                chains.append(c)
            c["idx"].append(row["bi"])
            c["texts"].append(row["b"])
            c["steps"].append(row["status"])
            c["cids"].append(row["cid"])
            if row["b"] is not None:
                c["location"] = row["location"]
            if row["bi"] is not None:
                new_by_b[row["bi"]] = c
        by_b = new_by_b
    # 중간에 끊긴 줄은 끝까지 None 으로 채운다
    for c in chains:
        while len(c["texts"]) < n:
            c["idx"].append(None)
            c["texts"].append(None)
        while len(c["steps"]) < n - 1:
            c["steps"].append("")
            c["cids"].append(None)
    return chains


def _classify(ch: Dict[str, Any]) -> str:
    texts: List[Optional[str]] = ch["texts"]
    first, last = texts[0], texts[-1]
    present = [t for t in texts if t is not None]
    if first is None and last is None:
        return "flip"
    if first is None:
        return "added"
    if last is None:
        return "deleted"
    if all(s in ("same", "format", "") for s in ch["steps"]):
        return "format"
    if first == last and any(t != first for t in present):
        return "reverted"
    return "changed"
