"""데스크톱 패키지에 공유 Python 소스를 복사한다."""

from __future__ import annotations

import shutil
from pathlib import Path


base = Path(__file__).resolve().parent
project_root = base.parent
staging = base / "stlite_src"
staging.mkdir(exist_ok=True)
staged_package = staging / "src"
if staged_package.exists():
    shutil.rmtree(staged_package)
shutil.copytree(project_root / "src", staged_package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

(staging / "app.py").write_text(
    "from src.ui import render_app\n\nrender_app()\n",
    encoding="utf-8",
)
print("데스크톱 빌드용 Python 소스 동기화 완료")
