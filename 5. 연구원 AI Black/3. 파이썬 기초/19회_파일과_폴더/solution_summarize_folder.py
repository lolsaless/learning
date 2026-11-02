"""측정 폴더 자동 요약 프로그램 (19회 과제 해답)

같은 폴더의 data/ 안에 있는 모든 측정 CSV(DateTime, CO2_ppm, Temp_C, RH)를 읽어
파일마다 CO2 요약과 온도·습도 평균을 계산하고 output/CO2_요약.csv 로 저장한다.

실행 방법 (가상환경을 켠 상태)
    python solution_summarize_folder.py
"""

import csv
from pathlib import Path

BASE_DIR = Path(__file__).parent          # 이 .py 파일이 있는 폴더 (어디서 실행해도 같음)
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "output"
CO2_LIMIT = 1000                          # 수업용 예시 기준


def read_rows(path):
    """측정 CSV 한 개를 읽어 딕셔너리의 리스트로 돌려준다."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def mean(values):
    return round(sum(values) / len(values), 1)


def summarize(rows):
    """측정 행들에서 CO2 요약과 온도·습도 평균을 계산한다."""
    co2 = [int(r["CO2_ppm"]) for r in rows]
    temp = [float(r["Temp_C"]) for r in rows]
    rh = [float(r["RH"]) for r in rows]
    co2_mean = mean(co2)
    return {
        "count": len(co2),
        "co2_mean": co2_mean,
        "co2_max": max(co2),
        "co2_min": min(co2),
        "result": "부적합" if co2_mean >= CO2_LIMIT else "적합",
        "temp_mean": mean(temp),
        "rh_mean": mean(rh),
    }


def main():
    summary = []
    for path in sorted(DATA_DIR.glob("*.csv")):
        date, place = path.stem.split("_", 1)
        summary.append({"file": path.name, "date": date, "place": place, **summarize(read_rows(path))})

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / "CO2_요약.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)

    failed = sum(1 for row in summary if row["result"] == "부적합")
    print(f"{len(summary)}개 파일 요약 완료 (부적합 {failed}곳) → {out_path.name}")


if __name__ == "__main__":
    main()
