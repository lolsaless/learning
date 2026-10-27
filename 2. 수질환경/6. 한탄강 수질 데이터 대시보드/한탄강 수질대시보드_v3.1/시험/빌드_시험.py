"""
빌드_시험.py — 빌드 도구가 제대로 막고·만드는지 시험 (브라우저 필요 없음, Python만)

사용법 (프로그램 폴더에서)
    python 시험/빌드_시험.py

프로그램 폴더를 임시 폴더에 복사해서 시험하므로 원본은 바뀌지 않는다.
시험 항목
  1. 정상 빌드: HTML이 만들어지고, 모든 부품 표시가 들어 있고, 데이터 수가 DB와 같다
  2. 고장 넣기: 이름 중복 / 목록의 파일 없음 / 문법 오류(Node.js 있을 때) / </script> / 화면 자리 없음
     → 빌드가 실패하고 기존 HTML이 그대로인지
  3. 간단 빌드(build_simple.sh 또는 .ps1) 결과가 build.py --cache 와 글자 하나까지 같은지
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
RESULTS = []


def ok(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("  [통과] " if cond else "  [실패] ") + name + (f" — {detail}" if detail and not cond else ""))


def copy_program():
    tmp = Path(tempfile.mkdtemp(prefix="한탄강시험_"))
    dst = tmp / "prog"
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns("빌드결과", "백업", "시험", "__pycache__", "*.zip"))
    return dst


def run_build(prog, *args):
    r = subprocess.run([PY, str(prog / "tools" / "build.py"), *args], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def main():
    print("■ 1. 정상 빌드")
    prog = copy_program()
    code, out = run_build(prog)
    html = prog / "한탄강_수질대시보드.html"
    ok("빌드 성공", code == 0, out[-300:])
    text = html.read_text(encoding="utf-8") if html.exists() else ""
    parts = [ln.split("#")[0].strip() for ln in (prog / "소스" / "빌드목록.txt").read_text(encoding="utf-8").splitlines()]
    parts = [p for p in parts if p and not p.startswith("10_외부라이브러리/") and not p.startswith("00_틀/01_")]
    missing = [p for p in parts if f"부품: {p} =====" not in text]
    ok("모든 부품 표시가 HTML에 들어 있음", not missing, ", ".join(missing))
    ok("외부 글꼴·CDN 링크 없음", "fonts.googleapis" not in text and "cdnjs.cloudflare" not in text)
    sys.path.insert(0, str(prog / "tools"))
    import data_builder  # noqa: E402
    d, _ = data_builder.build_data(prog / "한탄강_수질DB.xlsx")
    m = re.search(r"const D = (\{.*?\});</script>", text, re.S)
    import json
    D = json.loads(m.group(1).replace("<\\/", "</")) if m else {}
    ok("HTML 속 데이터 = DB (시료번호·월·점검 수)", D and len(D["stations"]) == len(d["stations"]) and D["months"] == d["months"] and len(D["qc"]) == len(d["qc"]))
    ok("버전 표기", f'window.APP_VERSION = "{(prog / "소스" / "버전.txt").read_text(encoding="utf-8").strip()}"' in text)

    print("■ 2. 고장 넣기 → 빌드가 막고 기존 HTML을 지키는지")
    before = html.read_bytes()

    def fault(name, path, mutate, expect):
        f = prog / "소스" / path
        orig = f.read_text(encoding="utf-8")
        f.write_text(mutate(orig), encoding="utf-8")
        code, out = run_build(prog)
        f.write_text(orig, encoding="utf-8")
        ok(f"{name} → 실패로 막음", code != 0 and expect in out, out.strip().splitlines()[-1] if out.strip() else "")
        ok(f"{name} → 기존 HTML 그대로", html.read_bytes() == before)

    fault("이름 중복", "40_화면/13_히트맵.js", lambda s: s + "\nfunction renderTs(){}\n", "두 부품에 있음")
    fault("목록의 파일 없음", "빌드목록.txt", lambda s: s + "\n40_화면/99_없는부품.js\n", "파일이 없음")
    fault("</script> 글자", "40_화면/15_연도별.js", lambda s: s + '\nconst __x = "</script>";\n', "</script")
    fault("화면 자리 없음", "빌드목록.txt", lambda s: s.replace("02_화면/13_히트맵.html\n", ""), "화면 자리")
    if shutil.which("node"):
        fault("문법 오류", "40_화면/12_종단.js", lambda s: s + "\nfunction broken( {\n", "12_종단.js")
    else:
        print("  [건너뜀] 문법 오류 시험 — Node.js 없음")

    print("■ 3. 간단 빌드 = build.py --cache")
    code, out = run_build(prog, "--cache", "--out", str(prog / "_py.html"))
    ok("build.py --cache 성공", code == 0, out[-200:])
    simple = None
    if os.name == "nt":
        if shutil.which("powershell"):
            simple = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(prog / "tools" / "build_simple.ps1")]
    elif shutil.which("bash"):
        simple = ["bash", str(prog / "tools" / "build_simple.sh")]
    if simple:
        r = subprocess.run(simple, capture_output=True, text=True, encoding="utf-8")
        same = html.exists() and (prog / "_py.html").exists() and html.read_bytes() == (prog / "_py.html").read_bytes()
        ok("간단 빌드 결과가 같음", r.returncode == 0 and same, (r.stdout + r.stderr)[-200:])
    else:
        print("  [건너뜀] 간단 빌드 — bash/PowerShell 없음")

    shutil.rmtree(prog.parent, ignore_errors=True)
    bad = [r for r in RESULTS if not r[1]]
    print(f"\n결과: 통과 {len(RESULTS) - len(bad)} / {len(RESULTS)}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
