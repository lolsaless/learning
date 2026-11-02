"""병합 엔진 (v2.0) — 원본(base) 하나에 여러 버전의 변경을 골라 넣어 깨짐 없는 HWPX 를 만든다.

원리 (첨부 문서로 한글에서 정상 열림을 확인한 방식):
  · 원본 XML 은 그대로 두고, 바뀐 '문단(hp:p)'·'표 칸 안쪽' 바이트만 해당 버전의 바이트로 갈아 끼운다.
  · 가져온 조각의 모양 번호는 resources.HeaderMerger 로 원본 번호로 바꾸고, 없는 모양은 원본 목록 끝에 덧붙인다.
  · 표를 품은 문단은 통째로 바꾸지 않고 '자기 글자 run' 만 바꾼다 (표는 그대로 → 표 안 변경과 충돌하지 않음).

흐름
    plan = plan_merge(base, [v1, v2, ...], compare_fn)      # 변경 항목(item)·선택지(option)·충돌 계산
    data, report = apply_merge(base, docs, plan, choices)  # 고른 것만 적용 → 새 HWPX bytes

항목(item) = 원본의 한 자리(문단/칸) 또는 새로 끼울 자리. 선택지(option) = 그 자리에 대한 버전별 변경.
같은 자리를 두 버전이 다르게 고치면 '충돌' → 사용자가 고른다 (기본: 원본 유지).
"""
from __future__ import annotations

import io
import re
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ..hwpx import load_document
from ..hwpx.model import Block, Document
from ..hwpx.package import local
from ..hwpx.xmlspan import parse_with_spans
from .resources import HeaderMerger

CompareFn = Callable[[Document, Document], Dict[str, Any]]
NESTED_P = re.compile(rb"<hp:p[\s>]")
TEXT_CHILDREN = {"t"}


class MergeError(Exception):
    pass


# ════════════════════════════════════════════════════════════════
# 문서 원문 접근 + 배치 트리 색인
# ════════════════════════════════════════════════════════════════
class DocParts:
    def __init__(self, doc: Document):
        self.doc = doc
        z = zipfile.ZipFile(io.BytesIO(doc.raw))
        self.zip = z
        self.sections = [z.read(n) for n in doc.section_names]
        self.header = z.read("Contents/header.xml")
        self.top_of_block: Dict[int, Dict[str, Any]] = {}    # 블록 → 그 블록을 품은 본문 최상위 문단 노드
        self.cells: Dict[Tuple[int, int, int], Dict[str, Any]] = {}   # (표 번호, 행, 열) → 칸 노드
        self.block_table: Dict[int, int] = {}
        self.top_nodes: List[Dict[str, Any]] = [n for n in doc.layout if n.get("t") == "p"]
        for top in self.top_nodes:
            self._walk(top, top)

    def _walk(self, node, top) -> None:
        t = node.get("t")
        if t == "p":
            if node.get("b") is not None:
                self.top_of_block[node["b"]] = top
            for it in node.get("items", []):
                self._walk(it, top)
        elif t == "tbl":
            for row in node["rows"]:
                for c in row:
                    self.cells[(node["no"], c.get("r"), c.get("c"))] = c
                    if c.get("b") is not None:
                        self.top_of_block[c["b"]] = top
                        self.block_table[c["b"]] = node["no"]
                    for it in c.get("items", []):
                        self._walk(it, top)
        elif t == "sub":
            for p in node["paras"]:
                self._walk(p, top)

    def bytes_at(self, span: Sequence[int]) -> bytes:
        return self.sections[span[0]][span[1]:span[2]]

    def blocks_in_top(self, top) -> List[int]:
        return [b for b, t in self.top_of_block.items() if t is top]


def is_leaf(fragment: bytes) -> bool:
    """안에 다른 문단(표·글상자 등)을 품지 않은 문단인가."""
    return len(NESTED_P.findall(fragment)) <= 1


def _run_groups(p_bytes: bytes):
    """문단 안 run 들을 '글자 run 묶음(gap)'과 '고정 run(anchor: 표·필드·도형 등)'으로 나눈다.
    돌려줌: (gaps[(시작,끝)], anchors[원문 bytes])  — gap 은 anchor 수 + 1 개."""
    root, spans = parse_with_spans(p_bytes)
    runs = [c for c in root if local(c.tag) == "run"]
    start_tag_end = p_bytes.index(b">") + 1
    gaps: List[Tuple[int, int]] = []
    anchors: List[bytes] = []
    cur_s: Optional[int] = None
    cur_e: Optional[int] = None
    last_end = spans[id(runs[0])][0] if runs else start_tag_end
    for r in runs:
        s, e = spans[id(r)]
        textual = all(local(c.tag) in TEXT_CHILDREN for c in r)
        if textual:
            cur_s = s if cur_s is None else cur_s
            cur_e = e
        else:
            gaps.append((cur_s, cur_e) if cur_s is not None else (s, s))
            anchors.append(p_bytes[s:e])
            cur_s = cur_e = None
        last_end = e
    gaps.append((cur_s, cur_e) if cur_s is not None else (last_end, last_end))
    return gaps, anchors


def own_run_splices(base_p: bytes, base_off: int, src_p: Optional[bytes]) -> Optional[List[Tuple[int, int, bytes]]]:
    """표를 품은 문단: 고정 run 은 그대로, 글자 run 묶음만 출처 것으로. 구조가 다르면 None."""
    bg, ba = _run_groups(base_p)
    if src_p is None:                        # 글자만 지우기
        return [(base_off + s, base_off + e, b"") for s, e in bg if e > s]
    sg, sa = _run_groups(src_p)
    if len(ba) != len(sa):
        return None
    out = []
    for (bs, be), (ss, se) in zip(bg, sg):
        rep = src_p[ss:se]
        if base_p[bs:be] != rep:
            out.append((base_off + bs, base_off + be, rep))
    return out


# ════════════════════════════════════════════════════════════════
# 계획: 변경 항목·선택지·충돌
# ════════════════════════════════════════════════════════════════
@dataclass
class Option:
    op_id: str
    version: str              # 문서 id
    vname: str
    type: str                 # modified | added | deleted | format
    label: str
    summary: str
    new_text: str
    segments: List[Dict[str, str]]
    mode: str                 # element | cell | own | delete | insert
    base_span: Optional[List[int]] = None
    src_span: Optional[List[int]] = None
    insert_pos: Optional[List[int]] = None
    unsupported: str = ""
    includes: List[str] = field(default_factory=list)     # 이 선택지에 함께 들어가는 안쪽 변경(표 칸 안의 표 등)


@dataclass
class Item:
    key: str
    location: str
    context: str
    base_index: Optional[int]          # 원본 블록 (끼우기는 None)
    ghost_before: Optional[int]        # 끼우기 항목: 원본 화면에서 이 블록 앞에 표시 (None=문서 끝)
    base_text: str
    options: List[Option] = field(default_factory=list)
    conflict: bool = False
    same: bool = False
    default: str = "base"              # 'base' 또는 선택지 op_id


def plan_merge(base: Document, versions: Sequence[Document], compare: CompareFn) -> Dict[str, Any]:
    bp = DocParts(base)
    items: Dict[str, Item] = {}
    order: List[str] = []
    stats = Counter()
    for vno, v in enumerate(versions, 1):
        vp = DocParts(v)
        res = compare(base, v)
        changes = {c["id"]: c for c in res["changes"]}
        tmap, trev = _table_maps(res, bp, vp)
        opts = _options_for_version(base, v, vno, bp, vp, res, changes, tmap, trev)
        _absorb_nested(opts)
        for key, item_info, opt in opts:
            if key not in items:
                items[key] = Item(key=key, **item_info)
                order.append(key)
            items[key].options.append(opt)
            stats["options"] += 1
    for it in items.values():
        usable = [o for o in it.options if not o.unsupported]
        texts = {(o.type, o.new_text) for o in usable}
        it.same = len(usable) > 1 and len(texts) == 1
        it.conflict = len(usable) > 1 and len(texts) > 1
        it.default = usable[0].op_id if usable and not it.conflict else "base"
    out_items = [asdict(items[k]) for k in sorted(order, key=lambda k: _sort_key(items[k], base))]
    return {
        "base": base.id, "versions": [{"id": v.id, "name": v.name, "no": i + 1} for i, v in enumerate(versions)],
        "items": out_items,
        "counts": {"items": len(out_items), "conflicts": sum(1 for i in out_items if i["conflict"]),
                   "same": sum(1 for i in out_items if i["same"]),
                   "unsupported": sum(1 for i in out_items for o in i["options"] if o["unsupported"]),
                   "options": stats["options"]},
    }


def _sort_key(it: Item, base: Document):
    if it.base_index is not None:
        return (it.base_index, 0)
    if it.ghost_before is not None:
        return (it.ghost_before, -1)
    return (len(base.blocks) + 1, 0)


def _table_maps(res, bp: DocParts, vp: DocParts):
    votes = Counter()
    for r in res["rows"]:
        if r["ai"] is not None and r["bi"] is not None:
            ta, tb = bp.block_table.get(r["ai"]), vp.block_table.get(r["bi"])
            if ta and tb:
                votes[(ta, tb)] += 1
    tmap, trev = {}, {}
    for (ta, tb), _ in votes.most_common():
        if ta not in tmap and tb not in trev:
            tmap[ta], trev[tb] = tb, ta
    return tmap, trev


def _check_src(frag: bytes) -> str:
    if b"binaryItemIDRef" in frag:
        return "그림이 들어 있는 변경은 자동 적용할 수 없습니다 (한글에서 직접 넣어 주세요)"
    return ""


def _options_for_version(base, v, vno, bp: DocParts, vp: DocParts, res, changes, tmap, trev):
    out = []
    rows = res["rows"]
    inserted_tops = set()
    last_ai = None
    for k, r in enumerate(rows):
        c = changes.get(r["cid"]) if r["cid"] else None
        if c is None:
            if r["ai"] is not None:
                last_ai = r["ai"]
            continue
        ai, bi = r["ai"], r["bi"]
        ba = base.blocks[ai] if ai is not None else None
        bb = v.blocks[bi] if bi is not None else None
        opt = Option(op_id=f"{v.id}:{c['id']}", version=v.id, vname=v.name, type=c["type"], label=c["label"],
                     summary=c["summary"], new_text=bb.text if bb else "", segments=c["segments"], mode="")
        info = {"location": c["location"], "context": c["context"], "base_index": ai, "ghost_before": None,
                "base_text": ba.text if ba else ""}
        key = None
        if ba is not None and bb is not None:                       # 수정·서식
            key = _modify(opt, ba, bb, bp, vp)
        elif ba is not None:                                        # 삭제
            key = _delete(opt, ba, bp, vp, tmap)
        else:                                                       # 추가
            top_v = vp.top_of_block.get(bi)
            matched_inside = top_v is not None and any(
                rr["bi"] in vp.blocks_in_top(top_v) and rr["ai"] is not None for rr in rows)
            if bb.kind == "cell" and matched_inside:
                key = _fill_cell(opt, bb, bp, vp, trev, info)
            elif top_v is not None and not matched_inside:
                if id(top_v) in inserted_tops:
                    continue                                        # 이미 문단째 끼워 넣음
                inserted_tops.add(id(top_v))
                key = _insert_top(opt, top_v, last_ai, bp, vp, info, base)
            elif bb.kind == "para" and matched_inside:
                key = _own_added(opt, top_v, bp, vp, rows)
            else:
                opt.unsupported = "이 위치(머리말·각주 등)에 새로 생긴 글은 자동 적용할 수 없습니다"
                key = f"ins:{v.id}:{bi}"
        if ai is not None:
            last_ai = ai
        if opt.src_span and not opt.unsupported:
            opt.unsupported = _check_src(vp.bytes_at(opt.src_span))
        if key:
            if key.startswith("ins:") and info["base_index"] is None and info.get("ghost_before") is None:
                info["ghost_before"] = _ghost_anchor(bp, last_ai)
            out.append((key, info, opt))
    return out


def _span_key(span) -> str:
    return f"s{span[0]}:{span[1]}-{span[2]}"


def _modify(opt: Option, ba: Block, bb: Block, bp: DocParts, vp: DocParts) -> Optional[str]:
    if ba.kind != bb.kind or not ba.span or not bb.span:
        opt.unsupported = "문단 ↔ 표 칸처럼 종류가 바뀐 변경은 자동 적용할 수 없습니다"
        return f"blk:{ba.index}"
    if ba.kind == "cell":
        opt.mode, opt.base_span, opt.src_span = "cell", ba.span, bb.span
        return _span_key(ba.span)
    fa, fb = bp.bytes_at(ba.span), vp.bytes_at(bb.span)
    if is_leaf(fa) and is_leaf(fb):
        opt.mode, opt.base_span, opt.src_span = "element", ba.span, bb.span
    elif ba.kind == "para":
        opt.mode, opt.base_span, opt.src_span = "own", ba.span, bb.span
    else:
        opt.unsupported = "표·글상자를 품은 머리말·각주 문단은 자동 적용할 수 없습니다"
    return _span_key(ba.span)


def _delete(opt: Option, ba: Block, bp: DocParts, vp: DocParts, tmap) -> str:
    key = _span_key(ba.span) if ba.span else f"blk:{ba.index}"
    if ba.kind == "cell":
        tv = tmap.get(bp.block_table.get(ba.index))
        cell_v = vp.cells.get((tv, ba.row, ba.col)) if tv else None
        if cell_v and cell_v.get("sp"):
            opt.mode, opt.base_span, opt.src_span = "cell", ba.span, cell_v["sp"]
        else:
            opt.unsupported = "표 구조가 달라 비워진 칸을 찾지 못했습니다"
    elif ba.kind == "para":
        frag = bp.bytes_at(ba.span)
        opt.mode, opt.base_span = ("delete" if is_leaf(frag) else "own"), ba.span
    else:
        opt.unsupported = "머리말·각주 문단 삭제는 자동 적용할 수 없습니다"
    return key


def _fill_cell(opt: Option, bb: Block, bp: DocParts, vp: DocParts, trev, info) -> str:
    ta = trev.get(vp.block_table.get(bb.index))
    cell_b = bp.cells.get((ta, bb.row, bb.col)) if ta else None
    if not cell_b or not cell_b.get("sp"):
        opt.unsupported = "표 구조가 달라 채울 칸을 원본에서 찾지 못했습니다"
        return f"ins:{opt.version}:{bb.index}"
    opt.mode, opt.base_span, opt.src_span = "cell", cell_b["sp"], bb.span
    info["base_index"] = None
    info["ghost_before"] = _first_block_after(bp, cell_b["sp"])
    return _span_key(cell_b["sp"])


def _own_added(opt: Option, top_v, bp: DocParts, vp: DocParts, rows) -> str:
    """표를 품은 문단에 글자가 새로 생김 → 원본의 같은 문단(안의 표가 짝지어진 것)의 글자 run 만 바꿈."""
    inner = vp.blocks_in_top(top_v)
    ai = next((r["ai"] for r in rows if r["bi"] in inner and r["ai"] is not None), None)
    top_b = bp.top_of_block.get(ai) if ai is not None else None
    if not top_b or not top_b.get("sp") or not top_v.get("sp"):
        opt.unsupported = "원본에서 같은 문단을 찾지 못했습니다"
        return f"ins:{opt.version}:{id(top_v)}"
    opt.mode, opt.base_span, opt.src_span = "own", top_b["sp"], top_v["sp"]
    return _span_key(top_b["sp"])


def _insert_top(opt: Option, top_v, last_ai, bp: DocParts, vp: DocParts, info, base: Document) -> str:
    if not top_v.get("sp"):
        opt.unsupported = "위치 정보를 찾지 못했습니다"
        return f"ins:{opt.version}:{id(top_v)}"
    anchor_top = bp.top_of_block.get(last_ai) if last_ai is not None else None
    anchor = anchor_top or (bp.top_nodes[0] if bp.top_nodes else None)
    if not anchor or not anchor.get("sp"):
        opt.unsupported = "끼울 자리를 찾지 못했습니다"
        return f"ins:{opt.version}:{id(top_v)}"
    sp = anchor["sp"]
    opt.mode, opt.src_span, opt.insert_pos = "insert", top_v["sp"], [sp[0], sp[2]]
    opt.new_text = "\n".join(vp.doc.blocks[b].text for b in sorted(vp.blocks_in_top(top_v)))
    info["ghost_before"] = _first_block_after(bp, [sp[0], sp[2], sp[2]])
    return f"ins:{opt.version}:{sp[0]}:{sp[2]}:{top_v['sp'][1]}"


def _first_block_after(bp: DocParts, span) -> Optional[int]:
    for b in bp.doc.blocks:
        if b.span and (b.span[0], b.span[1]) >= (span[0], span[2]):
            return b.index
    return None


def _ghost_anchor(bp: DocParts, last_ai) -> Optional[int]:
    if last_ai is None:
        return 0 if bp.doc.blocks else None
    top = bp.top_of_block.get(last_ai)
    return _first_block_after(bp, top["sp"]) if top and top.get("sp") else None


def _absorb_nested(opts) -> None:
    """같은 버전 안에서, 바깥 칸 교체가 안쪽 변경을 이미 포함하면 안쪽은 따로 적용하지 않는다."""
    outer = [(o.base_span, o) for _, _, o in opts if o.mode == "cell" and o.base_span]
    keep = []
    for key, info, o in opts:
        host = None
        if o.base_span and o.mode in ("cell", "element", "delete", "own"):
            for sp, h in outer:
                if h is not o and sp[0] == o.base_span[0] and sp[1] <= o.base_span[1] and o.base_span[2] <= sp[2] \
                        and (sp[1], sp[2]) != (o.base_span[1], o.base_span[2]):
                    host = h
                    break
        if host:
            host.includes.append(o.op_id)
        else:
            keep.append((key, info, o))
    opts[:] = keep


# ════════════════════════════════════════════════════════════════
# 적용: 고른 선택지 → 새 HWPX
# ════════════════════════════════════════════════════════════════
def apply_merge(base: Document, docs: Dict[str, Document], plan: Dict[str, Any], choices: Dict[str, Any],
                note: str = "") -> Tuple[bytes, Dict[str, Any]]:
    """choices: {item key: op_id | 'base' | [op_id, ...](끼우기 여러 개)} — 없으면 항목 기본값."""
    bp = DocParts(base)
    hm = HeaderMerger(bp.header)
    splices: Dict[int, List[Tuple[int, int, bytes, int]]] = defaultdict(list)   # 구역 → (시작, 끝, 바이트, 순서)
    applied, skipped = [], []
    seq = 0
    parts_cache: Dict[str, DocParts] = {}
    for it in plan["items"]:
        choice = choices.get(it["key"], it["default"])
        chosen = choice if isinstance(choice, list) else [choice]
        for o in it["options"]:
            if o["op_id"] not in chosen:
                continue
            if o["unsupported"]:
                skipped.append({"op_id": o["op_id"], "reason": o["unsupported"], "location": it["location"]})
                continue
            vp = parts_cache.setdefault(o["version"], DocParts(docs[o["version"]]))
            src = hm.source(vp.header)
            seq += 1
            for sec, s, e, rep in _op_splices(o, bp, vp, hm, src):
                splices[sec].append((s, e, rep, seq))
            applied.append({"op_id": o["op_id"], "location": it["location"], "summary": o["summary"],
                            "version": o["vname"]})
    new_sections = []
    for i, sec in enumerate(bp.sections):
        new_sections.append(_splice(sec, splices.get(i, [])))
    files = {"Contents/header.xml": hm.build()}
    files.update({n: d for n, d in zip(base.section_names, new_sections)})
    files["Contents/content.hpf"] = _touch_meta(bp.zip.read("Contents/content.hpf"), note)
    data = write_package(bp.zip, files)
    # 결과 검사: 다시 읽히는지. (미리보기 Preview/* 는 일부러 그대로 둔다 — 한글로 열어 저장하면 새로 만들어짐)
    doc = load_document(data, name="병합본.hwpx")
    return data, {"applied": applied, "skipped": skipped, "header_added": hm.added,
                  "stats": doc.stats, "warnings": doc.warnings}


def _op_splices(o, bp: DocParts, vp: DocParts, hm: HeaderMerger, src):
    mode = o["mode"]
    if mode in ("element", "cell"):
        sp = o["base_span"]
        yield sp[0], sp[1], sp[2], hm.remap(vp.bytes_at(o["src_span"]), src)
    elif mode == "delete":
        sp = o["base_span"]
        yield sp[0], sp[1], sp[2], b""
    elif mode == "insert":
        pos = o["insert_pos"]
        yield pos[0], pos[1], pos[1], hm.remap(vp.bytes_at(o["src_span"]), src)
    elif mode == "own":
        sp = o["base_span"]
        src_p = vp.bytes_at(o["src_span"]) if o["src_span"] else None
        pieces = own_run_splices(bp.bytes_at(sp), sp[1], src_p)
        if pieces is None:
            raise MergeError(f"{o['vname']}: 표를 품은 문단의 구조가 달라 글자만 바꿀 수 없습니다")
        for s, e, rep in pieces:
            yield sp[0], s, e, hm.remap(rep, src)


def _splice(data: bytes, edits: List[Tuple[int, int, bytes, int]]) -> bytes:
    if not edits:
        return data
    edits = sorted(edits, key=lambda x: (x[0], x[1], x[3]))
    # 겹침 검사 (같은 위치 끼우기는 순서대로 이어 붙임)
    merged: List[List[Any]] = []
    for s, e, rep, q in edits:
        if merged and s == e == merged[-1][0] == merged[-1][1]:
            merged[-1][2] += rep
            continue
        if merged and s < merged[-1][1]:
            raise MergeError("같은 자리를 두 변경이 동시에 바꾸려 합니다 (충돌 항목을 하나만 고르세요)")
        merged.append([s, e, rep])
    out, pos = [], 0
    for s, e, rep in merged:
        out.append(data[pos:s])
        out.append(rep)
        pos = e
    out.append(data[pos:])
    return b"".join(out)


def _touch_meta(hpf: bytes, note: str) -> bytes:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out = re.sub(rb'(name="ModifiedDate" content="text">)[^<]*', lambda m: m.group(1) + now.encode(), hpf)
    return out


def preview_text(doc: Document, limit: int = 1000) -> bytes:
    text = "\r\n".join(b.text for b in doc.blocks if b.kind in ("para", "cell"))[:limit]
    return text.encode("utf-8")


def write_package(src_zip: zipfile.ZipFile, replace: Dict[str, bytes]) -> bytes:
    """원본 zip 의 파일 순서·압축 방식을 그대로 두고 일부 파일만 바꿔 새 zip. mimetype 은 맨 앞·무압축."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zo:
        for info in src_zip.infolist():
            data = replace.get(info.filename, src_zip.read(info.filename))
            ni = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            ni.external_attr = info.external_attr
            ni.compress_type = zipfile.ZIP_STORED if info.filename == "mimetype" else info.compress_type
            zo.writestr(ni, data)
    return buf.getvalue()
