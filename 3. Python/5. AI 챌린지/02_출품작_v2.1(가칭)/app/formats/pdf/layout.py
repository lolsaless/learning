# -*- coding: utf-8 -*-
"""[PDF ⑤] 배치 복원: 글자 조각 → 줄 → (칸으로 나뉜 줄이 이어지면) 표 / 나머지는 문단."""
import re

from app.common import numbers as N

MARK = re.compile(r"^\s*([□■○●◦·\-\*※▶◎]|[①-⑳]|\d{1,2}\s*[\.\)](?!\d)|[가-하]\s*\.|\(\d{1,2}\))")


def _ruled(vlines, xa, xb, y):
    """xa~xb 사이에 이 줄 높이를 지나는 세로 선(표 테두리)이 있는가."""
    return any(xa - 0.8 <= x <= xb + 0.8 and y0 - 2 <= y <= y1 + 2 for x, y0, y1 in vlines)


def lines_of(frags, vlines=None):
    """같은 높이(y)의 조각을 한 줄로 모으고, 줄 안에서 간격(또는 표 세로 선)으로 칸(segment)을 나눈다."""
    vlines = vlines or []
    out = []
    for f in sorted(frags, key=lambda f: (-round(f["y"], 1), f["x0"])):
        tol = max(1.5, f["size"] * 0.45)
        for ln in out[-4:]:
            if abs(ln["y"] - f["y"]) <= tol:
                ln["frags"].append(f)
                break
        else:
            out.append({"y": f["y"], "frags": [f]})
    out.sort(key=lambda l: -l["y"])
    for ln in out:
        fs = sorted(ln["frags"], key=lambda f: f["x0"])
        size = max(1.0, sum(f["size"] for f in fs) / len(fs))
        segs, cur = [], None
        for f in fs:
            if cur is None:
                cur = dict(f)
                continue
            gap = f["x0"] - cur["x1"]
            if gap > size * 1.2 or (vlines and gap > -0.5 and _ruled(vlines, cur["x1"], f["x0"], ln["y"])):
                segs.append(cur)
                cur = dict(f)
            else:
                sep = " " if gap > size * 0.22 and not cur["text"].endswith(" ") else ""
                cur["text"] += sep + f["text"]
                cur["x1"] = max(cur["x1"], f["x1"])
        if cur:
            segs.append(cur)
        for s in segs:
            s["text"] = re.sub(r"\s+", " ", s["text"]).strip()
        ln["segs"] = [s for s in segs if s["text"]]
        ln["size"] = size
    return [l for l in out if l["segs"]]


def _is_table_line(ln):
    return len(ln["segs"]) >= 2


def _columns(run):
    """줄들의 칸 x 범위를 겹침으로 묶어 열 경계를 만든다."""
    spans = sorted((s["x0"], s["x1"]) for ln in run for s in ln["segs"])
    cols = []
    for a, b in spans:
        if cols and a <= cols[-1][1] + 0.5:
            cols[-1][1] = max(cols[-1][1], b)
        else:
            cols.append([a, b])
    return cols


def _table(run):
    cols = _columns(run)
    if len(cols) < 2:
        return None
    cells = []
    for r, ln in enumerate(run):
        for s in ln["segs"]:
            mid = (s["x0"] + s["x1"]) / 2
            c = next((k for k, (a, b) in enumerate(cols) if a - 0.5 <= mid <= b + 0.5), None)
            if c is None:
                c = min(range(len(cols)), key=lambda k: abs((cols[k][0] + cols[k][1]) / 2 - mid))
            prev = next((x for x in cells if x["r"] == r and x["c"] == c), None)
            if prev:
                prev["text"] += " " + s["text"]
            else:
                cells.append({"r": r, "c": c, "rs": 1, "cs": 1, "text": s["text"]})
    return {"type": "table", "cells": cells, "nrow": len(run), "ncol": len(cols)}


def blocks_of(lines):
    blocks, i, para = [], 0, None
    right = max((ln["segs"][-1]["x1"] for ln in lines), default=0)
    left = min((ln["segs"][0]["x0"] for ln in lines), default=0)
    while i < len(lines):
        ln = lines[i]
        if _is_table_line(ln):
            run = [ln]
            j = i + 1
            while j < len(lines) and _is_table_line(lines[j]) and \
                    abs(lines[j - 1]["y"] - lines[j]["y"]) < max(lines[j]["size"] * 3.5, 30):
                run.append(lines[j])
                j += 1
            numeric = sum(1 for l in run for s in l["segs"] if N.parse_cell(s["text"]))
            if j == len(lines) and len(run) == 1 and numeric == 0 and len(ln["segs"]) >= 2:
                # 쪽 맨 아래에 혼자 남은 머리글 줄: 다음 쪽 표와 이어 붙일 수 있게 표로 표시(못 이으면 문단으로 되돌림)
                t = _table(run)
                if t:
                    t["header_only"] = True
                    if para:
                        blocks.append(para)
                        para = None
                    blocks.append(t)
                    i = j
                    continue
            single_top = not blocks and para is None and len(run) == 1 and numeric >= 1 and len(ln["segs"]) >= 2
            if (len(run) >= 2 and numeric >= 2) or single_top:
                # single_top: 쪽 맨 위 한 줄짜리 표(앞 쪽 표의 마지막 행이 넘어온 것) — 못 이으면 문단으로 되돌림
                t = _table(run)
                if t and single_top and len(run) == 1:
                    t["cont_only"] = True
                if t:
                    if para:
                        blocks.append(para)
                        para = None
                    blocks.append(t)
                    i = j
                    continue
        text = " ".join(s["text"] for s in ln["segs"])
        prev_y = lines[i - 1]["y"] if i else None
        # 앞 줄이 오른쪽 끝까지 찼을 때만(줄바꿈으로 이어진 문장) 한 문단으로 잇는다
        prev_full = at_edge = False
        if i > 0:
            px1 = lines[i - 1]["segs"][-1]["x1"]
            s0 = ln["segs"][0]
            word = (s0["text"].split(" ") or [""])[0]
            first_w = (s0["x1"] - s0["x0"]) * len(word) / max(1, len(s0["text"]))
            # 앞 줄이 오른쪽 끝 가까이 찼거나, 이 줄 첫 낱말이 앞 줄에 들어갈 자리가 없었으면 줄바꿈된 것
            prev_full = px1 >= left + (right - left) * 0.85 or px1 + first_w + ln["size"] * 0.3 >= right - 1
            at_edge = px1 >= right - ln["size"] * 1.5          # 오른쪽 끝까지 꽉 찬 줄: 문장 끝 글자와 상관없이 잇는다
        joinable = para is not None and prev_y is not None and abs(prev_y - ln["y"]) < ln["size"] * 1.9 \
            and prev_full and not MARK.match(text) and (
                at_edge or not para["text"].rstrip().endswith((".", "다", "음", "함", "임", ":")) or para["text"].rstrip().endswith("보다"))
        if joinable:
            para["text"] += " " + text
        else:
            if para:
                blocks.append(para)
            para = {"type": "p", "text": text}
        i += 1
    if para:
        blocks.append(para)
    return blocks
