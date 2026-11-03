"""
수원시 자원회수시설 반입량 - AJAX(POST) 직접 호출 방식 (2025년 1~12월, 월간)
- 엔드포인트: https://www.rrfsuwon.co.kr/_Skin/24_1.php (POST)
- 결과 컬럼: 일자, 반입량(톤), 소각량(톤), 바닥재(톤), 비산재(톤), 비고
- 결과: suwon_rrf_output/ 아래 월별 CSV + 2025년 전체 합본 CSV

사전 준비:
    pip install requests beautifulsoup4 pandas
"""

import re
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

MAIN_URL = "https://www.rrfsuwon.co.kr/?p=24"
AJAX_URL = "https://www.rrfsuwon.co.kr/_Skin/24_1.php"
TARGET_YEAR = 2025
OUT_DIR = Path("suwon_rrf_output")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": MAIN_URL,
    "Origin": "https://www.rrfsuwon.co.kr",
    "Accept": "text/html, */*; q=0.01",
}

COLUMNS = ["일자", "반입량(톤)", "소각량(톤)", "바닥재(톤)", "비산재(톤)", "비고"]
DATE_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")


def build_payload(month: int) -> dict:
    """개발자 도구에서 확인한 Payload 그대로 사용 (월간 조회)"""
    return {
        "gubun": "mon",
        "sYear": str(TARGET_YEAR),
        "sMonth": str(month),
        "sDate": "",
        "eDate": "",
    }


def fetch_month(session: requests.Session, month: int) -> str:
    resp = session.post(AJAX_URL, data=build_payload(month), headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def parse_rows(html: str) -> pd.DataFrame:
    """응답 HTML에서 '2026.11.01' 형태의 일자 행만 골라 표로 만든다.
    헤더가 2단(바닥재/비산재가 소각재처리량 아래)이라 고정 컬럼명을 사용한다."""
    soup = BeautifulSoup(html, "lxml")
    records = []
    for tr in soup.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or not DATE_RE.match(cells[0]):
            continue
        cells = (cells + [""] * len(COLUMNS))[: len(COLUMNS)]   # 빈 칸 보정
        records.append(cells)
    return pd.DataFrame(records, columns=COLUMNS)


def to_number(s: pd.Series) -> pd.Series:
    """'34.820' -> 34.82, '' / '-' -> NaN"""
    return pd.to_numeric(s.str.replace(",", "", regex=False)
                          .replace({"-": None, "": None}), errors="coerce")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    frames = []

    with requests.Session() as session:
        session.headers.update(HEADERS)
        session.get(MAIN_URL, timeout=30)          # 세션 쿠키(PHPSESSID) 획득

        for month in range(1, 13):
            ym = f"{TARGET_YEAR}-{month:02d}"
            html = fetch_month(session, month)
            df = parse_rows(html)

            if df.empty:
                print(f"[{ym}] 일자 행을 찾지 못했습니다.")
                continue

            # 숫자 컬럼 변환 (원본 값은 보존하고 싶다면 이 블록을 지우세요)
            for col in ["반입량(톤)", "소각량(톤)", "바닥재(톤)", "비산재(톤)"]:
                df[col] = to_number(df[col])

            df.insert(0, "조회연월", ym)
            df.to_csv(OUT_DIR / f"{ym}.csv", index=False, encoding="utf-8-sig")
            frames.append(df)
            print(f"[{ym}] 저장 완료: {len(df)}행")

    if frames:
        merged = pd.concat(frames, ignore_index=True)
        merged.to_csv(OUT_DIR / f"{TARGET_YEAR}_전체.csv", index=False, encoding="utf-8-sig")
        print(f"합본 저장 완료: {len(merged)}행")
    else:
        print("수집된 데이터가 없습니다.")


if __name__ == "__main__":
    main()
