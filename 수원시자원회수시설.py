# -*- coding: utf-8 -*-
"""
rrfsuwon.co.kr 크롤러 - 2025년 1월~12월 표 데이터 수집
"""
import time
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ================= 설정 =================
URL = "https://www.rrfsuwon.co.kr/?p=24"
YEAR = 2025
MONTHS = range(1, 13)
HEADLESS = True                 # 디버깅 시 False
OUT_DIR = Path("output_2025")
WAIT_SEC = 1.0
PAUSE_SEC = 1.0

# ================= XPath =================
FORM = "/html/body/div[1]/div[4]/div/div[2]/div[1]/div[2]/div[2]/div/form/fieldset"
XPATH_TYPE_SELECT  = f"{FORM}/select[1]"    # 월간 (첫 번째 옵션)
XPATH_YEAR_SELECT  = f"{FORM}/select[2]"
XPATH_MONTH_SELECT = f"{FORM}/select[3]"
XPATH_BODY         = "/html/body/div[1]/div[4]/div/div[2]/div[1]/div[2]/div[3]"
XPATH_TABLE        = f"{XPATH_BODY}/table"
XPATH_SUBMIT       = None                   # 조회 버튼이 있으면 XPath 입력

# 표 열 (thead 기준: 일자 | 반입량 | 소각량 | 소각재처리량(바닥재, 비산재) | 비고)
COLUMNS = ["일자", "반입량", "소각량", "소각재처리량_바닥재", "소각재처리량_비산재", "비고"]
NUMERIC_COLS = ["반입량", "소각량", "소각재처리량_바닥재", "소각재처리량_비산재"]


def select_by_number(select_loc, number: int, suffix: str):
    """옵션 텍스트에서 숫자를 찾아 선택. '2025', '2025년', '1월', '01월' 모두 매칭."""
    opts = select_loc.locator("option")
    for i in range(opts.count()):
        text = opts.nth(i).inner_text().strip().replace(suffix, "").strip()
        try:
            if int(text) == number:
                select_loc.select_option(index=i)
                return
        except ValueError:
            continue
    raise ValueError(f"옵션 '{number}{suffix}'을(를) 찾지 못했습니다.")


def read_table_rows(page):
    """tbody의 각 tr에서 td/th 텍스트를 리스트로 반환 (rowspan/colspan 영향 없음)."""
    return page.evaluate(
        """(xp) => {
            const tbl = document.evaluate(xp, document, null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (!tbl) return null;
            return Array.from(tbl.querySelectorAll(':scope > tbody > tr')).map(
                tr => Array.from(tr.children).map(c => c.innerText.trim()));
        }""",
        XPATH_TABLE,
    )


def to_num(s: str):
    """'34.820' -> 34.82, '-' or '' -> None"""
    s = s.replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return s


def parse_rows(raw_rows):
    """원본 행 -> 정제된 dict 리스트"""
    records = []
    for cells in raw_rows or []:
        if not cells or not cells[0]:
            continue
        if len(cells) != len(COLUMNS):
            print(f"  [경고] 열 개수 불일치({len(cells)}개), 건너뜀: {cells}")
            continue
        rec = dict(zip(COLUMNS, cells))
        for c in NUMERIC_COLS:
            rec[c] = to_num(rec[c])
        rec["일자"] = pd.to_datetime(rec["일자"], format="%Y.%m.%d", errors="coerce")
        records.append(rec)
    return records


def crawl_one(page, year: int, month: int):
    """한 달치 표 데이터를 조회해 레코드 리스트 반환."""
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector(f"xpath={XPATH_BODY}", timeout=30000)

    # 1) 월간 (첫 번째 옵션)
    page.locator(f"xpath={XPATH_TYPE_SELECT}").select_option(index=0)
    # 2) 년도
    select_by_number(page.locator(f"xpath={XPATH_YEAR_SELECT}"), year, "년")
    # 3) 월
    select_by_number(page.locator(f"xpath={XPATH_MONTH_SELECT}"), month, "월")

    # 기존 첫 행 기록 (변경 감지용)
    before = page.evaluate(
        """(xp) => {
            const tr = document.evaluate(xp + '/tbody/tr[1]', document, null,
                       XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            return tr ? tr.innerText : '';
        }""", XPATH_TABLE)

    # 4) 조회 버튼 (필요한 경우)
    if XPATH_SUBMIT:
        page.locator(f"xpath={XPATH_SUBMIT}").click()

    # 5) 표 내용이 바뀔 때까지 대기 (바뀌지 않으면 현재 상태로 진행)
    try:
        page.wait_for_function(
            """([xp, before]) => {
                const tr = document.evaluate(xp + '/tbody/tr[1]', document, null,
                           XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                return tr && tr.innerText !== before;
            }""",
            arg=[XPATH_TABLE, before],
            timeout=10000,
        )
    except PWTimeout:
        pass

    page.wait_for_load_state("networkidle")
    time.sleep(WAIT_SEC)

    raw = read_table_rows(page)
    if raw is None:
        raise RuntimeError("표(table)를 찾지 못했습니다.")
    return parse_rows(raw)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    summary, all_records = [], []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(locale="ko-KR")
        page = context.new_page()

        for m in MONTHS:
            ym = f"{YEAR}-{m:02d}"
            try:
                records = crawl_one(page, YEAR, m)
                status = "ok"
                for r in records:
                    r["년"] = YEAR
                    r["월"] = m
                all_records.extend(records)
                if records:
                    pd.DataFrame(records).to_csv(
                        OUT_DIR / f"{ym}.csv", index=False, encoding="utf-8-sig")
            except Exception as e:
                records = []
                status = f"error: {e}"
                try:
                    page.screenshot(path=str(OUT_DIR / f"error_{ym}.png"))
                except Exception:
                    pass

            summary.append({"year": YEAR, "month": m, "status": status, "rows": len(records)})
            print(f"[{ym}] {status} | 행 {len(records)}개")
            time.sleep(PAUSE_SEC)

        browser.close()

    pd.DataFrame(summary).to_csv(OUT_DIR / "summary.csv", index=False, encoding="utf-8-sig")
    if all_records:
        pd.DataFrame(all_records).to_csv(
            OUT_DIR / f"all_{YEAR}.csv", index=False, encoding="utf-8-sig")
    print(f"\n완료: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()