from flask import Flask, jsonify, render_template_string, request
import pandas as pd
import folium
from tkinter import Tk, filedialog
import webbrowser
import threading
import os
import signal
import platform
import json
from html import escape
from pathlib import Path

# Flask 앱 초기화
app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
FACILITY_COLOR_PATH = BASE_DIR / "facility_colors.json"
COMPLETED_COLOR = "black"
DEFAULT_FACILITY_COLOR = "green"
AVAILABLE_ICON_COLORS = [
    "blue",
    "gray",
    "white",
    "red",
    "green",
    "yellow",
    "purple",
    "orange",
    "brown",
    "pink",
    "lightblue",
    "beige",
    "cadetblue",
    "darkblue",
    "darkgreen",
    "darkpurple",
    "lightgray",
    "lightgreen",
]

# 엑셀 파일 로드
def load_excel():
    """엑셀 파일 선택"""
    Tk().withdraw()  # Tkinter GUI 숨기기
    file_path = filedialog.askopenfilename(
        title="엑셀 파일 선택",
        filetypes=[("Excel files", "*.xlsx *.xls")]
    )
    
    if file_path:
        return pd.read_excel(file_path), file_path
    
    raise FileNotFoundError("엑셀 파일이 선택되지 않았습니다.")


def prepare_dataframe(raw_df):
    """지도 렌더링 전에 필요한 컬럼과 타입을 정리합니다."""
    working_df = raw_df.copy()

    if "완료" not in working_df.columns:
        working_df["완료"] = ""

    working_df["완료"] = working_df["완료"].fillna("").astype(str).str.strip()
    working_df["시설군"] = working_df["시설군"].fillna("미분류").astype(str).str.strip()
    working_df["시군"] = working_df["시군"].fillna("미상").astype(str).str.strip()
    working_df["시설명"] = working_df["시설명"].fillna("").astype(str).str.strip()
    working_df["주소"] = working_df["주소"].fillna("").astype(str).str.strip()
    working_df["Latitude"] = pd.to_numeric(working_df["Latitude"], errors="coerce")
    working_df["Longitude"] = pd.to_numeric(working_df["Longitude"], errors="coerce")

    return working_df


def load_facility_colors(dataframe):
    """시설군별 색상을 JSON 파일에서 읽고, 새 시설군은 자동 배정합니다."""
    default_colors = {
        "학원": "blue",
        "지하역사": "gray",
        "장례식장": "white",
        "인터넷컴퓨터게임시설제공업의영업시설": "red",
        "의료기관": "green",
        "영화상영관": "yellow",
        "업무시설": "purple",
        "어린이집": "orange",
        "실내주차장": "brown",
        "실내어린이놀이시설": "pink",
        "산후조리원": "lightblue",
        "박물관": "beige",
        "목욕장업의 영업시설": "cadetblue",
        "도서관": "darkblue",
        "대규모 점포": "darkpurple",
        "노인요양시설": "lightgreen",
    }
    facility_color_map = default_colors.copy()

    if FACILITY_COLOR_PATH.exists():
        try:
            saved_colors = json.loads(FACILITY_COLOR_PATH.read_text(encoding="utf-8"))
            if isinstance(saved_colors, dict):
                facility_color_map.update(
                    {
                        str(name).strip(): color
                        for name, color in saved_colors.items()
                        if str(color) in AVAILABLE_ICON_COLORS
                    }
                )
        except json.JSONDecodeError:
            pass

    used_colors = {color for color in facility_color_map.values() if color in AVAILABLE_ICON_COLORS}
    remaining_colors = [color for color in AVAILABLE_ICON_COLORS if color not in used_colors]
    all_facilities = sorted(dataframe["시설군"].dropna().unique())

    for facility in all_facilities:
        if facility in facility_color_map:
            continue
        if remaining_colors:
            facility_color_map[facility] = remaining_colors.pop(0)
        else:
            palette_index = abs(hash(facility)) % len(AVAILABLE_ICON_COLORS)
            facility_color_map[facility] = AVAILABLE_ICON_COLORS[palette_index]

    FACILITY_COLOR_PATH.write_text(
        json.dumps(facility_color_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return facility_color_map

try:
    # 엑셀 파일 로드 시도
    df, EXCEL_PATH = load_excel()
except FileNotFoundError as e:
    # 엑셀 파일이 선택되지 않은 경우 프로그램 종료
    print(str(e))
    exit()

df = prepare_dataframe(df)
map_df = df.dropna(subset=["Latitude", "Longitude"]).copy().reset_index().rename(columns={"index": "row_id"})
facility_colors = load_facility_colors(df)


def get_facility_color(row):
    """시설군에 따른 색상 반환."""
    if row["완료"] == "완료":
        return COMPLETED_COLOR
    return facility_colors.get(row["시설군"], DEFAULT_FACILITY_COLOR)


def calculate_progress():
    """시군별 완료 진행 상황 계산."""
    # 각 시군에 대해 완료된 건수와 전체 건수를 계산하여 문자열로 반환
    if "시군" not in df.columns:
        raise KeyError("'시군' 열이 데이터프레임에 존재하지 않습니다.")
    progress = df.groupby("시군").apply(lambda x: f"{(x['완료'] == '완료').sum()}건 완료 / {len(x)}건")
    return progress.to_dict()


def calculate_facility_progress():
    """시설군별 전체/완료/미완료 건수를 계산합니다."""
    summary = (
        df.assign(완료여부=df["완료"].eq("완료"))
        .groupby("시설군")
        .agg(전체=("시설군", "size"), 완료=("완료여부", "sum"))
        .sort_values(["전체", "완료"], ascending=[False, False])
    )
    summary["미완료"] = summary["전체"] - summary["완료"]
    return summary.reset_index().to_dict("records")


def calculate_total_progress():
    """전체 완료 진행 상황 계산."""
    total_completed = (df["완료"] == "완료").sum()
    total_count = len(df)
    return f"총 완료: {total_completed}건 / 전체: {total_count}건"


def build_side_panel():
    """진행 상황과 시설군 범례를 담은 사이드 패널 HTML을 생성합니다."""
    total_progress = calculate_total_progress()
    facility_progress = calculate_facility_progress()
    region_progress = calculate_progress()

    panel_html = [
        "<div style='position: fixed; top: 10px; right: 10px; width: 360px; max-height: calc(100vh - 20px); overflow-y: auto; background: rgba(255, 255, 255, 0.95); padding: 14px; border: 1px solid #333; border-radius: 12px; box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15); z-index: 1000; font-family: Arial, sans-serif;'>",
        f"<h3 style='margin: 0 0 10px;'>출장지 현황</h3><p style='margin: 0 0 12px;'><b>{escape(total_progress)}</b></p>",
        "<h4 style='margin: 0 0 8px;'>시설군별 범례</h4>",
        "<div style='display: grid; grid-template-columns: 1fr; gap: 6px; margin-bottom: 14px;'>",
    ]

    for item in facility_progress:
        color = facility_colors.get(item["시설군"], DEFAULT_FACILITY_COLOR)
        label = escape(item["시설군"])
        panel_html.append(
            "<div style='display: flex; align-items: center; justify-content: space-between; gap: 8px;'>"
            f"<div style='display: flex; align-items: center; gap: 8px;'><span style='display: inline-block; width: 14px; height: 14px; border-radius: 50%; background: {escape(color)}; border: 1px solid #555;'></span><span>{label}</span></div>"
            f"<span style='color: #555;'>{item['전체']}건</span>"
            "</div>"
        )

    panel_html.extend(
        [
            "</div>",
            "<div style='margin-bottom: 14px; padding: 8px 10px; border: 1px solid #ddd; border-radius: 8px; background: #f6f6f6;'>",
            f"<div style='display: flex; align-items: center; gap: 8px;'><span style='display: inline-block; width: 14px; height: 14px; border-radius: 50%; background: {COMPLETED_COLOR}; border: 1px solid #555;'></span><span>완료 처리된 출장지</span></div>",
            "</div>",
            "<h4 style='margin: 0 0 8px;'>시설군별 진행 상황</h4>",
        ]
    )

    for item in facility_progress:
        label = escape(item["시설군"])
        panel_html.append(
            f"<p style='margin: 4px 0;'><b>{label}</b>: 완료 {item['완료']}건 / 미완료 {item['미완료']}건 / 전체 {item['전체']}건</p>"
        )

    panel_html.append("<h4 style='margin: 14px 0 8px;'>시군별 진행 상황</h4>")
    for region, status in region_progress.items():
        panel_html.append(f"<p style='margin: 4px 0;'><b>{escape(region)}</b>: {escape(status)}</p>")

    panel_html.append(
        "<button onclick='shutdownServer()' style='margin-top: 12px; padding: 8px 12px; border: none; border-radius: 8px; background: #222; color: #fff; cursor: pointer;'>종료</button>"
    )
    panel_html.append("</div>")
    return "".join(panel_html)


@app.route("/")
def map_view():
    """지도와 초기 상태를 렌더링."""
    # 지도 생성 - 위도와 경도의 평균 값을 중심으로 설정
    map_center = [df["Latitude"].mean(), df["Longitude"].mean()]
    mymap = folium.Map(location=map_center, zoom_start=12)

    # 마커를 추가
    for row in map_df.to_dict("records"):
        color = get_facility_color(row)  # 각 시설의 색상을 결정
        marker = folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=(f"""
                <div style='width:300px; height:auto;'>
                    <b>시설명:</b> {escape(row['시설명'])}<br>
                    <b>시군:</b> {escape(row['시군'])}<br>
                    <b>시설군:</b> {escape(row['시설군'])}<br>
                    <b>주소:</b> {escape(row['주소'])}<br>
                    <button onclick='markAsComplete({row["row_id"]})'>완료</button>
                    <button onclick='cancelCompletion({row["row_id"]})'>취소</button>
                </div>
            """),
            icon=folium.Icon(color=color),  # 마커의 색상 설정
        )
        marker.add_to(mymap)  # 지도에 마커 추가

    # 지도 HTML 생성
    map_html = mymap.get_root().render()

    # JavaScript 추가 (마커 완료 처리 기능 및 서버 종료 기능)
    map_html += build_side_panel()
    map_html += """
    <script>
        async function updateMarker(index, action) {
            const formData = new URLSearchParams({ id: index, action: action });
            const response = await fetch("/update", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: formData.toString()
            });
            return response.json();
        }

        function markAsComplete(index) {
            updateMarker(index, "complete").then(function(response) {
                if (response.success) {
                    alert("마커 상태가 업데이트되었습니다.");
                    location.reload();
                } else {
                    alert("업데이트 실패: " + response.error);
                }
            });
        }

        function cancelCompletion(index) {
            updateMarker(index, "cancel").then(function(response) {
                if (response.success) {
                    alert("마커 상태가 취소되었습니다.");
                    location.reload();
                } else {
                    alert("취소 실패: " + response.error);
                }
            });
        }

        function shutdownServer() {
            if (confirm('프로그램을 종료하시겠습니까?')) {
                fetch('/shutdown').then(function(response) {
                    return response.text();
                }).then(function(message) {
                    alert(message);
                    window.open('', '_self', '');
                    window.close();
                });
            }
        }
    </script>
    """
    return render_template_string(map_html)


@app.route("/update", methods=["POST"])
def update_marker():
    """마커를 완료 상태로 업데이트 또는 취소."""
    try:
        marker_id = int(request.form["id"])
        action = request.form["action"]
        if action == 'complete':
            df.loc[marker_id, "완료"] = "완료"  # "완료" 열에 상태 저장
        elif action == 'cancel':
            df.loc[marker_id, "완료"] = ""  # 완료 상태 취소
        map_df.loc[map_df["row_id"] == marker_id, "완료"] = df.loc[marker_id, "완료"]
        df.to_excel(EXCEL_PATH, index=False)  # 엑셀 파일에 변경 사항 저장
        return jsonify(success=True)
    except Exception as e:
        # 예외 발생 시 오류 메시지를 반환
        return jsonify(success=False, error=str(e))


@app.route('/shutdown', methods=['GET'])
def shutdown():
    """서버를 종료합니다."""
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        if platform.system() == "Windows":
            os.system(f'taskkill /PID {os.getpid()} /F')
        else:
            os.kill(os.getpid(), signal.SIGTERM)
    else:
        func()
    return '서버가 종료되었습니다.'


def open_browser():
    """서버가 실행된 후 브라우저를 자동으로 엽니다."""
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == "__main__":
    # 웹 서버 실행 및 브라우저 열기
    threading.Timer(1, open_browser).start()  # 1초 후 브라우저 열기
    app.run(debug=False)
