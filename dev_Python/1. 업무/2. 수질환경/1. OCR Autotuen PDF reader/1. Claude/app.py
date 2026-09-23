"""GC/MS Autotune OCR 판독 - 배포용 데스크톱 앱

PDF/이미지를 드래그하거나 업로드 버튼으로 올리면 ocr_engine.py의 판독 로직을
그대로 실행해 평가 결과를 화면에 보여주고, 평가서 PDF를 다운로드할 수 있게
한다. Tesseract/Poppler 실행파일은 bin/<os>/ 폴더에 번들해두면 별도 설치 없이
그대로 동작하고, 없으면 시스템 PATH에서 찾는다(개발용 폴백).
"""
import os
import platform
import socket
import sys
import tempfile
import threading
import traceback
import uuid
from pathlib import Path

import pytesseract
import webview
from flask import Flask, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

import ocr_engine

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
STATIC_DIR = BASE_DIR / "static"

ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg"}

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
REPORTS = {}  # report_id -> 생성된 평가서 PDF 경로
WORK_DIR = Path(tempfile.mkdtemp(prefix="gcms_autotune_"))


def _bundled_bin_dir() -> Path:
    system = platform.system().lower()
    if system == "windows":
        return BASE_DIR / "bin" / "windows"
    if system == "darwin":
        return BASE_DIR / "bin" / "mac"
    return BASE_DIR / "bin" / "linux"


def configure_ocr_binaries() -> str:
    """번들된 tesseract/poppler를 찾아 설정한다. 없으면 시스템 PATH를 사용한다.

    반환값은 진단용 상태 메시지(콘솔 출력용).
    """
    bin_dir = _bundled_bin_dir()
    system = platform.system().lower()
    tesseract_name = "tesseract.exe" if system == "windows" else "tesseract"

    tesseract_path = bin_dir / tesseract_name
    tessdata_dir = bin_dir / "tessdata"
    poppler_bin_dir = bin_dir / "poppler"

    msgs = []
    if tesseract_path.exists():
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)
        if tessdata_dir.exists():
            os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)
        msgs.append(f"tesseract: 번들({tesseract_path})")
    else:
        msgs.append("tesseract: 시스템 PATH 사용 (개발 모드)")

    if poppler_bin_dir.exists():
        ocr_engine.DEFAULT_POPPLER_PATH = str(poppler_bin_dir)
        msgs.append(f"poppler: 번들({poppler_bin_dir})")
    else:
        ocr_engine.DEFAULT_POPPLER_PATH = None
        msgs.append("poppler: 시스템 PATH 사용 (개발 모드)")

    return " / ".join(msgs)


ocr_engine.DEFAULT_POPPLER_PATH = None


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.post("/api/evaluate")
def api_evaluate():
    if "file" not in request.files:
        return jsonify(success=False, error="파일이 전달되지 않았습니다."), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify(success=False, error="파일이 선택되지 않았습니다."), 400

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify(
            success=False,
            error=f"지원하지 않는 파일 형식입니다({ext}). PDF, PNG, JPG 파일만 가능합니다.",
        ), 400

    report_id = uuid.uuid4().hex
    run_dir = WORK_DIR / report_id
    run_dir.mkdir(parents=True, exist_ok=True)

    src_name = secure_filename(f.filename) or ("input" + ext)
    src_path = run_dir / src_name
    f.save(src_path)

    try:
        page_img = ocr_engine.load_page_image(
            str(src_path), dpi=300, poppler_path=ocr_engine.DEFAULT_POPPLER_PATH
        )
        data = ocr_engine.extract_all_fields(page_img)
        rows = ocr_engine.evaluate(data)

        out_path = run_dir / "평가서.pdf"
        ocr_engine.build_pdf(data, rows, str(src_path), str(out_path))
    except Exception as e:  # noqa: BLE001 - 사용자에게 원인을 그대로 보여줘야 함
        traceback.print_exc()
        return jsonify(success=False, error=f"판독 중 오류가 발생했습니다: {e}"), 500

    REPORTS[report_id] = str(out_path)

    n_pass = sum(1 for r in rows if r[3] == ocr_engine.PASS)
    n_warn = sum(1 for r in rows if r[3] == ocr_engine.WARN)
    n_fail = sum(1 for r in rows if r[3] == ocr_engine.FAIL)
    n_unk = sum(1 for r in rows if r[3] == ocr_engine.UNKNOWN)
    overall = "경고" if n_fail else ("주의" if (n_warn or n_unk) else "정상")

    return jsonify(
        success=True,
        reportId=report_id,
        fileName=f.filename,
        meta={
            "title": data.get("title") or "Autotune",
            "timestamp": data.get("timestamp") or "판독불가",
            "methodPath": data.get("method_path") or "판독불가",
        },
        overall=overall,
        counts={"pass": n_pass, "warn": n_warn, "fail": n_fail, "unknown": n_unk, "total": len(rows)},
        rows=[
            {"name": name, "value": value, "criteria": criteria, "verdict": verdict}
            for name, value, criteria, verdict in rows
        ],
    )


@app.get("/api/report/<report_id>")
def api_report(report_id):
    path = REPORTS.get(report_id)
    if not path or not os.path.exists(path):
        return jsonify(success=False, error="평가서를 찾을 수 없습니다."), 404
    return send_file(path, as_attachment=True, download_name="Autotune_평가서.pdf")


def find_free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def main() -> None:
    status = configure_ocr_binaries()
    print(f"[OCR 엔진 준비] {status}")

    port = find_free_port()
    server = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server.start()

    webview.create_window(
        "GC/MS Autotune 자동 판독",
        f"http://127.0.0.1:{port}",
        width=1100,
        height=800,
        min_size=(800, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
