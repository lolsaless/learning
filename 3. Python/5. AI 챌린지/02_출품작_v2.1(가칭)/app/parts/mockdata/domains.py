# -*- coding: utf-8 -*-
"""[가상자료 ③] 자료 영역 12종. 영역 하나 = 요구자료 표 하나(DataTable)를 무작위로 만든다.

새 영역 추가: make_<이름>(rng, ctx) 함수를 만들고 아래 DOMAINS 목록에 (이름, 함수)를 넣는다.
  ctx: {"year", "cities", "rivers", "stations", "teams"}
모든 함수는 표시값으로 다시 계산해도 합계·비율이 맞는 '정상 표'를 돌려준다(retry 로 보장).
"""
from app.parts.mockdata.model import DataTable
from app.parts.mockdata import vocab as V


def _retry(fn, rng, ctx, tries=40):
    for _ in range(tries):
        t = fn(rng, ctx)
        if t.consistent():
            return t
    return t


def make_river(rng, ctx):
    """하천 수질(지점×항목, 1~9월 평균). 원본: 월별 시트 9개 + 연평균 시트, 지점은 코드로 적음."""
    rivers = ctx["rivers"]
    sites = []
    for rv in rivers[:3]:
        for pos in rng.sample(["상류", "중류", "하류", "합류전", "합류후"], 2):
            sites.append(f"{rv} {pos}")
    sites = sites[:rng.randint(5, 6)]
    items = rng.sample(["BOD", "COD", "TOC", "SS", "T-N", "T-P"], rng.randint(4, 5))
    items.sort(key=["BOD", "COD", "TOC", "SS", "T-N", "T-P"].index)
    base = {"BOD": (1.8, 0.9), "COD": (4.4, 1.6), "TOC": (3.2, 1.0), "SS": (6.5, 4.0), "T-N": (2.6, 0.9), "T-P": (0.06, 0.03)}
    rawdec = {"BOD": 1, "COD": 1, "TOC": 1, "SS": 1, "T-N": 3, "T-P": 4}
    docdec = {"BOD": 1, "COD": 1, "TOC": 1, "SS": 1, "T-N": 2, "T-P": 3}
    cols = [V.DOC_NAME[i] for i in items]
    monthly, values = {}, {}
    for si, s in enumerate(sites):
        load = 0.6 + 0.15 * si + rng.uniform(-0.1, 0.1)
        for it, cn in zip(items, cols):
            mu, sd = base[it]
            ms = [round(max(0.005 if it == "T-P" else 0.1, mu * load + rng.uniform(-sd, sd) * 0.6), rawdec[it]) for _ in range(9)]
            monthly[(s, cn)] = ms
            values[(s, cn)] = sum(ms) / 9
    codes = {s: f"{ctx['code']}-{i + 1:02d}" for i, s in enumerate(sites)}
    t = DataTable("river", "수질", f"{ctx['year']}년 주요 하천 수질 측정 결과", "측정지점", sites, cols, values,
                  {c: docdec[i] for i, c in zip(items, cols)}, unit="(단위: mg/L, 1~9월 평균)",
                  src_cols={c: i for i, c in zip(items, cols)}, src_rows=codes, src_title=f"{ctx['year']}년 하천 수질 연평균(1~9월)",
                  src_file="하천수질_측정결과.xlsx", src_sheet="연평균", allow_transpose=False, monthly=True,
                  sheet_unit="단위: mg/L / 산술평균, 반올림 전 값")
    t.monthly_data = monthly
    return t


def make_requests(rng, ctx):
    """시군별 수질검사 의뢰 접수(건수·항목 수·수수료). 원본 수수료는 원 단위."""
    cities = ctx["cities"][:rng.randint(5, 7)]
    vals = {}
    for c in cities:
        n = rng.randint(18, 160)
        vals[(c, "접수 건수")] = n
        vals[(c, "검사 항목 수")] = n * rng.randint(5, 14) + rng.randint(0, 9)
        vals[(c, "수수료(천원)")] = (vals[(c, "검사 항목 수")] * rng.choice([18200, 23500, 31800]) + rng.randint(0, 9) * 100) / 1000
    return DataTable("requests", "수질", "시군별 수질검사 의뢰 접수 현황", "의뢰기관", cities,
                     ["접수 건수", "검사 항목 수", "수수료(천원)"], vals, {"접수 건수": 0, "검사 항목 수": 0, "수수료(천원)": 0},
                     total=True, src_scale={"수수료(천원)": 1000},
                     src_cols={"접수 건수": "접수 건수", "검사 항목 수": "검사항목수", "수수료(천원)": "수수료 합계(원)"},
                     src_title=f"{ctx['year']}년 시군별 의뢰 접수 집계", src_file="수질검사의뢰_접수대장.xlsx", src_sheet="시군별집계",
                     sheet_unit="단위: 건, 항목, 원")


def make_effluent(rng, ctx):
    """폐수배출시설 방류수 검사와 부적합률."""
    cities = rng.sample(ctx["cities"], rng.randint(5, 6))
    vals = {}
    for c in cities:
        n = rng.randint(40, 260)
        vals[(c, "검사 건수")] = n
        vals[(c, "부적합 건수")] = rng.randint(1, max(2, n // 9))
    return DataTable("effluent", "수질", "폐수배출시설 방류수 검사 및 부적합 현황", "시군", cities,
                     ["검사 건수", "부적합 건수", "부적합률(%)"], vals, {"검사 건수": 0, "부적합 건수": 0, "부적합률(%)": 1},
                     total=True, ratio=("부적합률(%)", "부적합 건수", "검사 건수"),
                     src_cols={"검사 건수": "검사", "부적합 건수": "부적합", "부적합률(%)": "부적합률"},
                     src_title="방류수 오염도 검사 결과 집계", src_file="폐수_오염도검사_결과대장.xlsx", src_sheet="시군별")


def make_air(rng, ctx):
    """대기오염 측정망(측정소가 문서에서는 열, 원본에서는 행 → 행·열 뒤바뀜)."""
    sts = ctx["stations"][:rng.randint(5, 6)]
    rows = ["PM10 평균(㎍/㎥)", "PM2.5 평균(㎍/㎥)", "PM10 나쁨 일수", "PM2.5 나쁨 일수"]
    vals = {}
    for i, s in enumerate(sts):
        vals[("PM10 평균(㎍/㎥)", s)] = rng.uniform(30, 52) + i * 0.37
        vals[("PM2.5 평균(㎍/㎥)", s)] = rng.uniform(14, 27) + i * 0.21
        vals[("PM10 나쁨 일수", s)] = rng.randint(4, 19)
        vals[("PM2.5 나쁨 일수", s)] = rng.randint(9, 34)
    t = DataTable("air", "대기", f"대기오염측정망 측정 결과({ctx['year']}. 1.~9.)", "구분", rows, sts, vals,
                  {s: 1 for s in sts}, src_title=f"{ctx['year']}년 측정소별 요약(1~9월)",
                  src_file="대기측정망_월보.xlsx", src_sheet="요약", allow_transpose=True,
                  note="※ 나쁨 일수: 일평균 PM10 81㎍/㎥, PM2.5 36㎍/㎥ 초과일")
    t.force_transpose = True
    t.row_decs = {"PM10 평균(㎍/㎥)": 1, "PM2.5 평균(㎍/㎥)": 1, "PM10 나쁨 일수": 0, "PM2.5 나쁨 일수": 0}
    return t


def make_drinking(rng, ctx):
    types = ["수돗물", "지하수(민방위 비상급수)", "먹는샘물", "약수터"]
    vals = {}
    for t_ in types:
        n = rng.randint(90, 720)
        vals[(t_, "검사 건수")] = n
        vals[(t_, "부적합 건수")] = rng.randint(0, max(1, n // 40))
    return DataTable("drinking", "먹는물", f"먹는물 수질검사 및 부적합 현황({ctx['year']}. 1.~9.)", "구분", types,
                     ["검사 건수", "부적합 건수", "부적합률(%)"], vals, {"검사 건수": 0, "부적합 건수": 0, "부적합률(%)": 1},
                     total=True, ratio=("부적합률(%)", "부적합 건수", "검사 건수"),
                     src_cols={"검사 건수": "검사", "부적합 건수": "부적합", "부적합률(%)": "부적합 비율"},
                     src_title="부적합 현황(1~9월)", src_file="먹는물_수질검사_실적.xlsx", src_sheet="부적합")


def make_equip(rng, ctx):
    cats = rng.sample(["크로마토그래피", "분광분석기", "질량분석기", "미생물 분석장비", "전처리 장비", "현장 측정장비",
                       "중금속 분석장비", "유기물 분석장비"], rng.randint(4, 6))
    vals = {}
    for c in cats:
        n = rng.randint(9, 48)
        vals[(c, "보유(대)")] = n
        vals[(c, "내용연수 경과(대)")] = rng.randint(1, n // 2)
    return DataTable("equip", "운영", "주요 시험장비 보유 현황", "분류", cats, ["보유(대)", "내용연수 경과(대)"], vals,
                     {"보유(대)": 0, "내용연수 경과(대)": 0}, total=True,
                     src_cols={"보유(대)": "보유", "내용연수 경과(대)": "내용연수 경과"},
                     src_title="분류별 집계(장비관리대장)", src_file="장비관리대장_통합.xlsx", src_sheet="분류별집계")


def make_budget(rng, ctx):
    progs = rng.sample(["시험분석 장비 운영", "하천 수질측정망 운영", "대기측정망 운영", "토양 실태조사", "먹는물 검사",
                        "악취 관리 지원", "연구원 시설 유지관리", "직원 역량 강화", "정도관리 운영", "감염병 검사 지원"],
                       rng.randint(5, 7))
    vals = {}
    for p in progs:
        b = rng.randint(180, 2600) * 1000 + rng.randint(0, 999) + rng.choice([0, 0.5])
        vals[(p, "예산액(천원)")] = b
        vals[(p, "집행액(천원)")] = round(b * rng.uniform(0.6, 0.94), 2)
    return DataTable("budget", "운영", f"{ctx['year']}년 세출예산 집행 현황(9. 30. 기준)", "세부사업", progs,
                     ["예산액(천원)", "집행액(천원)", "집행률(%)"], vals, {"예산액(천원)": 0, "집행액(천원)": 0, "집행률(%)": 1},
                     total=True, ratio=("집행률(%)", "집행액(천원)", "예산액(천원)"),
                     src_scale={"예산액(천원)": 1000, "집행액(천원)": 1000},
                     src_cols={"예산액(천원)": "예산현액", "집행액(천원)": "지출액", "집행률(%)": "집행률"},
                     src_title=f"{ctx['year']}년 세출예산 집행현황(9. 30. 기준)", src_file="세출예산_집행현황.xlsx",
                     src_sheet="집행현황", sheet_unit="단위: 원")


def make_staff(rng, ctx):
    jobs = ["환경연구사", "보건연구사", "환경직", "행정직", "공무직"]
    vals = {}
    for j in jobs:
        a = rng.randint(11, 64)
        vals[(j, "정원")] = a
        vals[(j, "현원")] = a - rng.randint(0, 4)
        vals[(j, "결원")] = vals[(j, "정원")] - vals[(j, "현원")]
    return DataTable("staff", "운영", "직렬별 인력 현황", "직렬", jobs, ["정원", "현원", "결원"], vals,
                     {"정원": 0, "현원": 0, "결원": 0}, total=True, src_title=f"직렬별 인력 현황({ctx['year']}. 9. 30.)",
                     src_file="인력현황.xlsx", src_sheet="직렬별")


def make_inspection(rng, ctx):
    rivers = rng.sample(ctx["rivers"], min(5, len(ctx["rivers"])))
    vals = {}
    for r in rivers:
        vals[(r, "사업량(km)")] = round(rng.uniform(0.8, 9.5), 2)
        vals[(r, "총사업비(백만원)")] = rng.randint(1200, 24000) + rng.randint(0, 9) / 10
        vals[(r, "채수 지점 수")] = rng.randint(3, 9)
    return DataTable("inspection", "생태", f"{ctx['year']}년 하반기 생태하천복원사업 현장점검 대상", "하천명", rivers,
                     ["사업량(km)", "총사업비(백만원)", "채수 지점 수"], vals,
                     {"사업량(km)": 1, "총사업비(백만원)": 0, "채수 지점 수": 0},
                     src_cols={"사업량(km)": "사업량\n(km)", "총사업비(백만원)": "총사업비\n(단위: 백만원)", "채수 지점 수": "지점 수"},
                     src_title="[붙임 1] 점검대상 및 일정", src_file="생태하천_현장점검_대상지.xlsx", src_sheet="하반기 점검대상")


def make_qc(rng, ctx):
    items = rng.sample(["BOD", "COD", "총질소", "총인", "페놀류", "시안", "6가크롬", "노말헥산 추출물질"], rng.randint(4, 6))
    vals = {}
    for it in items:
        vals[(it, "정확도(%)")] = rng.uniform(86, 112)
        vals[(it, "정밀도(%RSD)")] = rng.uniform(1.2, 14.5)
        vals[(it, "정량한계(mg/L)")] = rng.choice([0.005, 0.01, 0.02, 0.05, 0.1, 0.5]) * rng.uniform(0.8, 1.2)
    return DataTable("qc", "정도", f"{ctx['year']}년 시험항목별 정도관리 결과", "시험항목", items,
                     ["정확도(%)", "정밀도(%RSD)", "정량한계(mg/L)"], vals,
                     {"정확도(%)": 1, "정밀도(%RSD)": 1, "정량한계(mg/L)": 3},
                     src_cols={"정확도(%)": "회수율(%)", "정밀도(%RSD)": "RSD(%)", "정량한계(mg/L)": "LOQ(mg/L)"},
                     src_title="정도관리 결과 집계(내부정도관리)", src_file="정도관리_결과.xlsx", src_sheet="항목별")


def make_perf(rng, ctx):
    y = ctx["year"]
    fields = ["먹는물", "수질", "대기", "토양·폐기물", "기타(의뢰 시험)"]
    vals, prev_q = {}, {}
    for f_, base in zip(fields, [3150, 2850, 1720, 780, 410]):
        a = int(base * rng.uniform(0.85, 1.05))
        b = int(base * rng.uniform(0.92, 1.08))
        q25 = int(b * rng.uniform(0.7, 0.78))
        vals[(f_, f"{y - 2}년")] = a
        vals[(f_, f"{y - 1}년")] = b
        vals[(f_, f"{y}년(1~9월)")] = int(q25 * rng.uniform(0.9, 1.2))
        prev_q[f_] = q25
    cols = [f"{y - 2}년", f"{y - 1}년", f"{y}년(1~9월)"]
    t = DataTable("perf", "운영", "최근 3년간 분야별 시험·검사 실적", "분야", fields, cols, vals, {c: 0 for c in cols},
                  total=True, src_title="분야별 시험·검사 실적", src_file="시험검사_실적_종합.xlsx", src_sheet="분야별",
                  sheet_unit="단위: 건")
    a = int(t.values[("합계", f"{y}년(1~9월)")])
    b = sum(prev_q.values())
    t.extra_src_cols = {f"{y - 1}년 1~9월": prev_q}      # 문장에 쓰는 비교값(문서 표에는 없음)
    t.claim = {"what": f"{y}년 1~9월 시험·검사 실적", "a": a, "b": b, "u": "건"}
    return t


def make_complaint(rng, ctx):
    y = ctx["year"]
    rows = ["접수", "처리 완료", "처리 중"]
    cols = [f"{y - 2}년", f"{y - 1}년", f"{y}년(1~9월)"]
    vals = {}
    for c in cols:
        n = rng.randint(280, 520)
        done = n - rng.randint(5, 22)
        vals[("접수", c)] = n
        vals[("처리 완료", c)] = done
        vals[("처리 중", c)] = n - done
    t = DataTable("complaint", "대기", "악취 민원 처리 현황", "구분", rows, cols, vals, {c: 0 for c in cols},
                  src_title=f"악취 민원 처리 현황({y - 2}~{y})", src_file="악취민원_처리현황.xlsx", src_sheet="연도별",
                  sheet_unit="단위: 건")
    prev = int(vals[("접수", f"{y - 1}년")] * rng.uniform(0.7, 0.8))
    t.extra_src_rows = {f"{y - 1}년(1~9월) 접수": prev}
    t.claim = {"what": f"{y}년 1~9월 악취 민원", "a": vals[("접수", f"{y}년(1~9월)")], "b": prev, "u": "건"}
    return t


DOMAINS = [
    ("perf", make_perf), ("river", make_river), ("air", make_air), ("budget", make_budget),
    ("requests", make_requests), ("drinking", make_drinking), ("effluent", make_effluent), ("equip", make_equip),
    ("staff", make_staff), ("complaint", make_complaint), ("inspection", make_inspection), ("qc", make_qc),
]
DOMAIN_TITLES = {
    "perf": "시험·검사 실적", "river": "하천 수질", "air": "대기 측정망", "budget": "세출예산", "requests": "검사 의뢰 접수",
    "drinking": "먹는물 검사", "effluent": "폐수 검사", "equip": "장비 보유", "staff": "인력", "complaint": "악취 민원",
    "inspection": "생태하천 점검", "qc": "정도관리",
}


def make_tables(rng, ctx, names):
    fn = dict(DOMAINS)
    return [_retry(fn[n], rng, ctx) for n in names]
