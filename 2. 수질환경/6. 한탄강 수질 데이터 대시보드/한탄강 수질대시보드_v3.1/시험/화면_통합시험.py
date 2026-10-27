"""
화면_통합시험.py — 브라우저로 대시보드를 열어 화면·계산·저장을 시험

준비(처음 한 번):  pip install playwright   →   python -m playwright install chromium
사용법 (프로그램 폴더에서)
    python 시험/화면_통합시험.py            # 파일 모드 + 서버 모드 모두
    python 시험/화면_통합시험.py --file     # 파일 모드만(서버 시험 생략)

시험 항목
  [파일 모드] 모든 탭·분석 하위 탭이 오류 없이 그려짐 / 화면 통계(평균·표준편차·최대·최소) = Python 계산
              / 하천명 클릭 시 시료번호마다 다른 색 / ⚡ 특이 경향 표시 / 설정 화면 임시 저장
  [서버 모드] (임시 복사본에서) 지점 주소 저장 → 엑셀 반영·백업 생성 / 설정 저장 → 설정 시트 반영
              / 부품을 고치고 새로고침 → 자동 빌드 반영 / 부품을 망가뜨리면 이전 화면 유지
화면 사진은 시험/결과/ 에 저장된다(실제 자료가 보이므로 배포 묶음에 넣지 않는다).
"""
import argparse
import math
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "시험" / "결과"
HTML = "한탄강_수질대시보드.html"
RESULTS = []


def ok(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("  [통과] " if cond else "  [실패] ") + name + (f" — {detail}" if detail and not cond else ""))


def py_stats(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return None
    return (statistics.mean(v), statistics.stdev(v) if len(v) > 1 else 0, max(v), min(v))


def file_mode(pw):
    print("■ 파일 모드")
    sys.path.insert(0, str(ROOT / "tools"))
    import data_builder  # noqa: E402
    D, _ = data_builder.build_data(ROOT / "한탄강_수질DB.xlsx")
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((ROOT / HTML).as_uri())
    pg.evaluate("()=>{ try{ localStorage.clear(); }catch(e){} }")
    pg.reload()
    pg.wait_for_timeout(1200)
    tabs = pg.eval_on_selector_all("#tabs button", "b=>b.map(x=>x.dataset.view)")
    ok("탭이 만들어짐(9개)", len(tabs) == 9, str(tabs))
    for v in tabs:
        pg.click(f"#tabs button[data-view={v}]")
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(OUT / f"화면_{v}.png"))
    for a in ["trend", "corr", "box", "exceed"]:
        pg.click("#tabs button[data-view=ana]")
        pg.click(f"#anTabs button[data-a={a}]")
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(OUT / f"분석_{a}.png"))
    ok("모든 화면이 오류 없이 그려짐", not errs, "; ".join(errs[:3]))
    # 통계 대조
    js = pg.evaluate("()=>Object.fromEntries(ST.map(s=>[s.name, Object.fromEntries(ITEMS.map(i=>{ const t=stats(D.values[s.name][i.code]); return [i.code, t.n?[t.mean,t.sd,t.max,t.min]:null]; }))]))")
    bad = 0
    n = 0
    for st in D["stations"]:
        for it in D["items"]:
            p = py_stats(D["values"][st["name"]][it["code"]])
            j = js[st["name"]][it["code"]]
            n += 1
            if (p is None) != (j is None) or (p and any(not math.isclose(a, c, rel_tol=1e-9, abs_tol=1e-9) for a, c in zip(p, j))):
                bad += 1
    ok(f"화면 통계 = Python 계산 ({n}건)", bad == 0, f"{bad}건 다름")
    # 하천 클릭 → 색
    pg.click("#tabs button[data-view=ts]")
    pg.click('button[data-only="신천"]')
    pg.wait_for_timeout(400)
    cols = pg.evaluate("()=>{ const p = colorPlan(selectedOrdered()); return Object.values(p).map(x=>x.color); }")
    ok("하천명(신천) 클릭 → 13개 모두 다른 색", len(cols) == 13 and len(set(cols)) == 13, str(len(set(cols))))
    pg.click("#selAll")
    pg.click('button[data-it="T-P"]')
    pg.wait_for_timeout(400)
    ok("⚡ 특이 경향 표시(T-P 전체)", "특이 경향" in pg.text_content("#tsLegend"))
    pg.screenshot(path=str(OUT / "시계열_TP_특이경향.png"))
    # 설정(파일 모드: 이 브라우저 임시 저장)
    pg.click("#tabs button[data-view=set]")
    pg.wait_for_timeout(300)
    pg.fill('[data-set="특이경향_기준"]', "10")
    pg.dispatch_event('[data-set="특이경향_기준"]', "change")
    pg.click("#stSave")
    pg.wait_for_timeout(1800)
    ok("설정 임시 저장 → 다시 열어도 적용", pg.evaluate("()=>CFG.spike===10 && S.opt.spikeZ===10"))
    pg.evaluate("()=>{ try{ localStorage.clear(); }catch(e){} }")
    b.close()


def server_mode(pw):
    print("■ 서버 모드 (임시 복사본)")
    tmp = Path(tempfile.mkdtemp(prefix="한탄강서버시험_")) / "prog"
    shutil.copytree(ROOT, tmp, ignore=shutil.ignore_patterns("빌드결과", "백업", "시험", "__pycache__", "*.zip"))
    port = 8799
    proc = subprocess.Popen([sys.executable, str(tmp / "tools" / "serve.py"), "--no-open", "--port", str(port)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    url = f"http://localhost:{port}/" + urllib.request.quote(HTML)
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.3)
    try:
        b = pw.chromium.launch(args=["--no-proxy-server"])
        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(url)
        pg.wait_for_timeout(1500)
        pg.click("#tabs button[data-view=edit]")
        pg.wait_for_timeout(500)
        ok("서버 연결 표시", "서버 연결됨" in pg.text_content("#edMode"))
        inp = pg.locator('tr[data-row="한탄강1"] input[data-k="addr"]')
        inp.fill("포천시 창수면 운산리 영로교 아래(시험)")
        inp.dispatch_event("change")
        pg.click("#edSave")
        pg.wait_for_timeout(4000)
        sys.path.insert(0, str(tmp / "tools"))
        import importlib
        import wq_common
        importlib.reload(wq_common)
        db = wq_common.read_db(tmp / "한탄강_수질DB.xlsx")
        addr = next(s["주소"] for s in db["stations"] if s["시료번호"] == "한탄강1")
        ok("지점 주소 저장 → 엑셀 반영", addr.endswith("(시험)"), addr)
        ok("저장 전 백업 생성", any((tmp / "백업").glob("*.xlsx")))
        # 설정 저장
        pg.click("#tabs button[data-view=set]")
        pg.wait_for_timeout(500)
        pg.fill('[data-set="이상값_기준"]', "7")
        pg.dispatch_event('[data-set="이상값_기준"]', "change")
        pg.click("#stSave")
        pg.wait_for_timeout(4000)
        db = wq_common.read_db(tmp / "한탄강_수질DB.xlsx")
        ok("설정 저장 → 설정 시트 반영", str(wq_common.settings_dict(db).get("이상값_기준")) in ("7", "7.0"))
        # 부품 고치고 새로고침 → 자동 빌드
        part = tmp / "소스" / "40_화면" / "13_히트맵.js"
        orig = part.read_text(encoding="utf-8")
        part.write_text(orig.replace('label:"히트맵"', 'label:"히트맵(시험)"'), encoding="utf-8")
        time.sleep(1.1)
        pg.reload()
        pg.wait_for_timeout(2500)
        ok("부품 수정 + 새로고침 → 자동 빌드 반영", "히트맵(시험)" in pg.text_content("#tabs"))
        part.write_text(orig + "\nfunction broken( {\n", encoding="utf-8")
        time.sleep(1.1)
        pg.reload()
        pg.wait_for_timeout(2500)
        ok("부품을 망가뜨려도 이전 화면 유지", "히트맵(시험)" in pg.text_content("#tabs"))
        part.write_text(orig, encoding="utf-8")
        ok("서버 모드 화면 오류 없음", not errs, "; ".join(errs[:3]))
        b.close()
    finally:
        proc.terminate()
        try:
            log = proc.communicate(timeout=5)[0]
        except Exception:  # noqa: BLE001
            log = ""
        (OUT / "서버_기록.txt").write_text(log or "", encoding="utf-8")
        shutil.rmtree(tmp.parent, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="store_true", help="파일 모드만")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright가 없습니다: pip install playwright → python -m playwright install chromium")
    if not (ROOT / HTML).exists():
        sys.exit("먼저 빌드하세요: python tools/build.py")
    with sync_playwright() as pw:
        file_mode(pw)
        if not a.file:
            server_mode(pw)
    bad = [r for r in RESULTS if not r[1]]
    print(f"\n결과: 통과 {len(RESULTS) - len(bad)} / {len(RESULTS)}  (화면 사진: 시험/결과/)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
