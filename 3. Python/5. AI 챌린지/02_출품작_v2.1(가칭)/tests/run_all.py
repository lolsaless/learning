# -*- coding: utf-8 -*-
"""시험 한 번에 돌리기: 구조 규칙 → 기능 시험 → 파일 형식 → AI·재제출 비교 → 가상자료·자동 평가.
실행: python tests/run_all.py        (모두 통과하면 마지막 줄에 '전체 통과')
화면 시험(tests/e2e_ui.py)은 Playwright 가 있는 PC에서 따로 돌린다."""
import os
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = [("구조 규칙", ["test_structure.py"]), ("기능 시험", ["test_all.py"]), ("파일 형식", ["test_formats.py"]),
         ("AI·재제출 비교", ["test_ai_compare.py"]), ("가상자료·자동 평가", ["test_mockdata.py"])]


def main():
    bad = []
    for name, args in STEPS:
        print(f"\n===== {name} =====", flush=True)
        r = subprocess.run([sys.executable, "-W", "ignore", os.path.join(HERE, args[0])] + args[1:])
        if r.returncode != 0:
            bad.append(name)
    print("\n" + ("전체 통과" if not bad else f"실패: {', '.join(bad)}"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
