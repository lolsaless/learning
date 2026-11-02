"""버전 관계(계보) 분석 (v2.0) — 원본·최종본 추정, '누가 누구를 고쳤는지' 나무 만들기.

근거 (첨부 문서에서 확인한 사실)
  ① 글자모양 목록: 한글은 안 쓰는 글자모양도 지우지 않고, 고칠 때 새 글자모양을 '목록 끝'에 붙인다.
     → 문서 X 의 목록이 Y 목록의 앞부분과 같으면(접두) X 는 Y 의 조상일 수 있다.
     → 두 문서가 같은 번호에 서로 다른 새 글자모양을 붙였으면 서로 다른 갈래(형제)다.
  ② 문서 만든 날(CreatedDate)이 같으면 같은 문서에서 나온 가족이다.
  ③ 마지막 수정일(ModifiedDate): 부모는 자식보다 먼저 저장됐다.
  ④ 내용 차이: 부모 후보 중 내용이 가장 가까운 것.
사용자가 지정한 관계·역할(프로젝트 기록)이 있으면 추정보다 우선한다.
"""
from __future__ import annotations

import io
import zipfile
from typing import Any, Callable, Dict, List, Optional, Sequence

from ..hwpx.model import Document
from ..merge.resources import HeaderInfo, canonical

CompareFn = Callable[[Document, Document], Dict[str, Any]]


def style_signature(doc: Document) -> List[Any]:
    """글자모양 정의를 번호 순서대로 (견주기용 값)."""
    try:
        header = zipfile.ZipFile(io.BytesIO(doc.raw)).read("Contents/header.xml")
    except KeyError:
        return []
    items = HeaderInfo(header).items["charPr"]
    return [canonical(items[k]) for k in sorted(items, key=lambda x: int(x) if x.isdigit() else 0)]


def _is_prefix(a: List[Any], b: List[Any]) -> bool:
    return len(a) <= len(b) and b[:len(a)] == a


def analyze(docs: Sequence[Document], compare: CompareFn,
            fixed_parents: Optional[Dict[str, List[str]]] = None,
            roles: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """돌려줌: {nodes, edges, original, finals, latest, linear, notes}."""
    fixed_parents = fixed_parents or {}
    roles = roles or {}
    docs = list(docs)
    ids = [d.id for d in docs]
    by_id = {d.id: d for d in docs}
    sig = {d.id: style_signature(d) for d in docs}
    dist: Dict[tuple, int] = {}

    def distance(a: str, b: str) -> int:
        key = tuple(sorted((a, b)))
        if key not in dist:
            dist[key] = compare(by_id[key[0]], by_id[key[1]])["counts"]["total"]
        return dist[key]

    # ── 원본 추정 ───────────────────────────────────
    scores: Dict[str, float] = {}
    reasons: Dict[str, List[str]] = {i: [] for i in ids}
    earliest = min((d.modified or "9999") for d in docs) if docs else ""
    totals = {d.id: sum(distance(d.id, o.id) for o in docs if o.id != d.id) for d in docs}
    min_total = min(totals.values()) if totals else 0
    unique_center = list(totals.values()).count(min_total) == 1
    for d in docs:
        s = 0.0
        others = [o for o in docs if o.id != d.id]
        if others and all(_is_prefix(sig[d.id], sig[o.id]) for o in others):
            s += 3
            reasons[d.id].append("글자모양 목록이 다른 모든 문서의 앞부분과 같음 (다른 문서들이 여기서 고쳐짐)")
        if (d.modified or "9999") == earliest:
            s += 2
            reasons[d.id].append("마지막 수정일이 가장 이름")
        if others and unique_center and totals[d.id] == min_total:
                s += 1
                reasons[d.id].append("다른 문서들과의 내용 차이 합이 가장 작음 (가운데에 있는 문서)")
        scores[d.id] = s
    original = next((i for i, r in roles.items() if r == "original" and i in by_id), None)
    original_by = "지정"
    if not original and docs:
        original = max(ids, key=lambda i: (scores[i], -_ts(by_id[i].modified)))
        original_by = "추정"

    # ── 부모 정하기 ─────────────────────────────────
    parents: Dict[str, List[str]] = {}
    basis: Dict[str, str] = {}
    ordered = sorted(docs, key=lambda d: (d.modified or "9999", d.name))
    for d in ordered:
        if d.id == original:
            parents[d.id] = []
            continue
        if d.id in fixed_parents and all(p in by_id for p in fixed_parents[d.id]):
            parents[d.id] = list(fixed_parents[d.id])
            basis[d.id] = "기록"
            continue
        earlier = [o for o in docs if o.id != d.id and (o.modified or "") <= (d.modified or "") and o.id != d.id]
        if original not in [o.id for o in earlier] and original != d.id:
            earlier.append(by_id[original])
        cands = [o for o in earlier if _is_prefix(sig[o.id], sig[d.id])]
        why = "글자모양 목록 이어짐 + 내용이 가장 가까움"
        if not cands:
            cands, why = earlier, "내용이 가장 가까움 (글자모양 근거 없음)"
        # 사이클 방지: 자기 자손은 부모가 될 수 없음
        cands = [o for o in cands if not _descends(o.id, d.id, parents)]
        if not cands:
            parents[d.id] = [original] if original != d.id else []
            basis[d.id] = "기본(원본)"
            continue
        best = min(cands, key=lambda o: (distance(o.id, d.id), -_ts(o.modified)))
        parents[d.id] = [best.id]
        basis[d.id] = why

    children: Dict[str, List[str]] = {i: [] for i in ids}
    for c, ps in parents.items():
        for p in ps:
            children.setdefault(p, []).append(c)
    leaves = [i for i in ids if not children.get(i)]
    latest = max(ids, key=lambda i: _ts(by_id[i].modified)) if ids else None
    final = next((i for i, r in roles.items() if r == "final" and i in by_id), None)
    final_by = "지정"
    if not final:
        final_by = "추정"
        final = leaves[0] if len(leaves) == 1 else None

    edges = []
    for c, ps in parents.items():
        for p in ps:
            res = compare(by_id[p], by_id[c])
            edges.append({"from": p, "to": c, "counts": res["counts"], "headline": res["headline"],
                          "basis": basis.get(c, ""), "fixed": basis.get(c) == "기록"})
    depth: Dict[str, int] = {}

    def dep(i, seen=()):
        if i in depth:
            return depth[i]
        ps = [p for p in parents.get(i, []) if p not in seen]
        depth[i] = 0 if not ps else 1 + max(dep(p, seen + (i,)) for p in ps)
        return depth[i]

    for i in ids:
        dep(i)
    nodes = []
    for d in docs:
        role = roles.get(d.id) or ("original" if d.id == original else "final" if d.id == final else "revision")
        nodes.append({"id": d.id, "name": d.name, "modified": d.modified, "created": d.meta.get("CreatedDate", ""),
                      "author": d.meta.get("lastsaveby", ""), "app": d.meta.get("application", ""),
                      "role": role, "role_by": "지정" if d.id in roles else "추정",
                      "depth": depth.get(d.id, 0), "leaf": d.id in leaves, "latest": d.id == latest,
                      "score": scores.get(d.id, 0), "reasons": reasons.get(d.id, []),
                      "styles": len(sig[d.id]), "parents": parents.get(d.id, []),
                      "children": children.get(d.id, [])})
    notes = []
    created = {d.meta.get("CreatedDate", "") for d in docs}
    if len(created) > 1:
        notes.append("문서를 만든 날짜가 서로 달라, 다른 문서가 섞여 있을 수 있습니다")
    linear = all(len(children.get(i, [])) <= 1 for i in ids)
    if not linear:
        notes.append("한 문서에서 여러 갈래로 고쳐졌습니다 → 저장 순서대로 비교하면 '되돌림'처럼 보일 수 있으니 [병합] 탭에서 원본 기준으로 보세요")
    if len(leaves) > 1 and not final:
        notes.append(f"끝 문서(최종본 후보)가 {len(leaves)}개입니다 → 병합해서 최종본을 만들 수 있습니다")
    return {"nodes": nodes, "edges": edges, "original": original, "original_by": original_by,
            "final": final, "final_by": final_by, "latest": latest, "leaves": leaves,
            "linear": linear, "notes": notes}


def _ts(s: Optional[str]) -> float:
    import calendar
    import time as _t
    try:
        return calendar.timegm(_t.strptime((s or "")[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return 0.0


def _descends(a: str, b: str, parents: Dict[str, List[str]]) -> bool:
    """a 가 b 의 자손인가."""
    stack, seen = [a], set()
    while stack:
        x = stack.pop()
        if x == b:
            return True
        if x in seen:
            continue
        seen.add(x)
        stack.extend(parents.get(x, []))
    return False
