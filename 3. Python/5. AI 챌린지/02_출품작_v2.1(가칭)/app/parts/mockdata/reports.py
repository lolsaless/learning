# -*- coding: utf-8 -*-
"""[가상자료 ⑦] 팀 답변서·취합본·작성틀의 문서 모형을 만든다(오류는 errors.py 가 나중에 심음)."""
import copy

from app.parts.mockdata.model import rhalf
from app.parts.mockdata.errors import weekday_text
from app.parts.mockdata import statements

FAKE_WORDS = ["현장 합동점검", "찾아가는 수질 교육", "고농도 미세먼지 비상저감조치 발령", "시료 긴급 분석",
              "취약지역 환경 순찰", "민관 합동 하천 정화 활동"]


def claim_sentence(cl):
    a, b = cl["a"], cl["b"]
    pct = abs(a - b) / b * 100
    cl["pct"] = pct
    cl["pct_text"] = f"{rhalf(pct, 1):.1f}"
    way = "증가" if a >= b else "감소"
    return f"{cl['what']}은 총 {a:,}{cl['u']}으로 전년 동기({b:,}{cl['u']}) 대비 {cl['pct_text']}% {way}하였음"


def table_blocks(t, num, with_claim=True):
    out = [{"kind": "head", "text": f"□ 요구자료 {num}. {t.title}"}]
    if with_claim and t.claim:
        cl = dict(t.claim)
        out.append({"kind": "p", "style": "body", "text": claim_sentence(cl), "claim": cl})
    if t.unit:
        out.append({"kind": "note", "text": t.unit})
    rows = t.doc_rows()
    ncol = len(rows[0])
    wide_label = max(len(str(r[0]["t"] if isinstance(r[0], dict) else r[0])) for r in rows) > 8
    out.append({"kind": "table", "t": t, "rows": rows, "num": num,
                "widths": [4 if wide_label else 3] + [2] * (ncol - 1), "left": (0,) if wide_label else ()})
    if t.note:
        out.append({"kind": "note", "text": t.note})
    out.append({"kind": "blank"})
    return out


def team_docs(tables, nums, year, teams_names):
    docs = {}
    for t in tables:
        docs.setdefault(t.team, [{"kind": "title", "text": f"{year}년 행정사무감사 요구자료 답변({teams_names[t.team]})"},
                                 {"kind": "blank"}])
        docs[t.team].extend(table_blocks(t, nums[t.key]))
    return docs


def collected(tables, nums, ctx, rng):
    y = ctx["year"]
    org = ctx["org"]
    audit = ctx["audit_date"]
    due = ctx["due_date"]
    word = rng.choice(FAKE_WORDS)
    blocks = [{"kind": "title", "text": f"{y}년도 행정사무감사 요구자료"},
              {"kind": "text", "text": f"{org['name']} / {org['council']} 제출"},
              {"kind": "blank"},
              {"kind": "head", "text": "□ 개요"},
              {"kind": "p", "style": "body", "text": f"감사 일시: {weekday_text(audit)} 10:00, 도의회 제{rng.randint(1, 4)}회의실",
               "date": audit},
              {"kind": "p", "style": "body", "text": f"자료 제출 기한: {weekday_text(due)}까지 위원회 제출", "date": due},
              {"kind": "p", "style": "body", "text": f"올해 {word}은(는) 총 {{FAKE}}회 실시하였음", "fake_slot": True,
               "fake_word": word},
              {"kind": "blank"}]
    for t in sorted(tables, key=lambda x: nums[x.key]):
        tb = table_blocks(t, nums[t.key])
        free = ctx.get("stmt_free") and rng.random() < 0.5
        st = statements.make(t, rng, free=free)
        if st:                                       # 표 바로 뒤(주석 앞)에 계산 문장
            at = next(i for i, b in enumerate(tb) if b["kind"] == "table") + 1
            tb.insert(at, st)
        blocks.extend(tb)
    return blocks


def finish_fake(blocks, fallback):
    """오류로 쓰지 않은 '출처 없는 숫자' 자리는 지워서 정상 문장으로 바꾼다."""
    out = []
    for b in blocks:
        if b.get("fake_slot"):
            continue
        out.append(b)
    return out


def form_blocks(tables, nums, year):
    """작성틀: 값 칸을 비우고 문장의 숫자를 ○○ 로 바꾼 양식(작성해서 제출하는 문서)."""
    blocks = [{"kind": "title", "text": f"{year}년도 행정사무감사 요구자료 — 작성틀"},
              {"kind": "text", "text": "※ 빈 칸에 원본 엑셀 값을 [입력하기]로 채우면 출처가 함께 기록됩니다"},
              {"kind": "blank"}]
    blanks = 0
    for t in tables:
        tb = table_blocks(t, nums[t.key], with_claim=False)
        for b in tb:
            if b["kind"] == "table":
                b = copy.copy(b)
                rows = [b["rows"][0]] + [[r[0]] + [""] * (len(r) - 1) for r in b["rows"][1:]]
                blanks += sum(len(r) - 1 for r in rows[1:])
                b["rows"] = rows
            blocks.append(b)
        if t.claim:
            blocks.insert(len(blocks) - 1, {"kind": "body", "text": f"{t.claim['what']}은 총 ○○{t.claim['u']}으로 전년 동기(○○{t.claim['u']}) 대비 ○○% 증가(감소)하였음"})
            blanks += 3
    return blocks, blanks
