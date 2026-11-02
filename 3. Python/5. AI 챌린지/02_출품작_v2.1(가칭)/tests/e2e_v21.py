# -*- coding: utf-8 -*-
"""화면 시험(v2.1 추가 기능): AI 설정(시험용 모의 AI) → AI 로 문장 읽기 → 검증 요약 → 다시 받은 파일 비교.
실행: 프로그램을 켠 뒤(python app/main.py --no-browser)  python tests/e2e_v21.py [화면저장폴더]
끝나면 AI 설정을 '사용 안 함'으로 되돌린다."""
import os
import sys
import glob
import time
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else "e2e_shots_v21"
os.makedirs(OUT, exist_ok=True)
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 950})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto("http://127.0.0.1:8765/")
    pg.wait_for_selector("#demoCard button")
    pg.click("text=시연 처음부터 다시"); pg.click("#askModal button.pri")
    pg.wait_for_selector("#toast div:has-text('준비 완료')", timeout=30000)
    pg.click("text=검증 실행 →"); pg.wait_for_selector("#docView .num", timeout=20000)
    # AI 설정
    pg.click("#tabs button[data-p=conf]"); pg.wait_for_selector("#aiKind option", state="attached")
    pg.select_option("#aiKind", "mock")
    pg.evaluate("saveAi()"); time.sleep(0.5)
    pg.evaluate("testAi()"); pg.wait_for_selector("#aiSt:has-text('연결됨')", timeout=10000)
    print("AI 설정:", pg.inner_text("#aiSt"))
    pg.screenshot(path=f"{OUT}/1_AI설정.png")
    # AI 로 문장 읽기
    pg.click("#tabs button[data-p=check]"); pg.wait_for_selector("#docView .num")
    pg.click("#btnAiRead"); pg.wait_for_selector("#toast div:has-text('AI 읽기')", timeout=30000)
    print("AI 읽기:", pg.inner_text("#toast div:has-text('AI 읽기') >> nth=0"))
    pg.screenshot(path=f"{OUT}/2_AI읽기.png")
    # 요약
    pg.click("text=검증 요약 만들기"); pg.wait_for_selector("#askModal.on"); time.sleep(0.4)
    body = pg.inner_text("#askB"); print("요약:", body.splitlines()[:3])
    assert "규칙 요약" in body
    pg.screenshot(path=f"{OUT}/3_요약.png"); pg.click("#askModal button.pri")
    # 다시 받은 파일 비교(파일 고르기 창 대신 고른 결과를 바로 넘김)
    new = [f for f in sorted(glob.glob(os.path.join(ROOT, "시연자료", "나중에_받은_자료", "*.*"))) if not f.endswith((".bat", ".command"))][0]
    pg.click("#tabs button[data-p=prep]"); pg.evaluate("pickResubmit()")
    pg.wait_for_selector("#fsModal.on"); pg.evaluate(f"(()=>{{const cb=FS.cb; closeModal(); cb({new!r});}})()")
    pg.wait_for_selector("#askModal.on", timeout=15000); time.sleep(0.4)
    body = pg.inner_text("#askB"); print("재제출 비교:", " ".join(body.split())[:160])
    assert "새 판" in body
    pg.screenshot(path=f"{OUT}/4_재제출비교.png")
    pg.click("#askModal button.pri"); pg.wait_for_selector("#toast div:has-text('검증 완료')", timeout=30000)
    time.sleep(0.5); pg.screenshot(path=f"{OUT}/5_교체후검증.png")
    print("교체 후 칩:", pg.inner_text("#chips").replace("\n", " "))
    pg.evaluate("api('/api/ai/settings',{provider:'none',url:'',model:''})"); time.sleep(0.3)
    b.close()
print("화면 오류:", "; ".join(errs) if errs else "없음")
sys.exit(1 if errs else 0)
