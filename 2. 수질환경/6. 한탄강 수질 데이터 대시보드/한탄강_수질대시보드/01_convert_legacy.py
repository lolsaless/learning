"""
01_convert_legacy.py
기존 '월별 시트(YYYYMM)' 형식의 한탄강 수계 수질결과 엑셀을
대시보드용 표준 DB 엑셀(한탄강_수질DB.xlsx)로 변환한다.

사용법
    python 01_convert_legacy.py  원본.xlsx  [출력.xlsx]

- 원본의 'YYYYMM' 이름 시트를 모두 읽어 '측정결과' 한 장(1행 = 1지점·1회 채취)으로 합친다.
- '연도별 평균색도' 시트가 있으면 '연평균색도' 시트로 옮긴다.
- 지점정보(좌표 포함)·항목정보·기준값 시트를 함께 만든다.
- 이미 출력 파일이 있으면 지점정보/항목정보/기준값(사용자가 고친 값)은 유지하고
  측정결과만 원본 기준으로 다시 채운다.
"""
import re
import sys
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

ITEMS = ["TOC", "COD", "BOD", "SS", "T-N", "T-P", "색도"]

# ── 기본 메타데이터 ───────────────────────────────────────────
ITEM_INFO = [
    # 항목, 표시명, 단위, 소수자리, 설명
    ("TOC", "총유기탄소(TOC)", "mg/L", 2, "하천 생활환경기준 등급 판정 항목"),
    ("COD", "화학적산소요구량(COD)", "mg/L", 1, "일부 지점만 분석"),
    ("BOD", "생물화학적산소요구량(BOD)", "mg/L", 1, "하천 생활환경기준 등급 판정 항목"),
    ("SS", "부유물질(SS)", "mg/L", 1, "하천 생활환경기준 등급 판정 항목"),
    ("T-N", "총질소(T-N)", "mg/L", 3, "하천 기준 없음(참고)"),
    ("T-P", "총인(T-P)", "mg/L", 3, "하천 생활환경기준 등급 판정 항목"),
    ("색도", "색도", "도", 0, "목표 기준(아래 기준값 시트) 대비 달성 여부"),
]

GRADES = ["매우좋음", "좋음", "약간좋음", "보통", "약간나쁨", "나쁨", "매우나쁨"]
GRADE_CODE = ["Ia", "Ib", "II", "III", "IV", "V", "VI"]
# 하천 생활환경기준(환경정책기본법 시행령 별표1) 상한값. 마지막 등급(VI)은 상한 없음
GRADE_LIMITS = {
    "BOD": [1, 2, 3, 5, 8, 10],
    "TOC": [2, 3, 4, 5, 6, 8],
    "SS": [25, 25, 25, 25, 100, None],
    "T-P": [0.02, 0.04, 0.1, 0.2, 0.3, 0.5],
}
COLOR_TARGET = 15  # 원본 '목표기준 달성여부' 판정과 일치하는 값(연평균 ≤15도 → 달성)

# 수계 묶음
BASIN = {
    "한탄강": "한탄강 본류",
    "포천천": "영평천 수계", "금현천": "영평천 수계", "송우천": "영평천 수계",
    "영평천": "영평천 수계", "외북천": "영평천 수계", "수입천": "영평천 수계",
    "신천": "신천 수계", "능안천": "신천 수계", "효촌천": "신천 수계", "덕계천": "신천 수계",
    "마개미천": "신천 수계", "회암천": "신천 수계", "청담천": "신천 수계", "상패천": "신천 수계",
}

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from coords import COORDS  # 추정 좌표
except Exception:  # noqa: BLE001
    COORDS = {}

# ── 스타일 ───────────────────────────────────────────────────
HEAD_FILL = PatternFill("solid", fgColor="1F4E5A")
HEAD_FONT = Font(name="맑은 고딕", bold=True, color="FFFFFF", size=10)
BODY_FONT = Font(name="맑은 고딕", size=10)
NOTE_FILL = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="C9D3D6")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def num(v):
    """'7.3 ', '<0.5', '-' 같은 값을 숫자로. 정량한계 미만은 None 처리 후 표시값 보존."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in ("", "-", "—"):
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def clean_river(name):
    return re.sub(r"^\d+\)\s*", "", str(name)).strip() if name else None


def read_legacy(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    rows, stations, order = [], {}, []
    month_sheets = sorted([ws for ws in wb.worksheets if re.fullmatch(r"\d{6}", ws.title)],
                          key=lambda w: w.title)
    for ws in month_sheets:
        ym = f"{ws.title[:4]}-{ws.title[4:]}"
        # 헤더 행 찾기
        hdr_row = None
        for r in range(1, 8):
            vals = [str(c.value).strip() if c.value else "" for c in ws[r]]
            if "시료번호" in vals:
                hdr_row, hdr = r, vals
                break
        if not hdr_row:
            print(f"[경고] {ws.title}: 헤더(시료번호)를 찾지 못해 건너뜀")
            continue
        col = {h: i for i, h in enumerate(hdr) if h}
        river = None
        for r in ws.iter_rows(min_row=hdr_row + 1, values_only=True):
            st = r[col["시료번호"]]
            if not st:
                continue
            st = str(st).strip()
            if r[col["하천명"]]:
                river = clean_river(r[col["하천명"]])
            addr = r[col.get("주 소", col.get("주소", 3))]
            date = r[col["시료채취일"]] if "시료채취일" in col else None
            note = r[len(hdr) - 1] if len(r) >= len(hdr) else None
            if st not in stations:
                order.append(st)
                stations[st] = {"하천명": river, "주소": str(addr).strip() if addr else "", "비고": ""}
            if note and str(note).strip() in ("변경지점", "신규지점"):
                stations[st]["비고"] = str(note).strip()
            rec = {"조사연월": ym, "채취일": date if isinstance(date, datetime) else None, "지점명": st}
            for it in ITEMS:
                rec[it] = num(r[col[it]]) if it in col else None
            rows.append(rec)
    # 연도별 평균색도
    yearly = []
    if "연도별 평균색도" in wb.sheetnames:
        ws = wb["연도별 평균색도"]
        hdr = [c.value for c in ws[2]]
        years = [(i, int(h)) for i, h in enumerate(hdr) if isinstance(h, (int, float))]
        river = None
        for r in ws.iter_rows(min_row=3, values_only=True):
            if not r[2]:
                continue
            if r[1]:
                river = clean_river(r[1])
            for i, y in years:
                v = num(r[i])
                if v is not None:
                    yearly.append({"지점명": str(r[2]).strip(), "하천명": river, "주소": str(r[3] or "").strip(),
                                   "연도": y, "평균색도": round(v, 2), "구간": (r[12] or "") if len(r) > 12 else ""})
    return rows, stations, order, yearly


def flag_repeats(rows):
    """직전 달과 5개 항목 이상이 완전히 같으면 '검토필요' 표시 (복사 입력 의심)."""
    by = {}
    for r in rows:
        by[(r["지점명"], r["조사연월"])] = r
    for r in rows:
        y, m = map(int, r["조사연월"].split("-"))
        prev = f"{y - (m == 1)}-{(m - 2) % 12 + 1:02d}"
        p = by.get((r["지점명"], prev))
        if not p:
            continue
        same = [it for it in ITEMS if r[it] is not None and r[it] == p[it]]
        if len(same) >= 4:
            r["검토표시"] = "검토필요"
            r["비고"] = f"전월({prev})과 동일: {', '.join(same)}"


def style_sheet(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for c in ws[1]:
        c.fill, c.font, c.border = HEAD_FILL, HEAD_FONT, BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 24
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font, c.border = BODY_FONT, BORDER
    ws.freeze_panes = "A2"


def add_table(ws, name, style="TableStyleLight9"):
    ref = f"A1:{get_column_letter(ws.max_column)}{max(ws.max_row, 2)}"
    t = Table(displayName=name, ref=ref)
    t.tableStyleInfo = TableStyleInfo(name=style, showRowStripes=True)
    ws.add_table(t)


def load_existing_meta(out):
    """기존 DB 파일이 있으면 사용자가 수정한 지점정보/항목정보/기준값을 보존."""
    if not Path(out).exists():
        return None
    wb = openpyxl.load_workbook(out, data_only=True)
    keep = {}
    for sn in ("지점정보", "항목정보", "기준값"):
        if sn in wb.sheetnames:
            ws = wb[sn]
            hdr = [c.value for c in ws[1]]
            keep[sn] = [dict(zip(hdr, r)) for r in ws.iter_rows(min_row=2, values_only=True) if any(r)]
    return keep


def build(src, out):
    rows, stations, order, yearly = read_legacy(src)
    for r in rows:
        r.setdefault("검토표시", "")
        r.setdefault("비고", "")
    flag_repeats(rows)
    meas_years = {int(r["조사연월"][:4]) for r in rows}
    yearly = [y for y in yearly if y["연도"] not in meas_years]  # 측정결과가 있는 연도는 대시보드가 직접 계산
    old = load_existing_meta(out)

    wb = openpyxl.Workbook()

    # 1) 안내
    ws = wb.active
    ws.title = "안내"
    guide = [
        ("한탄강 수계 수질 DB", ""),
        ("", ""),
        ("시트", "용도 / 입력 규칙"),
        ("측정결과", "1행 = 1지점 1회 채취. 매월 지점 수만큼 행을 아래에 추가. 지점명은 '지점정보'의 지점명과 정확히 같아야 함(드롭다운 제공)."),
        ("", "조사연월은 YYYY-MM 형식(예: 2026-10). 값이 없으면 비워 둠('-' 입력 금지). 숫자 셀에는 숫자만 입력."),
        ("", "검토표시 = '검토필요'로 적으면 대시보드에서 점선 테두리로 구분 표시됨."),
        ("지점정보", "지점 추가·변경 시 여기에 한 줄 추가. 정렬순서 = 그래프·표 표시 순서(상류→하류). 위도/경도는 지도 위치."),
        ("", "좌표상태가 '추정'인 지점은 주소로 추정한 값이므로 현장 GPS 좌표로 바꾸고 '확인'으로 변경 권장."),
        ("항목정보", "단위·소수자리·기본 선 색상(HEX) 설정. 색상은 대시보드에서도 바꿀 수 있음."),
        ("기준값", "하천 생활환경기준 등급 상한값과 색도 목표값. 대시보드 기준선·등급 판정에 사용."),
        ("연평균색도", "과거 연도별 평균 색도(2019~). 대시보드 '연도별 색도' 화면에 사용. 연말에 해당 연도 행 추가."),
        ("", ""),
        ("갱신 방법", "① 이 파일 '측정결과'에 새 달 데이터 추가 → ② 02_build_dashboard.py 실행(더블클릭: 대시보드_만들기.bat) → ③ 생성된 HTML 열기"),
    ]
    for g in guide:
        ws.append(g)
    ws["A1"].font = Font(name="맑은 고딕", bold=True, size=14, color="1F4E5A")
    for r in ws.iter_rows(min_row=3, max_row=ws.max_row):
        r[0].font = Font(name="맑은 고딕", bold=True, size=10)
        r[1].font = Font(name="맑은 고딕", size=10)
        r[1].alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 110

    # 2) 측정결과
    ws = wb.create_sheet("측정결과")
    cols = ["조사연월", "채취일", "지점명"] + ITEMS + ["검토표시", "비고"]
    ws.append(cols)
    for r in rows:
        ws.append([r["조사연월"], r["채취일"], r["지점명"]] + [r[it] for it in ITEMS] + [r["검토표시"], r["비고"]])
    style_sheet(ws, [10, 12, 12, 8, 8, 8, 8, 8, 8, 8, 10, 40])
    for row in ws.iter_rows(min_row=2):
        row[1].number_format = "yyyy-mm-dd"
        for c in row[3:10]:
            c.number_format = "General"
            c.alignment = Alignment(horizontal="right")
        if row[10].value:
            for c in row:
                c.fill = NOTE_FILL
    add_table(ws, "측정결과")
    dv = DataValidation(type="list", formula1="=지점정보!$C$2:$C$200", allow_blank=False,
                        error="지점정보 시트에 등록된 지점명만 입력할 수 있습니다.", showErrorMessage=True)
    dv.add("C2:C20000")
    ws.add_data_validation(dv)
    dv2 = DataValidation(type="list", formula1='"검토필요"', allow_blank=True)
    dv2.add("K2:K20000")
    ws.add_data_validation(dv2)

    # 3) 지점정보
    ws = wb.create_sheet("지점정보")
    scols = ["정렬순서", "지점ID", "지점명", "하천명", "수계", "시군", "주소", "위도", "경도", "좌표상태", "비고"]
    ws.append(scols)
    old_st = {r["지점명"]: r for r in (old or {}).get("지점정보", [])}
    for i, st in enumerate(order, 1):
        if st in old_st:
            o = old_st[st]
            ws.append([o.get(c) for c in scols])
            continue
        meta = stations[st]
        river = meta["하천명"]
        addr = meta["주소"]
        sigun = addr.split()[0] if addr else ""
        lat, lon = COORDS.get(st, (None, None))
        note = meta["비고"]
        if "목표지점" in addr:
            note = (note + " " if note else "") + "색도 목표지점"
            addr = addr.replace("_색도 목표지점", "")
        ws.append([i, f"S{i:02d}", st, river, BASIN.get(river, "기타"), sigun, addr, lat, lon,
                   "추정" if lat else "미입력", note])
    style_sheet(ws, [8, 8, 12, 10, 12, 9, 52, 10, 10, 9, 18])
    add_table(ws, "지점정보", "TableStyleLight11")

    # 4) 항목정보
    ws = wb.create_sheet("항목정보")
    ws.append(["항목", "표시명", "단위", "소수자리", "설명"])
    old_it = (old or {}).get("항목정보")
    if old_it:
        for o in old_it:
            ws.append([o.get(c) for c in ["항목", "표시명", "단위", "소수자리", "설명"]])
    else:
        for it in ITEM_INFO:
            ws.append(list(it))
    style_sheet(ws, [8, 26, 8, 9, 46])
    add_table(ws, "항목정보", "TableStyleLight11")

    # 5) 기준값
    ws = wb.create_sheet("기준값")
    ws.append(["항목", "구분", "등급코드", "등급명", "상한값", "비고"])
    old_lim = (old or {}).get("기준값")
    if old_lim:
        for o in old_lim:
            ws.append([o.get(c) for c in ["항목", "구분", "등급코드", "등급명", "상한값", "비고"]])
    else:
        for it, lims in GRADE_LIMITS.items():
            for code, gname, lim in zip(GRADE_CODE, GRADES, lims + [None]):
                ws.append([it, "생활환경기준", code, gname, lim, "상한 없음" if lim is None else ""])
        ws.append(["색도", "목표", "-", "목표", COLOR_TARGET, "연평균 이하이면 달성(원본 판정과 일치하도록 설정, 확인 필요)"])
    style_sheet(ws, [8, 12, 9, 10, 9, 56])
    add_table(ws, "기준값", "TableStyleLight11")

    # 6) 연평균색도
    ws = wb.create_sheet("연평균색도")
    ws.append(["지점명", "하천명", "주소", "연도", "평균색도", "구간"])
    for y in yearly:
        ws.append([y["지점명"], y["하천명"], y["주소"], y["연도"], y["평균색도"], y["구간"]])
    style_sheet(ws, [14, 10, 56, 8, 10, 22])
    add_table(ws, "연평균색도", "TableStyleLight11")

    wb.save(out)
    n_flag = sum(1 for r in rows if r["검토표시"])
    months = sorted({r["조사연월"] for r in rows})
    print(f"[완료] {out}")
    print(f"  측정결과 {len(rows)}행 · 지점 {len(order)}개 · 기간 {months[0]} ~ {months[-1]}")
    print(f"  검토필요 표시 {n_flag}행 · 연평균색도 {len(yearly)}행")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else str(Path(src).with_name("한탄강_수질DB.xlsx"))
    build(src, out)
