"""실내공기질 출장지 관리 - 지도 마킹 프로그램

엑셀 파일을 불러와 지도에 마킹하고, 현장 방문 완료 여부를 관리한다.
엑셀 파일이 데이터 원본이며, 다른 업무에서도 그대로 참조하므로
프로그램이 직접 엑셀을 읽고 쓰는 구조를 유지한다.
"""
import hashlib
import socket
import sys
import threading
from pathlib import Path
from tkinter import Tk, filedialog

import pandas as pd
import webview
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
STATIC_DIR = BASE_DIR / "static"

# 시설군별 고정 색상
FACILITY_COLORS = {
    "학원": "#3388ff",
    "지하역사": "#808080",
    "장례식장": "#7f7f7f",
    "인터넷컴퓨터게임시설제공업의영업시설": "#e6194b",
    "의료기관": "#2ca02c",
    "영화상영관": "#ffd700",
    "업무시설": "#9467bd",
    "어린이집": "#ff8c00",
    "실내주차장": "#8b4513",
    "실내어린이놀이시설": "#ff69b4",
    "산후조리원": "#87ceeb",
    "박물관": "#d2b48c",
    "목욕장업의 영업시설": "#008080",
    "도서관": "#daa520",
    "대규모 점포": "#c0c0c0",
    "노인요양시설": "#b57edc",
}
DONE_COLOR = "#111111"
FALLBACK_PALETTE = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#46f0f0", "#f032e6", "#bcf60c"]

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
STATE = {"df": None, "excel_path": None, "lock": threading.Lock()}


def pick_excel_file() -> str:
    Tk().withdraw()
    path = filedialog.askopenfilename(
        title="엑셀 파일 선택",
        filetypes=[("Excel files", "*.xlsx *.xls")],
    )
    if not path:
        raise FileNotFoundError("엑셀 파일이 선택되지 않았습니다.")
    return path


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    for col in ("시군", "시설군", "시설명", "주소", "Latitude", "Longitude"):
        if col not in df.columns:
            raise KeyError(f"엑셀 파일에 '{col}' 열이 없습니다.")

    if "완료" not in df.columns:
        df["완료"] = ""
    df["완료"] = df["완료"].fillna("")

    changed = False
    if "ID" not in df.columns:
        df.insert(0, "ID", range(len(df)))
        changed = True
    if changed:
        df.to_excel(path, index=False)

    return df


def save_data() -> None:
    STATE["df"].to_excel(STATE["excel_path"], index=False)


def facility_color(facility: str) -> str:
    if facility in FACILITY_COLORS:
        return FACILITY_COLORS[facility]
    digest = int(hashlib.md5(facility.encode("utf-8")).hexdigest(), 16)
    color = FALLBACK_PALETTE[digest % len(FALLBACK_PALETTE)]
    print(f"[안내] 색상 매핑에 없는 시설군 '{facility}' -> 자동 색상 배정({color})")
    return color


def row_to_marker(row: pd.Series) -> dict:
    done = str(row["완료"]).strip() == "완료"
    return {
        "id": int(row["ID"]),
        "lat": float(row["Latitude"]),
        "lng": float(row["Longitude"]),
        "name": str(row["시설명"]),
        "facility": str(row["시설군"]),
        "address": str(row["주소"]),
        "region": str(row["시군"]),
        "done": done,
        "color": DONE_COLOR if done else facility_color(str(row["시설군"])),
    }


def region_summary(df: pd.DataFrame) -> dict:
    summary = {}
    for region, group in df.groupby("시군"):
        summary[region] = {
            "total": int(len(group)),
            "completed": int((group["완료"] == "완료").sum()),
        }
    return dict(sorted(summary.items()))


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/markers")
def api_markers():
    df = STATE["df"]
    return jsonify([row_to_marker(row) for _, row in df.iterrows()])


@app.get("/api/summary")
def api_summary():
    df = STATE["df"]
    return jsonify({
        "total": int(len(df)),
        "completed": int((df["완료"] == "완료").sum()),
        "by_region": region_summary(df),
    })


@app.post("/api/markers/<int:marker_id>")
def api_update_marker(marker_id: int):
    data = request.get_json(force=True, silent=True) or {}
    done = bool(data.get("done"))

    with STATE["lock"]:
        df = STATE["df"]
        mask = df["ID"] == marker_id
        if not mask.any():
            return jsonify(success=False, error="존재하지 않는 ID입니다."), 404

        df.loc[mask, "완료"] = "완료" if done else ""
        save_data()
        row = df.loc[mask].iloc[0]

    return jsonify(success=True, marker=row_to_marker(row), summary={
        "total": int(len(df)),
        "completed": int((df["완료"] == "완료").sum()),
        "by_region": region_summary(df),
    })


def find_free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def main() -> None:
    try:
        excel_path = pick_excel_file()
        STATE["excel_path"] = excel_path
        STATE["df"] = load_data(excel_path)
    except (FileNotFoundError, KeyError) as e:
        print(str(e))
        return

    port = find_free_port()
    server = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server.start()

    webview.create_window(
        "실내공기질 출장지 관리",
        f"http://127.0.0.1:{port}",
        width=1440,
        height=900,
        min_size=(1000, 700),
    )
    webview.start()


if __name__ == "__main__":
    main()
