# -*- coding: utf-8 -*-
"""화면 시험(Playwright): 5. 시연자료(만들기·채점·이 자료로 시연·일괄 평가) → 6. 구성도.
실행: python app/main.py --no-browser 를 켠 뒤  python tests/e2e_mock.py [화면저장폴더]"""
import sys, os, time
from playwright.sync_api import sync_playwright
OUT = sys.argv[1] if len(sys.argv) > 1 else "e2e_shots"
os.makedirs(OUT, exist_ok=True)
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 950})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto("http://127.0.0.1:8765/")
    pg.wait_for_selector("#demoCard button")
    pg.click("#tabs button[data-p=mock]"); pg.wait_for_selector("#mkKinds input")
    pg.fill("#mkSeed", "777"); pg.select_option("#mkSize", "보통"); pg.fill("#mkErr", "12")
    pg.click("#mkBtn"); pg.wait_for_selector("#mkList td button", timeout=30000); time.sleep(0.4)
    print("만들기:", pg.inner_text("#mkMsg"))
    pg.screenshot(path=f"{OUT}/m1_만들기.png", full_page=True)
    row = pg.locator("#mkList tr", has_text="_777")
    row.locator("button:has-text('채점')").click(); pg.wait_for_selector("#mkScoreT tr >> nth=2"); time.sleep(0.4)
    print("채점:", pg.inner_text("#mkScoreSum").replace("\n", " "))
    pg.screenshot(path=f"{OUT}/m2_채점.png", full_page=True)
    row.locator("button:has-text('이 자료로 시연')").click(); pg.click("#askModal button.pri")
    pg.wait_for_selector("#docView .num", timeout=30000); time.sleep(0.6)
    print("검증 칩:", pg.inner_text("#chips").replace("\n", " "))
    pg.screenshot(path=f"{OUT}/m3_무작위자료_검증.png")
    pg.click("#tabs button[data-p=mock]"); pg.wait_for_selector("#evN")
    pg.fill("#evN", "6"); pg.fill("#evSeed", "31000"); pg.click("#evBtn")
    pg.wait_for_selector("#evOut .chips", timeout=60000); time.sleep(0.4)
    print("일괄 평가:", pg.inner_text("#evOut .chips").replace("\n", " "))
    pg.screenshot(path=f"{OUT}/m4_일괄평가.png", full_page=True)
    pg.click("#tabs button[data-p=map]"); pg.wait_for_selector(".comp"); time.sleep(0.3)
    pg.click(".comp[data-id=P3]"); pg.wait_for_selector("#mapDetail .src"); time.sleep(0.3)
    pg.screenshot(path=f"{OUT}/m5_구성도.png")
    print("구성도 상자:", pg.locator(".comp").count())
    b.close()
print("화면 오류:", errs or "없음")
