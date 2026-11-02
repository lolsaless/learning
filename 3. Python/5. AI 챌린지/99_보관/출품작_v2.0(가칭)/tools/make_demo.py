# -*- coding: utf-8 -*-
"""
시연 자료 생성기
────────────────────────
가상 기관 「한빛도 보건환경연구원」의 2026년 행정사무감사 요구자료 작성 상황을 만든다.
  · 01_원본자료 : 팀별 원본 엑셀 12개(머리글·단위·배치가 한글 문서와 다름)
  · 02_팀제출   : 팀별 답변 hwpx 5개(팀이 엑셀에서 옮겨 적은 문서)
  · 03_취합     : 대표팀 취합본 hwpx(오류를 일부러 심음) + 빈 작성틀 hwpx
  · 나중에_받은_자료 : 수질팀이 나중에 보낸 수정 엑셀(원본 변경 시연용)
  · 정답표.json : 심은 오류 목록(자동 채점용)
모든 기관·지명·수치는 가상이다. 같은 씨앗값(SEED)으로 언제나 같은 자료가 만들어진다.

실행:  python tools/make_demo.py [출력폴더]   (기본: ./시연자료)
"""
import os
import sys
import json
import random
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from app.formats.xlsx import write_xlsx          # noqa: E402
from app.formats.hwpx_build import HwpxBuilder      # noqa: E402

SEED = 2026
ORG = "한빛도 보건환경연구원"
COUNCIL = "한빛도의회 환경농정위원회"
TEAM = {"수질": "수질분석팀", "대기": "대기환경팀", "토양": "토양폐기물팀", "먹는물": "먹는물검사팀", "운영": "운영지원팀"}

H = {"bold": True, "fill": "#DDE6F0", "align": "center"}


def hd(v):
    return dict(H, v=v)


def num(v, fmt):
    return {"v": v, "fmt": fmt}


def title_rows(title, sub=None):
    rows = [[{"v": title, "bold": True, "border": False}]]
    rows.append([{"v": sub or "", "border": False}])
    return rows


def f1(x):
    return f"{x:,.1f}"


def f0(x):
    return f"{int(round(x)):,}"


def r_half(x, d):
    """한국 문서 관행대로 반올림(사사오입)."""
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(1).scaleb(-d)
    return float(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))


def fmtd(x, d):
    return f"{r_half(x, d):,.{d}f}"


class Demo:
    def __init__(self, out):
        self.out = os.path.abspath(out)
        self.rng = random.Random(SEED)
        self.root = os.path.join(self.out, "공유폴더(가상)", "2026 행정사무감사")
        self.src = os.path.join(self.root, "01_원본자료")
        self.team = os.path.join(self.root, "02_팀제출")
        self.coll = os.path.join(self.root, "03_취합")
        self.later = os.path.join(self.out, "나중에_받은_자료")
        self.answers = []
        self.data = {}

    def p(self, *parts):
        path = os.path.join(*parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    # ════════════════════════════════════════════════
    #  1. 원본 엑셀
    # ════════════════════════════════════════════════
    def river(self, modified=False):
        rng = random.Random(SEED + 1)
        sites = [("HB-01", "은하천 상류", "은하천"), ("HB-02", "은하천 중류", "은하천"), ("HB-03", "은하천 하류", "은하천"),
                 ("HB-04", "솔내천 상류", "솔내천"), ("HB-05", "솔내천 하류", "솔내천"), ("HB-06", "가람강 합류전", "가람강"),
                 ("HB-07", "가람강 합류후", "가람강"), ("HB-08", "누리천 하류", "누리천")]
        items = ["수온", "pH", "DO", "BOD", "COD", "TOC", "SS", "T-N", "T-P"]
        base = {"수온": (14, 6, 1), "pH": (7.6, 0.3, 1), "DO": (9.8, 1.2, 1), "BOD": (1.6, 0.9, 1), "COD": (4.2, 1.5, 1),
                "TOC": (3.1, 1.0, 1), "SS": (6.5, 4.0, 1), "T-N": (2.6, 0.9, 3), "T-P": (0.06, 0.03, 4)}
        months = list(range(1, 10))
        vals = {}
        for si, (code, name, _) in enumerate(sites):
            load = 0.6 + 0.12 * si
            for it in items:
                mu, sd, d = base[it]
                for mo in months:
                    if it in ("수온",):
                        x = 4 + 22 * (1 - abs(mo - 7.5) / 6.5) + rng.uniform(-1.5, 1.5)
                    elif it in ("pH", "DO"):
                        x = mu + rng.uniform(-sd, sd)
                    else:
                        x = max(0.005 if it == "T-P" else 0.1, mu * load + rng.uniform(-sd, sd) * 0.6)
                    vals[(code, it, mo)] = round(x, d)

        def force_mean(code, it, target):
            cur = sum(vals[(code, it, m)] for m in months) / 9
            vals[(code, it, 9)] = round(vals[(code, it, 9)] + (target - cur) * 9, 4)
        force_mean("HB-03", "BOD", 2.338)     # 표시 2.3 → 취합본에서 3.2로 잘못 적음(E1)
        force_mean("HB-06", "T-P", 0.0853)    # 표시 0.085 → 나중에 0.092로 수정(E6)
        force_mean("HB-02", "T-N", 2.3455)    # 표시 2.35(반올림, 정상 사례)
        if modified:
            force_mean("HB-06", "T-P", 0.0921)
        mean = {(c, it): sum(vals[(c, it, m)] for m in months) / 9 for c, _, _ in sites for it in items}
        self.data["river"] = {"sites": sites, "items": items, "mean": mean}

        sheets = []
        rows = title_rows("2026년 하천 수질측정망 측정지점", "※ 측정지점 코드표")
        rows.append([hd("지점코드"), hd("지점명"), hd("수계"), hd("측정주기")])
        for code, name, sys_ in sites:
            rows.append([code, name, sys_, "월 1회"])
        sheets.append({"name": "측정지점", "rows": rows, "widths": [12, 16, 10, 10]})
        fmts = {"수온": "0.0", "pH": "0.0", "DO": "0.0", "BOD": "0.0", "COD": "0.0", "TOC": "0.0", "SS": "0.0",
                "T-N": "0.000", "T-P": "0.0000"}
        for mo in months:
            rows = title_rows(f"2026년 {mo}월 하천 수질 측정결과", "단위: mg/L (수온 ℃, pH 무차원)")
            rows.append([hd("지점코드"), hd("채수일")] + [hd(it) for it in items])
            for code, name, _ in sites:
                day = 3 + (sum(map(ord, code)) % 5)
                rows.append([code, f"2026-{mo:02d}-{day:02d}"] + [num(vals[(code, it, mo)], fmts[it]) for it in items])
            sheets.append({"name": f"{mo}월", "rows": rows, "widths": [10, 12] + [8] * len(items), "freeze": (3, 1)})
        rows = title_rows("2026년 하천 수질 연평균(1~9월)", "단위: mg/L / 산술평균, 반올림 전 값")
        rows.append([hd("지점코드")] + [hd(it) for it in items])
        for code, name, _ in sites:
            rows.append([code] + [num(mean[(code, it)], "0.000") for it in items])
        sheets.append({"name": "연평균", "rows": rows, "widths": [10] + [9] * len(items), "freeze": (3, 1)})
        return sheets

    def build_sources(self):
        rng = self.rng
        S = {}
        # 1) 하천 수질
        path = self.p(self.src, TEAM["수질"], "하천수질_측정결과_2026.xlsx")
        write_xlsx(path, self.river())
        S["river"] = path
        # 2) 수질검사 의뢰 접수대장
        cities = ["가온시", "나래시", "다솜군", "라온군", "마루시", "바다군"]
        kinds = ["하천수", "폐수", "지하수", "호소수", "공장 방류수"]
        rows = title_rows("2026년 수질검사 의뢰 접수대장", "1. 1. ~ 9. 30. 접수분")
        rows.append([hd(h) for h in ["접수번호", "접수일", "의뢰기관", "시료구분", "검사항목수", "수수료(원)"]])
        agg = {c: [0, 0, 0] for c in cities}
        for i in range(412):
            c = rng.choices(cities, weights=[30, 22, 12, 9, 18, 9])[0]
            n = rng.choice([3, 5, 8, 12, 15, 21])
            fee = n * rng.choice([18200, 23500, 31800])
            mo, dd = rng.randint(1, 9), rng.randint(1, 28)
            rows.append([f"2026-WQ-{i + 1:04d}", f"2026-{mo:02d}-{dd:02d}", c, rng.choice(kinds), n, num(fee, "#,##0")])
            agg[c][0] += 1
            agg[c][1] += n
            agg[c][2] += fee
        s1 = {"name": "접수대장", "rows": rows, "widths": [14, 12, 10, 12, 10, 12], "freeze": (3, 0), "autofilter": False}
        rows = title_rows("시군별 접수 집계", "단위: 건, 항목, 원")
        rows.append([hd("의뢰기관"), hd("접수 건수"), hd("검사 항목 수"), hd("수수료 합계(원)")])
        for c in cities:
            rows.append([c, agg[c][0], agg[c][1], num(agg[c][2], "#,##0")])
        rows.append([hd("합계"), sum(v[0] for v in agg.values()), sum(v[1] for v in agg.values()),
                     num(sum(v[2] for v in agg.values()), "#,##0")])
        path = self.p(self.src, TEAM["수질"], "수질검사의뢰_접수대장_2026.xlsx")
        write_xlsx(path, [s1, {"name": "시군별집계", "rows": rows, "widths": [12, 10, 12, 16]}])
        self.data["req"] = {"cities": cities, "agg": agg}
        # 3) 대기측정망 월보
        stations = ["가온동", "나래동", "다솜읍", "라온면", "마루동", "바다읍"]
        air = {}
        sheets = []
        for pol, mu in [("PM10", 38), ("PM2.5", 19), ("O3", 0.031), ("NO2", 0.018)]:
            rows = title_rows(f"2026년 대기오염도 월평균 — {pol}", "단위: ㎍/㎥ (O3·NO2는 ppm)")
            rows.append([hd("측정소")] + [hd(f"{m}월") for m in range(1, 10)] + [hd("평균")])
            for si, st in enumerate(stations):
                vs = []
                for m in range(1, 10):
                    season = 1.35 if m in (1, 2, 3, 4) else (0.8 if m in (7, 8, 9) else 1.0)
                    x = mu * season * (0.85 + 0.06 * si) * rng.uniform(0.85, 1.15)
                    vs.append(round(x, 3 if pol in ("O3", "NO2") else 0))
                avg = sum(vs) / len(vs)
                air[(pol, st)] = avg
                fm = "0.000" if pol in ("O3", "NO2") else "0"
                rows.append([st] + [num(v, fm) for v in vs] + [num(avg, "0.000" if fm == "0.000" else "0.0")])
            sheets.append({"name": pol, "rows": rows, "widths": [10] + [7] * 10, "freeze": (3, 1)})
        bad = {}
        rows = title_rows("2026년 측정소별 요약(1~9월)", "PM 나쁨 일수: 일평균 PM10 81㎍/㎥, PM2.5 36㎍/㎥ 초과일")
        rows.append([hd("측정소"), hd("PM10 평균"), hd("PM2.5 평균"), hd("PM10 나쁨일수"), hd("PM2.5 나쁨일수"), hd("유효측정일")])
        for si, st in enumerate(stations):
            b10, b25 = rng.randint(4, 15), rng.randint(9, 28)
            bad[st] = (b10, b25)
            rows.append([st, num(air[("PM10", st)], "0.0"), num(air[("PM2.5", st)], "0.0"), b10, b25, rng.randint(262, 272)])
        sheets.insert(0, {"name": "요약", "rows": rows, "widths": [10, 11, 11, 13, 13, 11]})
        path = self.p(self.src, TEAM["대기"], "대기측정망_월보_2026.xlsx")
        write_xlsx(path, sheets)
        self.data["air"] = {"stations": stations, "avg": air, "bad": bad}
        # 4) 악취 민원
        odor = {"2024": (468, 452, 16, 131), "2025": (471, 459, 12, 140), "2025(1~9월)": (352, 344, 8, 102),
                "2026(1~9월)": (312, 297, 15, 96)}
        rows = title_rows("악취 민원 처리 현황(2024~2026)", "단위: 건")
        rows.append([hd("기간"), hd("접수"), hd("처리 완료"), hd("처리 중"), hd("현장 점검")])
        for k, v in odor.items():
            rows.append([k] + list(v))
        path = self.p(self.src, TEAM["대기"], "악취민원_처리현황_2024-2026.xlsx")
        write_xlsx(path, [{"name": "연도별", "rows": rows, "widths": [14, 8, 10, 8, 10]}])
        self.data["odor"] = odor
        # 5) 토양오염 실태조사
        lands = ["공장용지", "주유소", "농경지", "하천변", "폐기물처리시설"]
        rows = title_rows("2026년 토양오염 실태조사 결과(지점별)", "단위: mg/kg")
        rows.append([hd(h) for h in ["지점번호", "지목", "시군", "카드뮴", "구리", "비소", "납", "아연", "니켈", "TPH", "우려기준 초과"]])
        cnt = {l: [0, 0] for l in lands}
        exceed_plan = {"공장용지": 2, "주유소": 3, "농경지": 0, "하천변": 1, "폐기물처리시설": 2}
        n_site = {"공장용지": 34, "주유소": 28, "농경지": 30, "하천변": 16, "폐기물처리시설": 12}
        k = 0
        for l in lands:
            ex_idx = set(rng.sample(range(n_site[l]), exceed_plan[l]))
            for j in range(n_site[l]):
                k += 1
                ex = j in ex_idx
                vals = [round(rng.uniform(0.1, 1.8), 2), round(rng.uniform(5, 60), 1), round(rng.uniform(1, 9), 2),
                        round(rng.uniform(5, 70), 1), round(rng.uniform(30, 180), 1), round(rng.uniform(3, 30), 1),
                        round(rng.uniform(20, 300) * (6 if ex else 1), 0)]
                rows.append([f"S-{k:03d}", l, rng.choice(cities)] + vals + ["초과" if ex else "-"])
                cnt[l][0] += 1
                cnt[l][1] += 1 if ex else 0
        s1 = {"name": "조사결과", "rows": rows, "widths": [9, 12, 8] + [8] * 7 + [10], "freeze": (3, 2)}
        rows = title_rows("지목별 집계", "단위: 지점")
        rows.append([hd("지목"), hd("조사 지점"), hd("우려기준 초과"), hd("대책기준 초과")])
        for l in lands:
            rows.append([l, cnt[l][0], cnt[l][1], 0])
        rows.append([hd("합계"), sum(v[0] for v in cnt.values()), sum(v[1] for v in cnt.values()), 0])
        path = self.p(self.src, TEAM["토양"], "토양오염실태조사_2026.xlsx")
        write_xlsx(path, [s1, {"name": "지목별집계", "rows": rows, "widths": [16, 10, 12, 12]}])
        self.data["soil"] = {"lands": lands, "cnt": cnt}
        # 6) 먹는물 검사 실적
        wtypes = ["수돗물", "지하수(민방위 비상급수)", "먹는샘물", "약수터"]
        rows = title_rows("2026년 먹는물 수질검사 월별 실적", "단위: 건")
        rows.append([hd("월")] + [hd(t) for t in wtypes] + [hd("계")])
        tot = [0] * 4
        for m in range(1, 10):
            r = [rng.randint(52, 75), rng.randint(14, 26), rng.randint(6, 13), rng.randint(9, 24)]
            tot = [a + b for a, b in zip(tot, r)]
            rows.append([f"{m}월"] + r + [sum(r)])
        rows.append([hd("누계")] + tot + [sum(tot)])
        s1 = {"name": "월별실적", "rows": rows, "widths": [8, 9, 22, 10, 9, 9]}
        unfit = [3, 4, 0, 7]
        rows = title_rows("부적합 현황(1~9월)", "")
        rows.append([hd("구분"), hd("검사"), hd("부적합"), hd("주요 부적합 항목")])
        for t, a, u, item in zip(wtypes, tot, unfit, ["잔류염소", "총대장균군, 질산성질소", "-", "총대장균군, 일반세균"]):
            rows.append([t, a, u, item])
        path = self.p(self.src, TEAM["먹는물"], "먹는물_수질검사_실적_2026.xlsx")
        write_xlsx(path, [s1, {"name": "부적합", "rows": rows, "widths": [22, 8, 8, 24]}])
        self.data["water"] = {"types": wtypes, "tot": tot, "unfit": unfit}
        # 7) 세출예산 집행현황 2026 (원 단위)
        progs = ["시험분석 장비 운영", "하천 수질측정망 운영", "대기측정망 운영", "토양 실태조사", "먹는물 검사",
                 "악취 관리 지원", "연구원 시설 유지관리", "직원 역량 강화"]
        budget, spent = {}, {}
        for pg in progs:
            b = rng.randint(180, 2600) * 1_000_000 + rng.randint(0, 999) * 1000 + rng.choice([0, 0, 500])
            budget[pg] = b
            spent[pg] = int(b * rng.uniform(0.62, 0.93) // 10 * 10)
        spent["하천 수질측정망 운영"] = int(budget["하천 수질측정망 운영"] * 0.7964 // 10 * 10)
        rows = title_rows("2026년 세출예산 집행현황(9. 30. 기준)", "단위: 원")
        rows.append([hd(h) for h in ["세부사업", "예산현액", "지출액", "집행잔액", "집행률"]])
        for pg in progs:
            rows.append([pg, num(budget[pg], "#,##0"), num(spent[pg], "#,##0"), num(budget[pg] - spent[pg], "#,##0"),
                         num(spent[pg] / budget[pg], "0.0%")])
        B, Sp = sum(budget.values()), sum(spent.values())
        rows.append([hd("합계"), num(B, "#,##0"), num(Sp, "#,##0"), num(B - Sp, "#,##0"), num(Sp / B, "0.0%")])
        path = self.p(self.src, TEAM["운영"], "2026_세출예산_집행현황.xlsx")
        write_xlsx(path, [{"name": "집행현황", "rows": rows, "widths": [22, 16, 16, 16, 9]}])
        self.data["budget"] = {"progs": progs, "budget": budget, "spent": spent, "rate": Sp / B * 100}
        # 8) 2025 결산
        rows = title_rows("2025년 세출예산 결산", "단위: 원")
        rows.append([hd(h) for h in ["세부사업", "예산현액", "지출액(12월말)", "지출액(9월말)", "9월말 집행률"]])
        b25, s25, q25 = {}, {}, {}
        for pg in progs:
            b = int(budget[pg] * rng.uniform(0.9, 1.05) // 1000 * 1000)
            b25[pg] = b
            s25[pg] = int(b * rng.uniform(0.95, 0.995))
            q25[pg] = int(b * rng.uniform(0.6, 0.82))
            rows.append([pg, num(b, "#,##0"), num(s25[pg], "#,##0"), num(q25[pg], "#,##0"), num(q25[pg] / b, "0.0%")])
        B25, Q25 = sum(b25.values()), sum(q25.values())
        rows.append([hd("합계"), num(B25, "#,##0"), num(sum(s25.values()), "#,##0"), num(Q25, "#,##0"), num(Q25 / B25, "0.0%")])
        path = self.p(self.src, TEAM["운영"], "2025_세출예산_결산.xlsx")
        write_xlsx(path, [{"name": "결산", "rows": rows, "widths": [22, 16, 16, 16, 12]}])
        self.data["budget"]["rate25"] = Q25 / B25 * 100
        # 9) 인력 현황
        jobs = [("환경연구사", 38, 35), ("보건연구사", 21, 20), ("환경직", 9, 8), ("행정직", 12, 12), ("공무직", 12, 12)]
        rows = title_rows("직렬별 인력 현황(2026. 9. 30.)", "단위: 명")
        rows.append([hd("직렬"), hd("정원"), hd("현원"), hd("결원"), hd("비고")])
        for j, a, b in jobs:
            rows.append([j, a, b, a - b, ""])
        rows.append([hd("합계"), sum(x[1] for x in jobs), sum(x[2] for x in jobs), sum(x[1] - x[2] for x in jobs), ""])
        path = self.p(self.src, TEAM["운영"], "인력현황_2026-09.xlsx")
        write_xlsx(path, [{"name": "직렬별", "rows": rows, "widths": [14, 8, 8, 8, 16]}])
        self.data["staff"] = jobs
        # 10) 장비 보유 현황
        cats = ["크로마토그래피", "분광분석기", "질량분석기", "미생물 분석장비", "전처리 장비", "현장 측정장비"]
        rows = title_rows("주요 시험장비 보유 현황(2026. 9. 30.)", "")
        rows.append([hd(h) for h in ["관리번호", "장비명", "분류", "취득일", "취득가(원)", "내용연수", "경과 여부"]])
        cc = {c: [0, 0] for c in cats}
        for i in range(146):
            c = rng.choices(cats, weights=[22, 18, 8, 14, 20, 18])[0]
            y = rng.randint(2009, 2025)
            life = rng.choice([8, 10, 12])
            over = (2026 - y) > life
            rows.append([f"EQ-{i + 1:04d}", f"{c} {rng.randint(1, 9)}호기", c, f"{y}-{rng.randint(1, 12):02d}-15",
                         num(rng.randint(8, 420) * 1_000_000, "#,##0"), life, "경과" if over else "-"])
            cc[c][0] += 1
            cc[c][1] += 1 if over else 0
        s1 = {"name": "장비목록", "rows": rows, "widths": [10, 22, 16, 12, 14, 8, 9], "freeze": (3, 0)}
        rows = title_rows("분류별 집계", "단위: 대")
        rows.append([hd("분류"), hd("보유"), hd("내용연수 경과")])
        for c in cats:
            rows.append([c] + cc[c])
        rows.append([hd("합계"), sum(v[0] for v in cc.values()), sum(v[1] for v in cc.values())])
        path = self.p(self.src, TEAM["운영"], "주요장비_보유현황.xlsx")
        write_xlsx(path, [s1, {"name": "분류별집계", "rows": rows, "widths": [18, 8, 14]}])
        self.data["equip"] = {"cats": cats, "cc": cc}
        # 11) 시험·검사 실적 종합
        fields = ["먹는물", "수질", "대기", "토양·폐기물", "기타(의뢰 시험)"]
        perf = {}
        for f_, base in zip(fields, [3150, 2850, 1720, 780, 410]):
            a24 = int(base * rng.uniform(0.9, 1.0))
            a25 = int(base * rng.uniform(0.95, 1.05))
            q25 = int(a25 * 0.74)
            q26 = int(q25 * rng.uniform(1.04, 1.18))
            perf[f_] = (a24, a25, q25, q26)
        rows = title_rows("분야별 시험·검사 실적", "단위: 건")
        rows.append([hd("분야"), hd("2024년"), hd("2025년"), hd("2025년 1~9월"), hd("2026년 1~9월")])
        for f_ in fields:
            rows.append([f_] + list(perf[f_]))
        rows.append([hd("합계")] + [sum(perf[f_][i] for f_ in fields) for i in range(4)])
        path = self.p(self.src, TEAM["운영"], "시험검사_실적_종합_2024-2026.xlsx")
        write_xlsx(path, [{"name": "분야별", "rows": rows, "widths": [16, 10, 10, 13, 13]}])
        self.data["perf"] = {"fields": fields, "perf": perf}
        # 12) 정보공개
        res = ["전부 공개", "부분 공개", "비공개", "정보 부존재", "취하·종결"]
        rows = title_rows("2026년 정보공개청구 처리 현황", "단위: 건")
        rows.append([hd("처리 결과"), hd("1분기"), hd("2분기"), hd("3분기"), hd("계")])
        info = {}
        for rr in res:
            q = [rng.randint(2, 19) for _ in range(3)]
            info[rr] = q + [sum(q)]
            rows.append([rr] + info[rr])
        rows.append([hd("합계")] + [sum(info[r][i] for r in res) for i in range(4)])
        path = self.p(self.src, "정보공개", "정보공개청구_처리현황_2026.xlsx")
        write_xlsx(path, [{"name": "분기별", "rows": rows, "widths": [14, 8, 8, 8, 8]}])
        self.data["info"] = {"res": res, "info": info}

        # 나중에 받은 수정 자료(원본 변경 시연)
        path = self.p(self.later, "하천수질_측정결과_2026.xlsx")
        write_xlsx(path, self.river(modified=True))
        self.river()  # 원래 값으로 되돌려 둠

    # ════════════════════════════════════════════════
    #  2. 표 내용(팀 제출본·취합본 공통)
    # ════════════════════════════════════════════════
    def t_perf(self, err=False):
        d = self.data["perf"]
        rows = [["분야", "2024년", "2025년", "2026년(1~9월)"]]
        for f_ in d["fields"]:
            a24, a25, q25, q26 = d["perf"][f_]
            rows.append([f_, f0(a24), f0(a25), f0(q26)])
        tot = [sum(d["perf"][f_][i] for f_ in d["fields"]) for i in (0, 1, 3)]
        if err:
            tot[1] += 90        # E2: 2025년 합계 잘못 입력
        rows.append([{"t": "합계", "total": True}] + [f0(x) for x in tot])
        return rows

    def t_river(self, err=False):
        d = self.data["river"]
        order = ["HB-06", "HB-07", "HB-01", "HB-02", "HB-03", "HB-05"]
        name = {c: n for c, n, _ in d["sites"]}
        rows = [["측정지점", "BOD", "TOC", "SS", "총질소", "총인"]]
        for c in order:
            m = d["mean"]
            r = [name[c], fmtd(m[(c, "BOD")], 1), fmtd(m[(c, "TOC")], 1), fmtd(m[(c, "SS")], 1),
                 fmtd(m[(c, "T-N")], 2), fmtd(m[(c, "T-P")], 3)]
            if err and c == "HB-03":
                r[1] = "3.2"          # E1: 2.3 → 3.2 자리 바뀜
            rows.append(r)
        return rows

    def t_req(self):
        d = self.data["req"]
        rows = [["의뢰기관", "접수 건수", "수수료(천원)"]]
        for c in d["cities"]:
            a = d["agg"][c]
            rows.append([c, f0(a[0]), f0(r_half(a[2] / 1000, 0))])
        rows.append([{"t": "합계", "total": True}, f0(sum(v[0] for v in d["agg"].values())),
                     f0(r_half(sum(v[2] for v in d["agg"].values()) / 1000, 0))])
        return rows

    def t_air(self, team_err=True):
        d = self.data["air"]
        sts = d["stations"]
        rows = [["구분"] + sts]
        r10 = ["PM10 평균(㎍/㎥)"] + [fmtd(d["avg"][("PM10", s)], 1) for s in sts]
        if team_err:
            r10[3] = "41.0"           # E7a: 대기팀이 41.0으로 잘못 적음(엑셀은 다른 값) → 취합본도 그대로 복사
        r25 = ["PM2.5 평균(㎍/㎥)"] + [fmtd(d["avg"][("PM2.5", s)], 1) for s in sts]
        b10 = ["PM10 나쁨 일수"] + [str(d["bad"][s][0]) for s in sts]
        b25 = ["PM2.5 나쁨 일수"] + [str(d["bad"][s][1]) for s in sts]
        return [rows[0], r10, r25, b10, b25]

    def t_odor(self):
        o = self.data["odor"]
        rows = [["구분", "2024년", "2025년", "2026년(1~9월)"]]
        for i, lab in enumerate(["접수", "처리 완료", "처리 중"]):
            rows.append([lab, str(o["2024"][i]), str(o["2025"][i]), str(o["2026(1~9월)"][i])])
        return rows

    def t_soil(self, err=False):
        d = self.data["soil"]
        rows = [["지목", "조사 지점 수", "우려기준 초과"]]
        for l in d["lands"]:
            a, b = d["cnt"][l]
            if err and l == "주유소":
                b = 5                 # E7b: 팀 문서는 3, 취합본에서 5로 옮겨 적음
            rows.append([l, str(a), str(b)])
        rows.append([{"t": "합계", "total": True}, str(sum(v[0] for v in d["cnt"].values())),
                     str(sum(v[1] for v in d["cnt"].values()))])
        return rows

    def t_water(self):
        d = self.data["water"]
        rows = [["구분", "검사 건수", "부적합 건수", "부적합률(%)"]]
        for t, a, u in zip(d["types"], d["tot"], d["unfit"]):
            rows.append([t, f0(a), str(u), fmtd(u / a * 100, 1)])
        A, U = sum(d["tot"]), sum(d["unfit"])
        rows.append([{"t": "합계", "total": True}, f0(A), str(U), fmtd(U / A * 100, 1)])
        return rows

    def t_budget(self, err=False):
        d = self.data["budget"]
        rows = [["세부사업", "예산액(천원)", "집행액(천원)", "집행률(%)"]]
        for pg in d["progs"]:
            b, s = d["budget"][pg], d["spent"][pg]
            r = [pg, f0(r_half(b / 1000, 0)), f0(r_half(s / 1000, 0)), fmtd(s / b * 100, 1)]
            if err and pg == "대기측정망 운영":
                r[2] = f"{s:,}"       # E3: 원 단위를 그대로 붙여 넣음
            if err and pg == "하천 수질측정망 운영":
                r[3] = "82.1"         # E14: 집행률 잘못 입력(실제 79.6)
            rows.append(r)
        B, S = sum(d["budget"].values()), sum(d["spent"].values())
        rows.append([{"t": "합계", "total": True}, f0(r_half(B / 1000, 0)), f0(r_half(S / 1000, 0)), fmtd(S / B * 100, 1)])
        return rows

    def t_staff(self):
        rows = [["직렬", "정원", "현원", "결원"]]
        for j, a, b in self.data["staff"]:
            rows.append([j, str(a), str(b), str(a - b)])
        js = self.data["staff"]
        rows.append([{"t": "합계", "total": True}, str(sum(x[1] for x in js)), str(sum(x[2] for x in js)),
                     str(sum(x[1] - x[2] for x in js))])
        return rows

    def t_equip(self):
        d = self.data["equip"]
        main = d["cats"][:4]
        rest = d["cats"][4:]
        rows = [["분류", "보유(대)", "내용연수 경과(대)"]]
        for c in main:
            rows.append([c, str(d["cc"][c][0]), str(d["cc"][c][1])])
        rows.append(["기타(전처리·현장)", str(sum(d["cc"][c][0] for c in rest)), str(sum(d["cc"][c][1] for c in rest))])
        rows.append([{"t": "합계", "total": True}, str(sum(v[0] for v in d["cc"].values())),
                     str(sum(v[1] for v in d["cc"].values()))])
        return rows

    def t_info(self):
        d = self.data["info"]
        rows = [["처리 결과", "건수"]]
        for r in d["res"]:
            rows.append([r, str(d["info"][r][3])])
        rows.append([{"t": "합계", "total": True}, str(sum(d["info"][r][3] for r in d["res"]))])
        return rows

    # ── 본문 문장 ──
    def s_perf(self):
        d = self.data["perf"]
        q26 = sum(d["perf"][f][3] for f in d["fields"])
        q25 = sum(d["perf"][f][2] for f in d["fields"])
        pct = (q26 - q25) / q25 * 100
        return f"2026년 1~9월 시험·검사 실적은 총 {q26:,}건으로 전년 동기({q25:,}건) 대비 {fmtd(pct, 1)}% 증가하였음"

    def s_odor(self, err=False):
        o = self.data["odor"]
        a, b = o["2026(1~9월)"][0], o["2025(1~9월)"][0]
        pct = abs(a - b) / b * 100
        shown = "15.3" if err else fmtd(pct, 1)   # E4: 증감률 잘못 기재
        return f"2026년 1~9월 악취 민원은 {a}건으로 전년 동기({b}건) 대비 {shown}% 감소하였음"

    def s_budget(self):
        d = self.data["budget"]
        a, b = r_half(d["rate"], 1), r_half(d["rate25"], 1)
        return f"9월 말 기준 세출예산 집행률은 {a:.1f}%로 전년 동기({b:.1f}%) 대비 {abs(a - b):.1f}%p {'상승' if a >= b else '하락'}하였음"

    # ════════════════════════════════════════════════
    #  3. 팀 제출본
    # ════════════════════════════════════════════════
    def build_team_docs(self):
        W = {"river": [3, 2, 2, 2, 2, 2], "air": [4] + [2] * 6}
        # 수질분석팀
        b = HwpxBuilder("수질분석팀 행정사무감사 요구자료 답변")
        b.title("2026년 행정사무감사 요구자료 답변(수질분석팀)")
        b.blank()
        b.heading("□ 요구자료 2. 2026년 주요 하천 수질 측정 결과")
        b.body("주요 하천 6개 지점의 1~9월 평균 수질은 아래와 같음")
        b.note("(단위: mg/L)")
        b.table(self.t_river(), widths=W["river"])
        b.note("※ 자료: 하천수질 측정결과(2026. 1.~9.), 산술평균")
        b.blank()
        b.heading("□ 요구자료 10. 시군별 수질검사 의뢰 접수 현황")
        b.table(self.t_req(), widths=[3, 2, 2])
        b.save(self.p(self.team, "수질분석팀_요구자료_답변.hwpx"))
        # 대기환경팀
        b = HwpxBuilder("대기환경팀 행정사무감사 요구자료 답변")
        b.title("2026년 행정사무감사 요구자료 답변(대기환경팀)")
        b.blank()
        b.heading("□ 요구자료 3. 대기오염측정망 측정 결과(2026. 1.~9.)")
        b.table(self.t_air(team_err=True), widths=W["air"])
        b.note("※ 나쁨 일수: 일평균 PM10 81㎍/㎥, PM2.5 36㎍/㎥ 초과일")
        b.blank()
        b.heading("□ 요구자료 8. 악취 민원 처리 현황")
        b.body(self.s_odor(err=False))
        b.table(self.t_odor(), widths=[3, 2, 2, 3])
        b.save(self.p(self.team, "대기환경팀_요구자료_답변.hwpx"))
        # 토양폐기물팀
        b = HwpxBuilder("토양폐기물팀 행정사무감사 요구자료 답변")
        b.title("2026년 행정사무감사 요구자료 답변(토양폐기물팀)")
        b.blank()
        b.heading("□ 요구자료 4. 토양오염 실태조사 결과")
        b.body("도내 120개 지점을 조사한 결과 우려기준 초과 지점은 아래와 같음")
        b.table(self.t_soil(err=False), widths=[3, 2, 2])
        b.save(self.p(self.team, "토양폐기물팀_요구자료_답변.hwpx"))
        # 먹는물검사팀
        b = HwpxBuilder("먹는물검사팀 행정사무감사 요구자료 답변")
        b.title("2026년 행정사무감사 요구자료 답변(먹는물검사팀)")
        b.blank()
        b.heading("□ 요구자료 11. 먹는물 수질검사 및 부적합 현황(2026. 1.~9.)")
        b.table(self.t_water(), widths=[4, 2, 2, 2])
        b.save(self.p(self.team, "먹는물검사팀_요구자료_답변.hwpx"))
        # 운영지원팀
        b = HwpxBuilder("운영지원팀 행정사무감사 요구자료 답변")
        b.title("2026년 행정사무감사 요구자료 답변(운영지원팀)")
        b.blank()
        b.heading("□ 요구자료 1. 최근 3년간 분야별 시험·검사 실적")
        b.body(self.s_perf())
        b.table(self.t_perf(err=False), widths=[3, 2, 2, 2])
        b.blank()
        b.heading("□ 요구자료 5. 2026년 세출예산 집행 현황(9. 30. 기준)")
        b.body(self.s_budget())
        b.table(self.t_budget(err=False), widths=[4, 2, 2, 2], left_cols=(0,))
        b.blank()
        b.heading("□ 요구자료 6. 직렬별 인력 현황")
        b.table(self.t_staff(), widths=[3, 2, 2, 2])
        b.blank()
        b.heading("□ 요구자료 7. 주요 시험장비 보유 현황")
        b.table(self.t_equip(), widths=[4, 2, 3])
        b.blank()
        b.heading("□ 요구자료 9. 정보공개청구 처리 현황")
        b.table(self.t_info(), widths=[3, 2])
        b.save(self.p(self.team, "운영지원팀_요구자료_답변.hwpx"))

    # ════════════════════════════════════════════════
    #  4. 취합본(오류 심음) + 작성틀
    # ════════════════════════════════════════════════
    def fake_count(self):
        """원본 어디에도 없는 숫자를 고른다(출처 미확인 시연용)."""
        from app.formats.xlsx import read_xlsx
        seen = set()
        for dp, _, fs in os.walk(self.src):
            for f in fs:
                wb = read_xlsx(os.path.join(dp, f))
                for s in wb.sheets:
                    for c in s.cells.values():
                        if c.kind == "n":
                            seen.add(round(c.v, 6))
        from app.formats.hwpx import HwpxDoc
        for dp, _, fs in os.walk(self.team):
            for f in fs:
                for it in HwpxDoc(os.path.join(dp, f)).items:
                    if it.value is not None:
                        seen.add(round(it.value, 6))
        for x in range(23, 99):
            if float(x) not in seen:
                return x
        return 97

    def build_collected(self):
        W = {"river": [3, 2, 2, 2, 2, 2], "air": [4] + [2] * 6}
        fake = self.fake_count()
        b = HwpxBuilder("2026년 행정사무감사 요구자료(취합본)")
        b.title("2026년도 행정사무감사 요구자료")
        b.text(f"{ORG} / {COUNCIL} 제출")
        b.blank()
        b.heading("□ 개요")
        b.body("감사 일시: 2026. 11. 25.(목) 10:00, 도의회 제2회의실")        # E5: 실제 수요일
        b.body("자료 제출 기한: 2026. 11. 11.(수)까지 위원회 제출")              # 정상
        b.body(f"올해 고농도 미세먼지 비상저감조치는 총 {fake}회 발령되었음")     # E8: 출처 없음
        b.blank()
        b.heading("□ 요구자료 1. 최근 3년간 분야별 시험·검사 실적")
        b.body(self.s_perf())
        b.note("(단위: 건)")
        b.table(self.t_perf(err=True), widths=[3, 2, 2, 2])                     # T0
        b.blank()
        b.heading("□ 요구자료 2. 2026년 주요 하천 수질 측정 결과")
        b.note("(단위: mg/L, 1~9월 평균)")
        b.table(self.t_river(err=True), widths=W["river"])                      # T1
        b.blank()
        b.heading("□ 요구자료 3. 대기오염측정망 측정 결과(2026. 1.~9.)")
        b.table(self.t_air(team_err=True), widths=W["air"])                     # T2
        b.blank()
        b.heading("□ 요구자료 4. 토양오염 실태조사 결과")
        b.table(self.t_soil(err=True), widths=[3, 2, 2])                        # T3
        b.blank()
        b.heading("□ 요구자료 5. 2026년 세출예산 집행 현황(9. 30. 기준)")
        b.body(self.s_budget())
        b.table(self.t_budget(err=True), widths=[4, 2, 2, 2], left_cols=(0,))   # T4
        b.blank()
        b.heading("□ 요구자료 6. 직렬별 인력 현황")
        b.table(self.t_staff(), widths=[3, 2, 2, 2])                            # T5
        b.blank()
        b.heading("□ 요구자료 7. 주요 시험장비 보유 현황")
        b.table(self.t_equip(), widths=[4, 2, 3])                               # T6
        b.blank()
        b.heading("□ 요구자료 8. 악취 민원 처리 현황")
        b.body(self.s_odor(err=True))
        b.table(self.t_odor(), widths=[3, 2, 2, 3])                             # T7
        b.blank()
        b.heading("□ 요구자료 9. 정보공개청구 처리 현황")
        b.table(self.t_info(), widths=[3, 2])                                   # T8
        b.blank()
        b.heading("□ 요구자료 10. 시군별 수질검사 의뢰 접수 현황")
        b.table(self.t_req(), widths=[3, 2, 2])                                 # T9
        b.blank()
        b.heading("□ 요구자료 11. 먹는물 수질검사 및 부적합 현황")
        b.table(self.t_water(), widths=[4, 2, 2, 2])                            # T10
        path = b.save(self.p(self.coll, "2026_행정사무감사_요구자료_취합본.hwpx"))

        d = self.data
        bd = d["budget"]
        sname = d["air"]["stations"][2]
        self.answers = [
            {"id": "E1", "구분": "옮겨 적기 오류", "표": 1, "행": "은하천 하류", "열": "BOD", "문서값": "3.2",
             "기대": ["mismatch"], "정답": fmtd(d["river"]["mean"][("HB-03", "BOD")], 1),
             "설명": "엑셀 연평균 2.338(표시 2.3)을 3.2로 잘못 적음"},
            {"id": "E2", "구분": "합계 오류", "표": 0, "행": "합계", "열": "2025년", "기대": ["calc", "mismatch"],
             "설명": "2025년 합계를 90건 많게 적음(각 분야 합과 다름)"},
            {"id": "E3", "구분": "단위 혼동", "표": 4, "행": "대기측정망 운영", "열": "집행액(천원)", "기대": ["unit"],
             "설명": "천원 단위 표에 원 단위 값을 그대로 붙여 넣음"},
            {"id": "E3-연쇄", "구분": "연쇄 표시", "표": 4, "행": "합계", "열": "집행액(천원)", "기대": ["calc", "ok", "single"],
             "설명": "E3 때문에 합계가 칸 합과 맞지 않음(정상적인 연쇄 표시)", "연쇄": True},
            {"id": "E3-연쇄2", "구분": "연쇄 표시", "표": 4, "행": "대기측정망 운영", "열": "집행률(%)", "기대": ["calc", "ok", "single"],
             "설명": "E3 때문에 집행률 재계산이 맞지 않음(정상적인 연쇄 표시)", "연쇄": True},
            {"id": "E14", "구분": "옮겨 적기 오류", "표": 4, "행": "하천 수질측정망 운영", "열": "집행률(%)",
             "기대": ["mismatch", "calc"], "설명": "실제 79.6%를 82.1%로 적음"},
            {"id": "E4", "구분": "증감률 오류", "본문": "악취 민원", "문서값": "15.3", "기대": ["calc"],
             "설명": f"({d['odor']['2026(1~9월)'][0]}-{d['odor']['2025(1~9월)'][0]})÷{d['odor']['2025(1~9월)'][0]} = 11.4% 감소"},
            {"id": "E5", "구분": "요일 오류", "요일": "11. 25.(목)", "기대": ["weekday"], "설명": "2026. 11. 25.은 수요일"},
            {"id": "E7a", "구분": "출처 간 충돌", "표": 2, "행": "PM10 평균(㎍/㎥)", "열": sname, "문서값": "41.0",
             "기대": ["conflict"], "정답": fmtd(d["air"]["avg"][("PM10", sname)], 1),
             "설명": "대기팀 제출본(41.0)과 원본 엑셀이 다름 → 담당자가 골라야 함"},
            {"id": "E7b", "구분": "옮겨 적기 오류", "표": 3, "행": "주유소", "열": "우려기준 초과", "문서값": "5",
             "기대": ["mismatch"], "정답": "3", "설명": "팀 제출본·엑셀 모두 3"},
            {"id": "E7b-연쇄", "구분": "연쇄 표시", "표": 3, "행": "합계", "열": "우려기준 초과", "기대": ["calc", "ok", "single"],
             "설명": "E7b 때문에 합계와 칸 합이 다름", "연쇄": True},
            {"id": "E8", "구분": "출처 없는 숫자", "본문": "비상저감조치", "문서값": str(fake), "기대": ["unknown"],
             "설명": "어느 원본에도 없는 숫자"},
            {"id": "N1", "구분": "정상(반올림)", "표": 1, "행": "은하천 중류", "열": "총질소", "기대": ["ok"], "정상": True,
             "설명": "2.3455 → 2.35 반올림은 정상"},
            {"id": "N2", "구분": "정상(단위 환산)", "표": 9, "행": "가온시", "열": "수수료(천원)", "기대": ["ok"], "정상": True,
             "설명": "원 → 천원 환산은 정상"},
            {"id": "N3", "구분": "정상(행·열 뒤바뀜)", "표": 2, "행": "PM2.5 평균(㎍/㎥)", "열": d["air"]["stations"][0],
             "기대": ["ok"], "정상": True, "설명": "엑셀은 측정소가 행, 문서는 측정소가 열"},
            {"id": "N4", "구분": "정상(머리글 다름)", "표": 1, "행": "가람강 합류전", "열": "총인", "기대": ["ok"], "정상": True,
             "단계2기대": ["conflict", "mismatch"], "설명": "엑셀은 지점코드·T-P, 문서는 지점명·총인"},
            {"id": "N5", "구분": "정상(합산값)", "표": 6, "행": "기타(전처리·현장)", "열": "보유(대)",
             "기대": ["unknown", "single", "multi", "ok"], "정상": True, "설명": "두 분류를 더한 값 — 원본에 그대로 없으므로 '출처 미확인'이 맞음"},
            {"id": "E6", "구분": "원본 변경(시연 2단계)", "표": 1, "행": "가람강 합류전", "열": "총인", "기대": ["ok"],
             "단계2기대": ["conflict", "mismatch"],
             "설명": "수질팀 수정본에서 0.085 → 0.092로 바뀜. 팀 제출본(0.085)과 새 엑셀(0.092)이 달라 '충돌'로 표시"},
        ]
        return path

    def build_blank_form(self):
        W = {"river": [3, 2, 2, 2, 2, 2], "air": [4] + [2] * 6}
        b = HwpxBuilder("2026년 행정사무감사 요구자료 작성틀(수질·대기)")
        b.title("2026년도 행정사무감사 요구자료 — 작성틀")
        b.text("※ 빈 칸에 원본 엑셀 값을 [입력하기]로 채우면 출처가 함께 기록됩니다")
        b.blank()
        b.heading("□ 요구자료 2. 2026년 주요 하천 수질 측정 결과")
        b.note("(단위: mg/L, 1~9월 평균)")
        rows = [r[:1] + [""] * 5 for r in self.t_river()]
        rows[0] = self.t_river()[0]
        b.table(rows, widths=W["river"])
        b.blank()
        b.heading("□ 요구자료 3. 대기오염측정망 측정 결과(2026. 1.~9.)")
        rows = [r[:1] + [""] * 6 for r in self.t_air(team_err=False)]
        rows[0] = self.t_air()[0]
        b.table(rows, widths=W["air"])
        b.blank()
        b.heading("□ 요구자료 8. 악취 민원 처리 현황")
        b.body("2026년 1~9월 악취 민원은 ○○건으로 전년 동기(○○건) 대비 ○○% 감소하였음")
        b.save(self.p(self.coll, "2026_행정사무감사_요구자료_작성틀(수질·대기).hwpx"))

    # ════════════════════════════════════════════════
    def extras(self):
        later = os.path.join("나중에_받은_자료", "하천수질_측정결과_2026.xlsx")
        tgt = os.path.join("공유폴더(가상)", "2026 행정사무감사", "01_원본자료", TEAM["수질"], "하천수질_측정결과_2026.xlsx")
        keep = os.path.join("나중에_받은_자료", "_처음_원본_보관", "하천수질_측정결과_2026.xlsx")
        os.makedirs(os.path.join(self.out, os.path.dirname(keep)), exist_ok=True)
        shutil.copy2(os.path.join(self.out, tgt), os.path.join(self.out, keep))
        bat = ("@echo off\r\nchcp 65001 >nul\r\ncd /d \"%~dp0\"\r\n"
               f"copy /Y \"{later}\" \"{tgt}\" >nul\r\n"
               "echo [시연] 수질분석팀이 수정한 엑셀로 원본을 바꿨습니다.\r\n"
               "echo 프로그램에서 [원본 변경 확인]을 눌러 보세요.\r\npause\r\n")
        open(os.path.join(self.out, "시연_2단계_원본변경_재현.bat"), "w", encoding="utf-8").write(bat)
        bat2 = ("@echo off\r\nchcp 65001 >nul\r\ncd /d \"%~dp0\"\r\n"
                f"copy /Y \"{keep}\" \"{tgt}\" >nul\r\n"
                "echo [시연] 원본 엑셀을 처음 상태로 되돌렸습니다.\r\npause\r\n")
        open(os.path.join(self.out, "시연_원본_되돌리기.bat"), "w", encoding="utf-8").write(bat2)
        sh = ("#!/bin/sh\ncd \"$(dirname \"$0\")\"\n"
              f"cp \"{later}\" \"{tgt}\" && echo '[시연] 원본을 수정본으로 바꿨습니다.'\n")
        p = os.path.join(self.out, "시연_2단계_원본변경_재현.command")
        open(p, "w", encoding="utf-8").write(sh)
        os.chmod(p, 0o755)
        sh2 = ("#!/bin/sh\ncd \"$(dirname \"$0\")\"\n"
               f"cp \"{keep}\" \"{tgt}\" && echo '[시연] 원본을 되돌렸습니다.'\n")
        p = os.path.join(self.out, "시연_원본_되돌리기.command")
        open(p, "w", encoding="utf-8").write(sh2)
        os.chmod(p, 0o755)
        with open(os.path.join(self.out, "정답표.json"), "w", encoding="utf-8") as f:
            json.dump({"설명": "시연 취합본에 일부러 심은 오류와 정상 사례. 표 번호는 문서 안 순서(0부터).",
                       "대상": "공유폴더(가상)/2026 행정사무감사/03_취합/2026_행정사무감사_요구자료_취합본.hwpx",
                       "항목": self.answers}, f, ensure_ascii=False, indent=1)

    def compat(self):
        """한글 호환성 점검 파일(사람이 한글에서 열어 확인)."""
        from app.formats.hwpx import HwpxDoc
        d = os.path.join(self.out, "한글_호환성_점검")
        os.makedirs(d, exist_ok=True)
        b = HwpxBuilder("한글 호환성 점검")
        b.title("한글 호환성 점검 문서")
        b.blank()
        b.heading("□ 점검 문단")
        b.body("본문 숫자 예시: 실적은 총 1,234건으로 전년(1,100건) 대비 12.2% 증가하였음")
        b.note("※ 이 문서는 프로그램이 만든 시험용 문서입니다")
        b.table([["구분", "2025년", "2026년"], ["가", "10", "12"], ["나", "20.5", "21.0"], [{"t": "합계", "total": True}, "30.5", "33.0"]],
                widths=[3, 2, 2])
        p1 = b.save(os.path.join(d, "점검1_기본_문단과표.hwpx"))
        doc = HwpxDoc(p1)
        doc.make_fields()
        p2 = doc.save(os.path.join(d, "점검2_누름틀.hwpx"))
        doc = HwpxDoc(p2)
        doc.set_field(doc.items[0].key, "9,999")
        p3 = doc.save(os.path.join(d, "점검3_값바꾸기.hwpx"))
        doc = HwpxDoc(p2)
        doc.mark(doc.items[0].key, "red")
        doc.mark(doc.items[3].key, "yellow")
        doc.save(os.path.join(d, "점검4_색표시.hwpx"))
        txt = ("한글 호환성 점검 방법 (각 파일을 한글에서 열어 확인하고 결과를 알려 주세요)\r\n\r\n"
               "점검1_기본_문단과표.hwpx : 제목·문단·표가 깨지지 않고 열리는가\r\n"
               "점검2_누름틀.hwpx       : 숫자를 누르면 누름틀(빨간 기울임 안내문이 있는 입력칸)로 동작하는가,\r\n"
               "                          [보기]-[조판 부호]를 켜면 숫자 앞뒤에 누름틀 표시가 보이는가\r\n"
               "점검3_값바꾸기.hwpx     : 본문의 1,234가 9,999로 바뀌어 보이는가\r\n"
               "점검4_색표시.hwpx       : 본문 첫 숫자가 빨간 굵은 글씨, 표 안 한 칸이 노란 배경인가\r\n")
        open(os.path.join(d, "점검방법.txt"), "w", encoding="utf-8").write(txt)

    def run(self):
        if os.path.exists(self.out):
            shutil.rmtree(self.out)
        os.makedirs(self.out)
        self.build_sources()
        self.build_team_docs()
        self.build_collected()
        self.build_blank_form()
        self.compat()
        self.extras()
        return self.out


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), "시연자료")
    d = Demo(out).run()
    n = sum(len(fs) for _, _, fs in os.walk(d))
    print(f"시연 자료 생성 완료: {d}  (파일 {n}개)")


if __name__ == "__main__":
    main()
