"""소스코드를 합쳐 '사진변환기.html' 한 파일로 만든다.

수정 방법
  1. 이 폴더의 파일을 고친다
       index.html : 화면 구성(버튼, 문구)
       style.css  : 디자인(색, 크기, 배치)
       app.js     : 동작(파일 추가, 변환, 저장)
  2. 이 폴더에서 실행:  python build.py   (Mac: python3 build.py)
  3. 상위 폴더의 '사진변환기.html'이 새로 만들어진다

lib 폴더는 외부 라이브러리이므로 고치지 않는다.
  pako 2.1.0 (MIT/Zlib)       - TIFF 압축 해제
  UTIF.js 3.1.0 (MIT)         - TIFF 읽기
  heic-to 1.5.2 (LGPL-3.0)    - HEIC 읽기 (libheif 1.22.2)
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent
OUT = SRC.parent / "사진변환기.html"


def inline(match):
    name = match.group(1)
    code = (SRC / name).read_text(encoding="utf-8")
    # HTML 안에 넣을 때 <script> 태그가 깨지지 않도록 확인
    for bad in ("</script", "<!--", "<script"):
        if bad in code.lower() and name.endswith(".js"):
            raise SystemExit(f"{name} 안에 '{bad}' 문자열이 있어 HTML에 넣을 수 없습니다.")
    return code


html = (SRC / "index.html").read_text(encoding="utf-8")
html = re.sub(r"/\*@@(.+?)@@\*/", inline, html)
OUT.write_text(html, encoding="utf-8")
print(f"완료: {OUT}  ({OUT.stat().st_size // 1024:,} KB)")
