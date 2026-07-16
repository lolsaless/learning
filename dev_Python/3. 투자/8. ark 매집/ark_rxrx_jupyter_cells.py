# %%
# ARK RXRX 매매기록 분석용 Jupyter 코드
# 사용법:
# 1. 이 파일과 같은 폴더에 ark.csv를 둡니다.
# 2. VS Code에서 이 파일을 열고 셀 단위로 실행합니다.
# 3. ark.csv 날짜가 "6월 10일"처럼 연도 없이 들어가면 YEAR 값을 분석 연도로 맞춥니다.

from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    display
except NameError:
    def display(obj):
        print(obj)

pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 140)

YEAR = 2026
ARK_CSV_PATH = Path("ark.csv")
OUTPUT_DIR = Path("ark_rxrx_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


# %%
# 1단계. ark.csv 원자료 읽기
# - 탭 구분 TSV 형태와 일반 CSV 형태를 모두 시도합니다.
# - 숫자 안 쉼표(예: 1,665,715)는 정제 단계에서 제거합니다.

def read_ark_csv(path: Path) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "cp949"]
    last_error: Exception | None = None

    for encoding in encodings:
        for sep in ["\t", None]:
            try:
                df = pd.read_csv(path, sep=sep, engine="python", encoding=encoding)
                if df.shape[1] >= 4:
                    return df
            except Exception as exc:
                last_error = exc

    raise RuntimeError(
        "ark.csv를 읽지 못했습니다. 가능하면 Numbers/Excel에서 UTF-8 CSV로 내보내거나, "
        "탭 구분 파일로 저장하세요."
    ) from last_error


raw = read_ark_csv(ARK_CSV_PATH)
print("원자료 크기:", raw.shape)
display(raw.head(10))
display(raw.dtypes)


# %%
# 2단계. 컬럼명 정리
# 기대 형식:
# 날짜 | ETF | 매도 | 매수

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().replace("\ufeff", "") for c in df.columns]

    rename_map = {}
    for col in df.columns:
        compact = re.sub(r"\s+", "", col)
        if compact in ["날짜", "date", "Date"]:
            rename_map[col] = "date_raw"
        elif compact.upper() == "ETF":
            rename_map[col] = "etf"
        elif compact in ["매도", "sell", "Sell"]:
            rename_map[col] = "sell_shares"
        elif compact in ["매수", "buy", "Buy"]:
            rename_map[col] = "buy_shares"

    df = df.rename(columns=rename_map)
    required = {"date_raw", "etf", "sell_shares", "buy_shares"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {missing}. 현재 컬럼: {list(df.columns)}")

    return df[["date_raw", "etf", "sell_shares", "buy_shares"]]


ark = normalize_columns(raw)
print("정리된 컬럼:")
display(ark.head(10))


# %%
# 3단계. 날짜와 숫자 정제
# - "6월 10일" -> 2026-06-10
# - "1,665,715" -> 1665715
# - 빈칸/NaN -> 0

def parse_korean_date(value, year: int = YEAR) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT

    text = str(value).strip()

    match = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    if match:
        month, day = map(int, match.groups())
        return pd.Timestamp(year=year, month=month, day=day)

    parsed = pd.to_datetime(text, errors="coerce")
    if pd.notna(parsed):
        if parsed.year == 1900:
            return pd.Timestamp(year=year, month=parsed.month, day=parsed.day)
        return parsed

    raise ValueError(f"날짜를 해석하지 못했습니다: {value}")


def clean_share_number(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(" ", "", regex=False)
        .replace({"": "0", "nan": "0", "None": "0"})
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
        .astype(int)
    )


ark["date"] = ark["date_raw"].apply(parse_korean_date)
ark["etf"] = ark["etf"].astype(str).str.strip().str.upper()
ark["sell_shares"] = clean_share_number(ark["sell_shares"])
ark["buy_shares"] = clean_share_number(ark["buy_shares"])
ark["net_shares"] = ark["buy_shares"] - ark["sell_shares"]

print("정제 후 원자료:")
display(ark)
display(ark.dtypes)


# %%
# 4단계. 날짜별 합산
# 같은 날짜에 ARKK와 ARKG가 같이 있으면 합산합니다.

ark_daily = (
    ark.groupby("date", as_index=False)
    .agg(
        buy_shares=("buy_shares", "sum"),
        sell_shares=("sell_shares", "sum"),
        net_shares=("net_shares", "sum"),
        etfs=("etf", lambda x: ", ".join(sorted(set(x)))),
    )
    .sort_values("date")
)

print("날짜별 ARK 매매 합산:")
display(ark_daily)

print("합계")
print("총 매수:", f"{ark_daily['buy_shares'].sum():,}주")
print("총 매도:", f"{ark_daily['sell_shares'].sum():,}주")
print("순매수:", f"{ark_daily['net_shares'].sum():,}주")


# %%
# 5단계. RXRX 일별 OHLCV 가져오기
# 기본은 yfinance를 사용합니다.
# 설치가 안 되어 있으면 터미널에서 아래 명령을 한 번만 실행하세요:
# pip install yfinance
#
# 인터넷/패키지 문제로 실패할 경우, 아래 fallback 데이터가 사용됩니다.

FALLBACK_RXRX_OHLCV = [
    ("2026-06-10", 3.15, 3.28, 3.03, 3.04, 19_534_855),
    ("2026-06-11", 3.00, 3.16, 2.95, 3.15, 25_424_806),
    ("2026-06-12", 3.20, 3.30, 3.12, 3.15, 14_837_646),
    ("2026-06-15", 3.30, 3.39, 3.23, 3.29, 15_393_576),
    ("2026-06-16", 3.27, 3.34, 3.16, 3.18, 15_477_040),
    ("2026-06-17", 3.18, 3.34, 3.07, 3.11, 22_173_125),
    ("2026-06-18", 3.18, 3.28, 3.11, 3.23, 24_853_721),
    ("2026-06-22", 3.20, 3.32, 3.11, 3.18, 14_444_897),
    ("2026-06-23", 3.10, 3.27, 3.09, 3.16, 11_169_433),
    ("2026-06-24", 3.20, 3.38, 3.16, 3.23, 15_304_675),
    ("2026-06-25", 3.24, 3.38, 3.19, 3.34, 15_562_243),
    ("2026-06-26", 3.29, 3.62, 3.28, 3.52, 42_027_521),
    ("2026-06-29", 3.62, 3.74, 3.55, 3.69, 22_827_048),
    ("2026-06-30", 3.68, 3.72, 3.57, 3.67, 23_055_708),
    ("2026-07-01", 3.65, 4.04, 3.61, 3.67, 35_638_910),
    ("2026-07-02", 3.75, 3.91, 3.70, 3.80, 32_543_230),
    ("2026-07-06", 3.78, 4.09, 3.66, 3.96, 37_974_665),
    ("2026-07-07", 3.95, 4.05, 3.81, 3.84, 28_753_865),
    ("2026-07-08", 3.72, 3.81, 3.63, 3.72, 22_653_988),
]


def load_rxrx_ohlcv(start: pd.Timestamp, end: pd.Timestamp, use_fallback: bool = False) -> pd.DataFrame:
    if not use_fallback:
        try:
            import yfinance as yf

            px = yf.download(
                "RXRX",
                start=start.date(),
                end=(end + pd.Timedelta(days=2)).date(),
                auto_adjust=False,
                progress=False,
            )
            if not px.empty:
                px = px.reset_index()
                px.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower() for c in px.columns]
                px = px.rename(columns={"date": "date"})
                return px[["date", "open", "high", "low", "close", "volume"]]
        except Exception as exc:
            print("[경고] yfinance 다운로드 실패. fallback 데이터를 사용합니다.")
            print("사유:", exc)

    px = pd.DataFrame(FALLBACK_RXRX_OHLCV, columns=["date", "open", "high", "low", "close", "volume"])
    px["date"] = pd.to_datetime(px["date"])
    return px[(px["date"] >= start) & (px["date"] <= end)].copy()


prices = load_rxrx_ohlcv(
    start=ark_daily["date"].min() - pd.Timedelta(days=5),
    end=ark_daily["date"].max(),
    use_fallback=False,
)

print("RXRX 가격 데이터:")
display(prices)


# %%
# 6단계. ARK 매매와 RXRX 가격/거래량 병합

data = prices.merge(ark_daily, on="date", how="left")
for col in ["buy_shares", "sell_shares", "net_shares"]:
    data[col] = data[col].fillna(0).astype(int)
data["etfs"] = data["etfs"].fillna("")

data["daily_return"] = data["close"].pct_change()
data["next_day_return"] = data["close"].pct_change().shift(-1)
data["ark_participation"] = data["net_shares"] / data["volume"]
data["ark_abs_participation"] = data["net_shares"].abs() / data["volume"]
data["ark_dollar_flow_at_close"] = data["net_shares"] * data["close"]
data["cum_net_shares"] = data["net_shares"].cumsum()
data["cum_dollar_flow_at_close"] = data["ark_dollar_flow_at_close"].cumsum()

print("병합 데이터:")
display(data)

missing_price_dates = sorted(set(ark_daily["date"]) - set(prices["date"]))
if missing_price_dates:
    print("주의: 가격 데이터가 없어 병합되지 않은 ARK 거래일")
    print([d.strftime("%Y-%m-%d") for d in missing_price_dates])


# %%
# 7단계. 핵심 지표 요약

trade_days = data[data["net_shares"] != 0].copy()

summary = {
    "분석 기간": f"{data['date'].min().date()} ~ {data['date'].max().date()}",
    "ARK 총 매수": f"{trade_days['buy_shares'].sum():,}주",
    "ARK 총 매도": f"{trade_days['sell_shares'].sum():,}주",
    "ARK 순매수": f"{trade_days['net_shares'].sum():,}주",
    "최대 순매수일": trade_days.loc[trade_days["net_shares"].idxmax(), "date"].strftime("%Y-%m-%d"),
    "최대 순매수량": f"{trade_days['net_shares'].max():,}주",
    "최대 시장참여율": f"{trade_days['ark_abs_participation'].max() * 100:.2f}%",
    "거래일 중앙 시장참여율": f"{trade_days['ark_abs_participation'].median() * 100:.2f}%",
    "RXRX 종가 변화율": f"{(data['close'].iloc[-1] / data['close'].iloc[0] - 1) * 100:.2f}%",
}

summary_df = pd.DataFrame(summary.items(), columns=["지표", "값"])
display(summary_df)


# %%
# 8단계. 그래프 1: 가격, 거래량, ARK 순매수 버블
# 해석 포인트:
# - 초록 버블이 클수록 ARK 순매수가 큽니다.
# - 빨간 버블이 클수록 ARK 순매도가 큽니다.
# - 회색 막대는 RXRX 전체 거래량입니다.

fig, ax1 = plt.subplots(figsize=(15, 6))

ax1.plot(data["date"], data["close"], color="#111827", lw=2.2, label="RXRX close")
ax1.set_ylabel("Close price ($)")
ax1.grid(alpha=0.25)

ax2 = ax1.twinx()
ax2.bar(data["date"], data["volume"] / 1_000_000, color="#cbd5e1", alpha=0.45, width=0.75, label="Volume")
ax2.set_ylabel("Volume (million shares)")

buys = trade_days[trade_days["net_shares"] > 0]
sells = trade_days[trade_days["net_shares"] < 0]

ax1.scatter(
    buys["date"],
    buys["close"],
    s=np.clip(buys["net_shares"].abs() / 900, 50, 1200),
    color="#16a34a",
    alpha=0.72,
    edgecolor="white",
    linewidth=1,
    label="ARK net buy",
)
ax1.scatter(
    sells["date"],
    sells["close"],
    s=np.clip(sells["net_shares"].abs() / 900, 50, 1200),
    color="#dc2626",
    alpha=0.72,
    edgecolor="white",
    linewidth=1,
    label="ARK net sell",
)

for _, row in trade_days.iterrows():
    ax1.annotate(
        f"{row['net_shares'] / 1000:+.0f}k",
        (row["date"], row["close"]),
        xytext=(0, 9 if row["net_shares"] > 0 else -16),
        textcoords="offset points",
        ha="center",
        fontsize=8,
    )

ax1.set_title("ARK RXRX Flow Overlay: Price, Volume, and Net Shares", fontsize=14, weight="bold")
ax1.legend(loc="upper left")
plt.xticks(rotation=30)
plt.show()


# %%
# 9단계. 그래프 2: 시장참여율 지도
# 이 그래프가 가장 핵심입니다.
# x축: 당일 RXRX 수익률
# y축: ARK 순매수 / RXRX 전체 거래량
# 버블 크기: ARK 거래량
# 색상: 다음 거래일 RXRX 수익률

fig, ax = plt.subplots(figsize=(9, 6))

scatter = ax.scatter(
    trade_days["daily_return"].fillna(0) * 100,
    trade_days["ark_participation"] * 100,
    s=np.clip(trade_days["net_shares"].abs() / 850, 60, 1300),
    c=trade_days["next_day_return"].fillna(0) * 100,
    cmap="RdYlGn",
    edgecolor="#111827",
    linewidth=0.7,
    alpha=0.88,
)

ax.axvline(0, color="#64748b", lw=1)
ax.axhline(0, color="#64748b", lw=1)
ax.set_xlabel("Same-day RXRX return (%)")
ax.set_ylabel("ARK net shares / RXRX volume (%)")
ax.set_title("Liquidity Absorption Map", fontsize=14, weight="bold")
ax.grid(alpha=0.25)

for _, row in trade_days.iterrows():
    ax.annotate(
        row["date"].strftime("%m-%d"),
        (
            0 if pd.isna(row["daily_return"]) else row["daily_return"] * 100,
            row["ark_participation"] * 100,
        ),
        xytext=(5, 5),
        textcoords="offset points",
        fontsize=8,
    )

cbar = plt.colorbar(scatter, ax=ax)
cbar.set_label("Next trading-day return (%)")
plt.show()


# %%
# 10단계. 그래프 3: 누적 순매수와 주가 인덱스
# ARK가 순매수로 돌아선 시점과 주가 반등 시점이 겹치는지 확인합니다.

plot_data = data.copy()
plot_data["close_index"] = plot_data["close"] / plot_data["close"].iloc[0] * 100

fig, ax1 = plt.subplots(figsize=(14, 6))

ax1.plot(plot_data["date"], plot_data["close_index"], color="#2563eb", lw=2.2, marker="o", ms=4, label="RXRX close indexed")
ax1.set_ylabel("Close index, first date = 100")
ax1.grid(alpha=0.25)

ax2 = ax1.twinx()
ax2.fill_between(plot_data["date"], plot_data["cum_net_shares"] / 1_000, color="#f59e0b", alpha=0.25)
ax2.plot(plot_data["date"], plot_data["cum_net_shares"] / 1_000, color="#d97706", lw=2.2, label="ARK cumulative net")
ax2.set_ylabel("Cumulative ARK net shares (thousand)")

ax1.set_title("Accumulation vs Price Base", fontsize=14, weight="bold")
plt.xticks(rotation=30)
plt.show()


# %%
# 11단계. 저장
# - 병합 데이터 CSV
# - 요약 CSV
# - 마지막 전체 대시보드 PNG

merged_path = OUTPUT_DIR / "ark_rxrx_merged_dataset.csv"
summary_path = OUTPUT_DIR / "ark_rxrx_summary.csv"

data.to_csv(merged_path, index=False, encoding="utf-8-sig")
summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

print("저장 완료")
print("병합 데이터:", merged_path.resolve())
print("요약 데이터:", summary_path.resolve())


# %%
# 12단계. 자동 해석문 출력
# 이 문장은 투자판단이 아니라 데이터 기반 관찰입니다.

largest_buy = trade_days.loc[trade_days["net_shares"].idxmax()]
largest_footprint = trade_days.loc[trade_days["ark_abs_participation"].idxmax()]

print("[자동 해석]")
print(
    f"- 분석 기간 동안 ARK는 RXRX를 순매수 {trade_days['net_shares'].sum():,.0f}주 기록했습니다."
)
print(
    f"- 최대 순매수일은 {largest_buy['date'].strftime('%Y-%m-%d')}이며, "
    f"순매수 {largest_buy['net_shares']:,.0f}주, 종가 ${largest_buy['close']:.2f}였습니다."
)
print(
    f"- 시장참여율이 가장 컸던 날은 {largest_footprint['date'].strftime('%Y-%m-%d')}이며, "
    f"ARK 순거래가 RXRX 전체 거래량의 {largest_footprint['ark_abs_participation'] * 100:.2f}%였습니다."
)
print(
    "- 단순 매수량보다 시장참여율을 같이 봐야 합니다. "
    "같은 50만 주라도 전체 거래량이 적은 날에는 가격에 미치는 잠재 영향이 더 클 수 있습니다."
)
