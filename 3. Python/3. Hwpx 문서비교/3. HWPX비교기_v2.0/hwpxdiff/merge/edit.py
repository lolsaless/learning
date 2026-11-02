"""직접 고치기 (v2.0) — 문단·표 칸의 글자를 고쳐 새 HWPX 를 만든다. 원본 서식을 그대로 이어받는다.

원칙
  · 바뀌지 않은 글자는 원래 run(글자모양 번호)을 그대로 둔다.
  · 새로 넣은 글자는 바로 앞 글자의 글자모양을 이어받는다 (맨 앞이면 뒤 글자). 한글에서 글자를 칠 때와 같다.
  · 원하면 새 글자를 표시색(예: 빨강)으로 — 원래 글자모양을 복사해 색만 바꾼 글자모양을 header 끝에 추가.
  · 글자가 바뀐 문단만 다시 만들고, 그 문단의 줄 배치 정보(hp:linesegarray)는 빼서 한글이 다시 계산하게 한다.
  · 구역 설정·필드·컨트롤만 든 run 은 '고정 run(anchor)'으로 제자리에 그대로 두고 글자만 고친다.
  · 표·글상자(안에 문단을 품은 것)나 글자와 특수 요소가 한 run 에 섞인 문단은 고치지 않는다 (한글에서 고치도록 안내).

    data, report = edit_document(doc, {블록 순번: 새 글자, ...}, mark_color="#FF0000" | None)
표 칸에서 줄바꿈(\\n)은 '문단 나누기', 본문 문단에서는 '줄 바꿈(Shift+Enter)'으로 들어간다.
"""
from __future__ import annotations

import io
import zipfile
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

from ..hwpx import load_document
from ..hwpx.model import Document
from ..hwpx.package import local
from ..hwpx.xmlspan import parse_with_spans
from .engine import NESTED_P, DocParts, MergeError, _splice, _touch_meta, write_package
from .resources import HeaderMerger

SIMPLE = {"tab": "\t", "lineBreak": "\n", "fwSpace": " ", "nbSpace": " ", "hyphen": "-"}
Item = Tuple[str, str, str, bytes]      # (종류 'c'|'el'|'para'|'anchor', 글자, 글자모양 번호, 원래 요소 bytes)


class EditError(MergeError):
    pass


def _items_of_unit(frag: bytes) -> Tuple[List[Item], List[bytes], List[bytes]]:
    """문단(들) 조각 → 글자 항목 목록, 문단별 시작 태그, 문단별 원문."""
    root, spans = parse_with_spans(b"<w>" + frag + b"</w>")
    off = 3
    items: List[Item] = []
    starts: List[bytes] = []
    originals: List[bytes] = []
    paras = [p for p in root if local(p.tag) == "p"]
    if not paras:
        raise EditError("고칠 문단을 찾지 못했습니다")
    for k, p in enumerate(paras):
        s, e = spans[id(p)]
        raw = frag[s - off:e - off]
        if len(NESTED_P.findall(raw)) > 1:
            raise EditError("표·글상자를 품은 문단은 여기서 고칠 수 없습니다 (한글에서 고쳐 주세요)")
        starts.append(raw[:raw.index(b">") + 1])
        originals.append(raw)
        if k:
            items.append(("para", "\n", items[-1][2] if items else "0", b""))
        for run in p:
            name = local(run.tag)
            if name == "linesegarray":
                continue
            if name != "run":
                raise EditError(f"특수 요소({name})가 든 문단은 여기서 고칠 수 없습니다")
            cid = run.get("charPrIDRef", "0")
            kinds = {local(c.tag) for c in run}
            if kinds and "t" not in kinds:          # 구역 설정·필드·컨트롤만 든 run → 제자리 고정
                rs, re_ = spans[id(run)]
                items.append(("anchor", "", cid, frag[rs - off:re_ - off]))
                continue
            for t in run:
                if local(t.tag) != "t":
                    # 글자와 섞인 필드·컨트롤 → 같은 글자모양의 별도 run 으로 떼어 제자리 고정
                    ts, te = spans[id(t)]
                    items.append(("anchor", "", cid, f'<hp:run charPrIDRef="{cid}">'.encode()
                                  + frag[ts - off:te - off] + b"</hp:run>"))
                    continue
                for ch in t.text or "":
                    items.append(("c", ch, cid, b""))
                for el in t:
                    nm = local(el.tag)
                    if nm not in SIMPLE:
                        raise EditError(f"특수 요소({nm})가 든 문단은 여기서 고칠 수 없습니다")
                    es, ee = spans[id(el)]
                    items.append(("el", SIMPLE[nm], cid, frag[es - off:ee - off]))
                    for ch in el.tail or "":
                        items.append(("c", ch, cid, b""))
            if not len(run) and not items:
                items.append(("empty", "", cid, b""))
    return items, starts, originals


def _rebuild(items: List[Item], new_text: str, is_cell: bool, starts: List[bytes], originals: List[bytes],
             color_cid) -> bytes:
    olds = [it for it in items if it[0] not in ("empty", "anchor")]
    # 고정 run 은 '바로 뒤 글자' 앞에 붙여 두었다가 그 글자 자리에서 다시 내보낸다
    anchors_before: Dict[int, List[Item]] = {}
    n = 0
    for it in items:
        if it[0] == "anchor":
            anchors_before.setdefault(n, []).append(it)
        elif it[0] != "empty":
            n += 1
    old_text = "".join(it[1] for it in olds)
    default_cid = next((it[2] for it in items if it[0] != "anchor"), items[0][2] if items else "0")
    sm = SequenceMatcher(None, old_text, new_text, autojunk=False)
    out: List[Item] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        for i in range(i1, i2):
            out.extend(anchors_before.get(i, []))
            if op == "equal":
                out.append(olds[i])
        if j2 > j1 and op != "equal":
            prev = next((x[2] for x in reversed(out) if x[0] not in ("anchor", "para")), None) \
                or (olds[i1][2] if i1 < len(olds) else default_cid)
            cid = color_cid(prev)
            for ch in new_text[j1:j2]:
                if ch == "\n":
                    out.append(("para", "\n", cid, b"") if is_cell else ("el", "\n", cid, b"<hp:lineBreak/>"))
                else:
                    out.append(("c", ch, cid, b""))
    out.extend(anchors_before.get(len(olds), []))
    # 문단으로 나누기
    paras: List[List[Item]] = [[]]
    for it in out:
        if it[0] == "para":
            paras.append([])
        else:
            paras[-1].append(it)
    old_paras: List[List[Item]] = [[]]
    for it in [x for x in items if x[0] != "empty"]:
        if it[0] == "para":
            old_paras.append([])
        else:
            old_paras[-1].append(it)
    chunks = []
    for k, its in enumerate(paras):
        if k < len(old_paras) and its == old_paras[k] and k < len(originals):
            chunks.append(originals[k])          # 안 바뀐 문단은 원문 그대로
            continue
        start = starts[min(k, len(starts) - 1)]
        chunks.append(start + _runs(its, default_cid) + b"</hp:p>")
    return b"".join(chunks)


def _runs(its: List[Item], default_cid: str) -> bytes:
    if not [x for x in its if x[0] != "anchor"]:
        its = its + [("c", "", default_cid, b"")] if not its else its
        if all(x[0] == "anchor" for x in its):
            return b"".join(x[3] for x in its) + f'<hp:run charPrIDRef="{default_cid}"/>'.encode()
    out, cur, buf = [], None, []

    def flush():
        if cur is not None:
            out.append(f'<hp:run charPrIDRef="{cur}"><hp:t>'.encode() + b"".join(buf) + b"</hp:t></hp:run>")

    for kind, ch, cid, raw in its:
        if kind == "anchor":
            flush()
            out.append(raw)
            cur, buf = None, []
            continue
        if cid != cur:
            flush()
            cur, buf = cid, []
        buf.append(raw if kind == "el" else escape(ch).encode())
    flush()
    return b"".join(out)


def edit_document(doc: Document, edits: Dict[int, str], mark_color: Optional[str] = None,
                  name: Optional[str] = None) -> Tuple[bytes, Dict]:
    if not edits:
        raise EditError("고친 곳이 없습니다")
    parts = DocParts(doc)
    hm = HeaderMerger(parts.header)
    cache: Dict[str, str] = {}

    def color_cid(cid: str) -> str:
        if not mark_color:
            return cid
        if cid not in cache:
            cache[cid] = hm.derive_charpr(cid, {"textColor": mark_color})
        return cache[cid]

    splices: Dict[int, list] = {}
    done = []
    for seq, (bi, text) in enumerate(sorted(edits.items())):
        blk = doc.blocks[int(bi)]
        if not blk.span:
            raise EditError(f"{blk.location}: 위치 정보가 없어 고칠 수 없습니다")
        if text == blk.text:
            continue
        frag = parts.bytes_at(blk.span)
        try:
            items, starts, originals = _items_of_unit(frag)
        except EditError as e:
            raise EditError(f"{blk.location}: {e}")
        rebuilt = _rebuild(items, text.replace("\r\n", "\n"), blk.kind == "cell", starts, originals, color_cid)
        splices.setdefault(blk.span[0], []).append((blk.span[1], blk.span[2], rebuilt, seq))
        done.append({"index": blk.index, "location": blk.location, "old": blk.text, "new": text})
    if not done:
        raise EditError("바뀐 글자가 없습니다")
    files = {"Contents/header.xml": hm.build(), "Contents/content.hpf": _touch_meta(parts.zip.read("Contents/content.hpf"), "")}
    for i, n in enumerate(doc.section_names):
        files[n] = _splice(parts.sections[i], splices.get(i, []))
    data = write_package(parts.zip, files)
    # 검사: 다시 읽어 고친 글자가 그대로 들어갔는지
    new_doc = load_document(data, name=name or doc.name)
    texts = {b.text for b in new_doc.blocks}
    bad = [d["location"] for d in done if d["new"].strip() and d["new"].replace("\r\n", "\n") not in texts]
    return data, {"edited": done, "check_failed": bad, "header_added": hm.added}
