# -*- coding: utf-8 -*-
"""[가상자료 ⑧] 가상 공문 만들기(요구 공문·검사 의뢰·결과 알림·협조 요청).

공문의 '틀'(수신·경유·제목·본문 번호·붙임·끝·발신명의·결재 줄·시행 번호·공개 구분·하단 문구)은
실제 공문에서 여러 문서에 공통으로 나오는 형식만 참고했다. 이름·기관·주소·번호는 모두 가상이다.
"""
import datetime

from app.parts.mockdata import vocab as V
from app.parts.mockdata.errors import weekday_text


def _approval(rng, sender_team, lead):
    """결재 줄 표: 기안자 → 검토자 → 결재권자(전결)."""
    a = V.person(rng)
    b = V.person(rng)
    c = V.person(rng)
    return {"kind": "table", "rows": [["기안자", "검토자", "결재권자"],
                                      [f"{rng.choice(V.RANKS)} {a}", f"{sender_team}장 {b}", f"{lead} {c}(전결)"]],
            "widths": [1, 1, 1]}


def letter(rng, sender, receiver, title, body, attach, signer, sender_team, lead, doc_no, date, org):
    blocks = [{"kind": "center", "text": sender},
              {"kind": "blank"},
              {"kind": "body", "text": f"수신  {receiver}"},
              {"kind": "body", "text": "(경유)"},
              {"kind": "body", "text": f"제목  {title}"},
              {"kind": "blank"}]
    blocks.extend(body)
    if attach:
        if len(attach) == 1:
            blocks.append({"kind": "body", "text": f"붙임  {attach[0]}.  끝."})
        else:
            for i, a in enumerate(attach):
                tail = ".  끝." if i == len(attach) - 1 else "."
                blocks.append({"kind": "body", "text": ("붙임  " if i == 0 else "      ") + f"{i + 1}. {a}{tail}"})
    else:
        blocks.append({"kind": "body", "text": "끝."})
    blocks += [{"kind": "blank"}, {"kind": "center", "text": signer}, {"kind": "blank"},
               _approval(rng, sender_team, lead),
               {"kind": "note", "text": f"협조자  {sender_team} {rng.choice(V.RANKS)} {V.person(rng)}"},
               {"kind": "note", "text": f"시행  {doc_no} ({date.year}. {date.month}. {date.day}.)   접수"},
               {"kind": "note", "text": f"우 {org['zip']}  {org['addr']}  / {org['web']}"},
               {"kind": "note", "text": f"전화번호 {org['tel']}  팩스번호 {org['tel'][:-4]}{rng.randint(1000, 9999)}  "
                                        f"/ {rng.choice(V.OPEN_KINDS)}"},
               {"kind": "note", "text": rng.choice(V.FOOTERS)}]
    return blocks


def request_letter(rng, ctx, tables, nums):
    """의회 → 연구원: 행정사무감사 요구자료 제출 요청(붙임: 작성양식·작성 지침)."""
    org, y = ctx["org"], ctx["year"]
    due = ctx["due_date"]
    rows = [["연번", "요구자료", "담당", "비고"]]
    for t in sorted(tables, key=lambda x: nums[x.key]):
        rows.append([str(nums[t.key]), t.title, ctx["teams"][t.team], "표 작성"])
    body = [{"kind": "body", "text": f"1. 관련: {org['council']}-{rng.randint(1000, 9999)}({y}. 10. {rng.randint(1, 9)}.)"},
            {"kind": "body", "text": f"2. 위 호와 관련하여 {y}년도 행정사무감사 요구자료를 아래와 같이 제출하여 주시기 바랍니다."},
            {"kind": "body", "text": f"  가. 제출 기한: {weekday_text(due)} 18:00까지"},
            {"kind": "body", "text": "  나. 제출 방법: 붙임 작성양식에 작성하여 전자문서로 제출(엑셀 원자료 함께 첨부)"},
            {"kind": "body", "text": "  다. 요구자료 목록"},
            {"kind": "table", "rows": rows, "widths": [1, 6, 2, 1], "left": (1,)},
            {"kind": "body", "text": "3. 수치는 원자료와 대조하여 정확하게 작성하고, 단위와 기준일을 반드시 표기하여 주시기 바랍니다."}]
    return letter(rng, f"{org['province']}의회", f"{org['name']}장", f"{y}년도 행정사무감사 요구자료 제출 요청", body,
                  ["요구자료 작성양식 1부", "요구자료 작성 지침 1부"], f"{org['province']}의회 환경농정위원장",
                  "의사담당", "전문위원", f"{org['province']}의회 환경농정위원회-{rng.randint(1000, 9999)}",
                  datetime.date(y, 10, rng.randint(10, 15)), org)


def test_request(rng, ctx, city, seq):
    """시군 → 연구원: 수질오염도 검사 의뢰."""
    org, y = ctx["org"], ctx["year"]
    m = rng.randint(9, 10)
    n = rng.randint(2, 6)
    items = rng.choice(["BOD, TOC, SS, T-N, T-P", "BOD, COD, SS", "TOC, BOD, SS, T-N, T-P, 총대장균군", "pH, SS, 노말헥산 추출물질"])
    rows = [["시료번호", "채취일", "시험항목(기준)", "지역구분", "시료 수량", "비고"]]
    for i in range(n):
        rows.append([f"{seq}-{m}-{i + 1}", f"'{y % 100}.{m:02d}.{rng.randint(1, 28):02d}.", items,
                     rng.choice(["청정", "가", "나", "특례"]), "1", ""])
    body = [{"kind": "body", "text": "1. 귀 원의 무궁한 발전을 기원합니다."},
            {"kind": "body", "text": f"2. 「물환경보전법」에 따라 우리 {city[-1]}에서 관리하는 배출시설에서 채수한 시료에 대하여 "
                                     "아래와 같이 오염도 검사를 의뢰하오니, 검사 후 그 결과를 회신하여 주시기 바랍니다."},
            {"kind": "body", "text": "□ 검사의뢰 내역"},
            {"kind": "table", "rows": rows, "widths": [2, 2, 4, 1, 1, 1], "left": (2,)}]
    return letter(rng, f"{org['province']} {city}", f"{org['name']}장", f"폐수오염도 검사 의뢰({seq}-{m}-1~{n})", body,
                  ["시료채취기록부 1부", f"시료 {n}건(별송)"], f"{city}장", "환경지도팀", "환경지도과장",
                  f"환경지도과-{rng.randint(1000, 9999)}", datetime.date(y, m, rng.randint(1, 28)), org)


def result_notice(rng, ctx, city, seq):
    """연구원 → 시군: 수질오염도 검사 결과 알림(결과 표 포함)."""
    org, y = ctx["org"], ctx["year"]
    m = rng.randint(9, 10)
    rows = [["시료번호", "검사항목", "결과", "기준", "판정"]]
    for i in range(rng.randint(2, 5)):
        for it, lim, lo, hi in [("BOD", 10, 0.5, 14), ("SS", 10, 0.6, 13), ("T-N", 20, 1.2, 24), ("T-P", 2, 0.05, 2.6)]:
            v = round(rng.uniform(lo, hi), 1 if it != "T-P" else 3)
            rows.append([f"{seq}-{m}-{i + 1}", it, f"{v}", f"{lim} 이하", "적합" if v <= lim else "부적합"])
    body = [{"kind": "body", "text": f"1. 귀 {city[-1]}의 무궁한 발전을 기원합니다."},
            {"kind": "body", "text": f"2. 귀 {city[-1]}에서 의뢰한 수질오염도 검사 결과를 붙임과 같이 알려 드립니다."},
            {"kind": "table", "rows": rows, "widths": [2, 2, 1, 1, 1]}]
    return letter(rng, org["name"], f"{city}장(환경지도과장)", f"수질오염도 검사 결과 알림[{seq}-{m}-1]", body,
                  ["시험성적서 각 1부"], f"{org['name']}장", "수질분석팀", "원장 지정대리",
                  f"{org['dept_code']}-{rng.randint(10000, 99999)}", datetime.date(y, m, rng.randint(1, 28)), org)


def coop_request(rng, ctx, rivers):
    """연구원 → 시군: 생태하천 현장점검 협조 요청(점검 일정 표, 날짜마다 요일)."""
    org, y = ctx["org"], ctx["year"]
    rows = [["연번", "시군", "하천명", "점검일", "점검시간", "비고"]]
    for i, rv in enumerate(rivers):
        d = datetime.date(y, rng.randint(10, 11), rng.randint(1, 27))
        rows.append([str(i + 1), rng.choice(ctx["cities"]), rv, weekday_text(d), "10:00~12:00", "사후관리 하천"])
    body = [{"kind": "body", "text": "1. 귀 기관의 무궁한 발전을 기원합니다."},
            {"kind": "body", "text": f"2. {y}년 하반기 생태하천복원사업 현장점검을 아래와 같이 실시하고자 하오니 "
                                     "관계 공무원이 참석할 수 있도록 협조하여 주시기 바랍니다."},
            {"kind": "table", "rows": rows, "widths": [1, 2, 2, 3, 2, 2]}]
    return letter(rng, org["name"], "수신자 참조", f"{y}년 하반기 생태하천복원사업 현장점검 협조 요청", body,
                  ["점검대상 및 일정 1부", "채수지점도 1부"], f"{org['name']}장", "생태하천팀", "원장 지정대리",
                  f"{org['dept_code']}-{rng.randint(10000, 99999)}", datetime.date(y, 9, rng.randint(15, 28)), org)
