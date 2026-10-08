"""Streamlit 소스를 포함한 단일 index.html을 생성한다."""

from __future__ import annotations

import json
from pathlib import Path


base = Path(__file__).resolve().parent
project_root = base.parent
template_path = base / "index_template.html"
output_path = base / "index.html"

source_files = {
    "src/__init__.py": project_root / "src" / "__init__.py",
    "src/ui.py": project_root / "src" / "ui.py",
    "src/processor.py": project_root / "src" / "processor.py",
}

files = {
    "app.py": "from src.ui import render_app\n\nrender_app()\n",
    **{name: path.read_text(encoding="utf-8") for name, path in source_files.items()},
}
files_json = json.dumps(files, ensure_ascii=False).replace("</", "<\\/")
template = template_path.read_text(encoding="utf-8")

placeholder = "__APP_FILES_JSON__"
if template.count(placeholder) != 1:
    raise RuntimeError(f"{placeholder} 플레이스홀더가 템플릿에 정확히 1개 있어야 합니다.")

output_path.write_text(template.replace(placeholder, files_json), encoding="utf-8")
print(f"{output_path.name} 생성 완료 ({output_path.stat().st_size:,} bytes)")
