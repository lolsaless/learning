"""설치 확인 프로그램

파이썬이 제대로 설치됐는지, 이 과정에서 쓰는 라이브러리가 준비됐는지 한 번에 확인합니다.

실행 방법
    Mac     : python3.13 check_setup.py   (가상환경을 켠 뒤에는 python check_setup.py)
    Windows : py -3.13 check_setup.py      (가상환경을 켠 뒤에는 python check_setup.py)
"""

import platform
import sys
from importlib import metadata

# 이 과정에서 사용하는 주요 라이브러리 (11회에서 설치합니다)
LIBRARIES = {
    "pandas": "표 데이터 처리 (4단계)",
    "openpyxl": "엑셀 파일 읽고 쓰기 (4단계)",
    "matplotlib": "그래프 그리기 (5단계)",
    "ipykernel": "VS Code에서 주피터 노트북 실행 (10~11회)",
}

print("=" * 55)
print(" 설치 확인 결과")
print("=" * 55)

# 1. 운영체제와 파이썬 정보
print(f"운영체제       : {platform.system()} {platform.release()} ({platform.machine()})")
print(f"파이썬 버전     : {platform.python_version()}")
print(f"파이썬 위치     : {sys.executable}")

# 2. 가상환경 안에서 실행 중인지 확인
in_venv = sys.prefix != sys.base_prefix
print(f"가상환경 사용   : {'예 ✅' if in_venv else '아니오 (11회에서 만듭니다)'}")

# 3. pip 버전
try:
    print(f"pip 버전        : {metadata.version('pip')}")
except metadata.PackageNotFoundError:
    print("pip 버전        : 찾을 수 없음 ❌")

# 4. 파이썬 버전이 3.12 이상인지 확인
if sys.version_info >= (3, 12):
    print("버전 판정       : 3.12 이상 ✅")
else:
    print("버전 판정       : 3.12 미만 ⚠️  새 버전을 설치하세요")

# 5. 라이브러리 설치 여부
print("-" * 55)
print(" 라이브러리")
print("-" * 55)
for name, usage in LIBRARIES.items():
    try:
        version = metadata.version(name)
        print(f"✅ {name:<11} {version:<10} {usage}")
    except metadata.PackageNotFoundError:
        print(f"⬜ {name:<11} {'미설치':<10} {usage}")

print("=" * 55)
print("⬜ 표시는 아직 설치하지 않은 것입니다. 11회에서 설치합니다.")
