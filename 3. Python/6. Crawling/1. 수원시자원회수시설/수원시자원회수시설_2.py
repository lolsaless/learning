"""
수원시 자원회수시설 반입량 - AJAX(POST) 방식 (월간 조회, 기간 설정 가능)
- 시작 연월 ~ 종료 연월을 설정하면 해당 기간을 월별로 수집
- 한 달을 받는 즉시 CSV 파일로 저장 (전체 데이터를 메모리에 쌓지 않음)
- 이미 저장된 월은 건너뛰므로 중간에 멈춰도 다시 실행하면 이어서 수집됨

사전 준비:
    pip install requests beautifulsoup4 lxml pandas
"""

import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ══════════════════════════════════════════════════════════
#  ★ 조회 기간 설정 (여기만 바꾸면 됩니다)
# ══════════════════════════════════════════════════════════
START_YEAR, START_MONTH = 2015, 1      # 수집 시작: 2015년 1월
END_YEAR, END_MONTH = None, None       # 수집 종료: None이면 이번 달까지
#                                        예) 2020년 12월까지 → END_YEAR, END_MONTH = 2020, 12

OUT_DIR = Path("수원시자원회수시설")     # CSV 저장 폴더
SKIP_EXISTING = True                   # True: 이미 저장된 월은 건너뜀
REQUEST_INTERVAL = 1.0                 # 요청 사이 대기 시간(초) - 서버 부담 줄이기
RETRY = 3                              # 오류 시 재시도 횟수

# ══════════════════════════════════════════════════════════
MAIN_URL = "https://www.rrfsuwon.co.kr/?p=24"
AJAX_URL = "https://www.rrfsuwon.co.kr/_Skin/24_1.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": MAIN_URL,
    "Origin": "https://www.rrfsuwon.co.kr",
    "Accept": "text/html, */*; q=0.01",
}

COLUMNS = ["일자", "반입량(톤)", "소각량(톤)", "바닥재(톤)", "비산재(톤)", "비고"]
NUMERIC_COLUMNS = ["반입량(톤)", "소각량(톤)", "바닥재(톤)", "비산재(톤)"]


def month_range(start_y: int, start_m: int, end_y: int, end_m: int):
    """시작 연월부터 종료 연월까지 (연도, 월) 쌍을 하나씩 만들어 준다."""
    y, m = start_y, start_m
    while (y, m) <= (end_y, end_m):
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def build_payload(year: int, month: int) -> dict:
    """개발자 도구에서 확인한 페이로드 그대로 (월간 조회)"""
    return {
        "gubun": "mon",
        "sYear": str(year),
        "sMonth": str(month),
        "sDate": "",
        "eDate": "",
    }


def fetch_month(session: requests.Session, year: int, month: int) -> str:
    """해당 연월의 응답 HTML을 받아온다."""
    resp = session.post(AJAX_URL, data=build_payload(year, month), headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def parse_rows(html: str) -> pd.DataFrame:
    """응답 HTML에서 '2026.11.01' 형태의 일자 행만 골라 표로 만든다."""
    soup = BeautifulSoup(html, "lxml")
    records = []
    for tr in soup.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or not _is_date(cells[0]):
            continue
        cells = (cells + [""] * len(COLUMNS))[: len(COLUMNS)]
        records.append(cells)
    return pd.DataFrame(records, columns=COLUMNS)


def _is_date(text: str) -> bool:
    """'2026.11.01' 형식인지 확인"""
    parts = text.split(".")
    return len(parts) == 3 and all(p.isdigit() for p in parts) and len(parts[0]) == 4


def clean_numbers(df: pd.DataFrame) -> pd.DataFrame:
    """'34.820' → 34.82, 빈 칸·'-' → NaN 으로 변환"""
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(
            df[col].str.replace(",", "", regex=False).replace({"-": None, "": None}),
            errors="coerce",
        )
    return df


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    today = date.today()
    end_y = END_YEAR or today.year
    end_m = END_MONTH or today.month
    months = list(month_range(START_YEAR, START_MONTH, end_y, end_m))
    print(f"수집 기간: {START_YEAR}-{START_MONTH:02d} ~ {end_y}-{end_m:02d} (총 {len(months)}개월)")

    show_preview = True

    with requests.Session() as session:
        session.headers.update(HEADERS)
        session.get(MAIN_URL, timeout=30)           # 세션 쿠키 획득

        for year, month in months:
            ym = f"{year}-{month:02d}"
            path = OUT_DIR / f"{ym}.csv"

            if SKIP_EXISTING and path.exists():
                print(f"[{ym}] 이미 저장됨 - 건너뜀")
                continue

            html = None
            for attempt in range(1, RETRY + 1):
                try:
                    html = fetch_month(session, year, month)
                    break
                except Exception as e:
                    print(f"[{ym}] 시도 {attempt} 실패: {e}")
                    time.sleep(REQUEST_INTERVAL * attempt * 2)

            if html is None:
                print(f"[{ym}] 최종 실패 - 건너뜀")
                continue

            if show_preview:
                print("--- 응답 미리보기 (첫 달) ---")
                print(html[:300])
                print("-----------------------------")
                show_preview = False

            df = parse_rows(html)
            if df.empty:
                print(f"[{ym}] 일자 데이터 없음 (해당 월 자료가 없거나 구조가 다름)")
            else:
                df = clean_numbers(df)
                df.insert(0, "조회연월", ym)
                df.to_csv(path, index=False, encoding="utf-8-sig")   # 받은 즉시 저장
                print(f"[{ym}] 저장 완료: {len(df)}행 → {path}")

            time.sleep(REQUEST_INTERVAL)

    print("\n모든 작업 완료.")


if __name__ == "__main__":
    main()
