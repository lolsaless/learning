"""
app.py 내용을 index_template.html에 삽입해 최종 index.html을 생성합니다.
app.py 로직을 수정한 뒤에는 반드시 이 스크립트를 다시 실행해서
index.html을 갱신해야 배포용 파일에 변경사항이 반영됩니다.

실행 방법:
    python build.py
"""
from pathlib import Path

base = Path(__file__).parent
app_code = (base / "app.py").read_text(encoding="utf-8")
template = (base / "index_template.html").read_text(encoding="utf-8")

# 템플릿 리터럴 안에 들어가므로 백틱/역슬래시/${ 는 이스케이프 처리
escaped = (
    app_code
    .replace("\\", "\\\\")
    .replace("`", "\\`")
    .replace("${", "\\${")
)

output = template.replace("__APP_PY_CODE__", escaped)
(base / "index.html").write_text(output, encoding="utf-8")
print("index.html 생성 완료")
