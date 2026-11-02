# -*- coding: utf-8 -*-
"""휴대용 Python 넣기(Windows): 공식 'Windows embeddable' Python 을 내려받아 프로그램 폴더의 python\\ 에 푼다.

인터넷이 되는 PC 에서 한 번 실행하면, 그 뒤로는 Python 을 설치하지 않은 PC(심사 PC 등)에서도
실행_Windows.bat 이 python\\python.exe 를 먼저 찾아 실행한다. 외부 라이브러리는 받지 않는다(표준 라이브러리만 사용).

  python tools/make_portable.py              # 기본 3.12.10 (64비트)
  python tools/make_portable.py --version 3.11.9

받은 파일은 python.org 공식 주소에서만 받는다. 라이선스: Python Software Foundation License(python\\LICENSE.txt).
"""
import io
import os
import sys
import zipfile
import argparse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://www.python.org/ftp/python/{v}/python-{v}-embed-{arch}.zip"


def main(argv=None):
    ap = argparse.ArgumentParser(description="휴대용 Python 넣기")
    ap.add_argument("--version", default="3.12.10")
    ap.add_argument("--arch", default="amd64", choices=["amd64", "win32", "arm64"])
    a = ap.parse_args(argv)
    dst = os.path.join(ROOT, "python")
    url = URL.format(v=a.version, arch=a.arch)
    print(f"내려받는 중: {url}")
    with urllib.request.urlopen(url, timeout=120) as r:
        data = r.read()
    os.makedirs(dst, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dst)
    # embeddable 판은 ._pth 파일에 적힌 경로만 쓴다 → 프로그램 폴더(..)를 넣어 app 패키지를 찾게 한다
    for f in os.listdir(dst):
        if f.endswith("._pth"):
            p = os.path.join(dst, f)
            lines = open(p, encoding="utf-8").read().splitlines()
            if ".." not in lines:
                lines.insert(1, "..")
            open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"완료: {dst}\\python.exe  (이 폴더째 USB·압축으로 옮기면 Python 설치 없이 실행됩니다)")


if __name__ == "__main__":
    sys.exit(main())
