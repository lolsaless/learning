# -*- coding: utf-8 -*-
"""화면 시험(Playwright): 시연 시작 → 검증 → 고치기 → 입력하기 → 저장 → 이력 → 내보내기.
실행: python app/server.py --no-browser 를 켠 뒤  python tests/e2e_ui.py [화면저장폴더]"""
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
    pg.on("dialog", lambda d: d.accept())
    pg.goto("http://127.0.0.1:8765/")
    pg.wait_for_selector("#demoCard button")
    pg.click("text=시연 처음부터 다시"); pg.click("#askModal button.pri")
    pg.wait_for_selector("#toast div:has-text('준비 완료')", timeout=30000)
    pg.screenshot(path=f"{OUT}/1_준비.png", full_page=True)
    pg.click("text=검증 실행 →")
    pg.wait_for_selector("#docView .num", timeout=20000)
    time.sleep(0.5)
    pg.screenshot(path=f"{OUT}/2_검증.png")
    chips = pg.inner_text("#chips"); print("칩:", chips.replace("\n", " "))
    # 불일치 칸 누르기
    pg.click("#docView .num.st-mismatch >> nth=0"); pg.wait_for_selector("#detail .src"); time.sleep(0.4)
    pg.screenshot(path=f"{OUT}/3_불일치_상세.png")
    pg.click("#detail button.pri >> nth=0"); time.sleep(0.6)
    # 충돌 칸
    pg.click("#docView .num.st-conflict >> nth=0"); pg.wait_for_selector("#detail .src"); time.sleep(0.4)
    pg.screenshot(path=f"{OUT}/4_충돌_상세.png")
    pg.click("#detail .src.dis button >> nth=0"); time.sleep(0.6)
    # 문제만 보기
    pg.click(".chip >> nth=1"); time.sleep(0.3)
    pg.screenshot(path=f"{OUT}/5_문제만.png")
    pg.click(".chip >> nth=0")
    # 입력하기: 표2 은하천 중류 BOD 칸에 엑셀 연평균 셀을 넣어 보기(값은 같지만 출처가 붙음)
    pg.click("#tabs button[data-p=input]"); pg.wait_for_selector("#docView2 .num")
    pg.click('#docView2 .num[data-k="표2_은하천중류_BOD"]')
    pg.select_option("#inSrc", label=[o for o in pg.eval_on_selector_all("#inSrc option", "os=>os.map(o=>o.textContent)") if "하천수질" in o][0])
    time.sleep(0.4); pg.select_option("#inSheet", "연평균"); pg.wait_for_selector("#gridWrap td[data-r]")
    # HB-02 행(엑셀 5행 = index 4) BOD 열(E열 = index 4) ~ TOC(G=6)까지 끌기 → BOD, COD, TOC 세 칸... 문서는 BOD,TOC,SS 순서
    pg.select_option("#inDec", "1")
    a = pg.locator('#gridWrap td[data-r="4"][data-c="4"]'); a.hover(); pg.mouse.down(); a.hover(); pg.mouse.up()
    pg.screenshot(path=f"{OUT}/6_입력하기.png")
    pg.click("#p-input .bar button.pri")
    pg.wait_for_selector("#toast div:has-text('출처만 확정')", timeout=5000)
    # 여러 칸 입력: 은하천 하류 행(HB-03, 엑셀 6행) BOD 한 칸을 고쳐 넣기 → 3.2 → 2.3
    pg.click('#docView2 .num[data-k="표2_은하천하류_BOD"]')
    a = pg.locator('#gridWrap td[data-r="5"][data-c="4"]'); a.hover(); pg.mouse.down(); a.hover(); pg.mouse.up()
    pg.click("#p-input .bar button.pri")
    time.sleep(0.8)
    pg.screenshot(path=f"{OUT}/7_입력후.png")
    print("대기:", pg.inner_text("#pendN2"))
    # 저장
    pg.click("#p-input button:has-text('저장(새 버전)')"); pg.wait_for_selector("#askModal.on"); time.sleep(0.3)
    pg.screenshot(path=f"{OUT}/8_저장확인.png")
    pg.click("#askModal button.pri"); time.sleep(1.5)
    print("헤더:", pg.inner_text("#hdmeta"))
    # 이력
    pg.click("#tabs button[data-p=hist]"); pg.wait_for_selector("#histT tr >> nth=1"); time.sleep(0.4)
    pg.screenshot(path=f"{OUT}/9_이력.png", full_page=True)
    # 원본 변경 시연
    pg.evaluate("api('/api/demo/stage2',{})"); time.sleep(0.4)
    pg.click("#tabs button[data-p=prep]"); pg.click("text=원본 변경 확인"); pg.wait_for_selector("#askModal.on"); time.sleep(0.3)
    pg.screenshot(path=f"{OUT}/10_원본변경.png")
    pg.click("#askModal button.pri"); pg.wait_for_selector("#banners .banner"); time.sleep(0.8)
    pg.screenshot(path=f"{OUT}/11_변경후검증.png")
    # 내보내기
    pg.click("button:has-text('내보내기')"); pg.wait_for_selector("#askModal.on"); time.sleep(0.3)
    pg.screenshot(path=f"{OUT}/12_내보내기.png")
    pg.click("#askModal button.pri")
    pg.evaluate("api('/api/demo/restore',{})")
    pg.click("#tabs button[data-p=conf]"); time.sleep(0.4)
    pg.screenshot(path=f"{OUT}/13_설정.png", full_page=True)
    b.close()
print("화면 오류:", errs or "없음")
