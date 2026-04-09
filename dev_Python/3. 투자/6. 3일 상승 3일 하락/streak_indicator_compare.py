import warnings
warnings.filterwarnings('ignore')

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu
import yfinance as yf

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

def set_korean_font_mac():
    """
    macOS용 한글 폰트 설정.
    - 1순위: AppleGothic
    - 2순위: Nanum 계열
    - 3순위: Arial Unicode MS
    - 최후: DejaVu Sans
    """
    available_fonts = {f.name for f in fm.fontManager.ttflist}

    preferred_fonts = [
        "AppleGothic",
        "NanumGothic",
        "NanumMyeongjo",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]

    selected_font = None
    for font_name in preferred_fonts:
        if font_name in available_fonts:
            selected_font = font_name
            break

    if selected_font is None:
        print("[경고] 사용 가능한 한글 폰트를 찾지 못했습니다. 그래프 한글이 깨질 수 있습니다.")
    else:
        plt.rcParams["font.family"] = selected_font
        print(f"[INFO] matplotlib 한글 폰트 설정: {selected_font}")

    # 마이너스 기호 깨짐 방지
    plt.rcParams["axes.unicode_minus"] = False


set_korean_font_mac()


TICKERS = ["RXRX", "SDGR", "TEM", "GLUE", "INTC", "CRSP"]
OUT_DIR = Path("results_streak_compare")
OUT_DIR.mkdir(exist_ok=True)

# 분석 파라미터
MIN_STREAK = 3
RSI_WINDOW = 14
BB_WINDOW = 20
BB_STD = 2
VOL_WINDOW = 20
MA_WINDOWS = [5, 20, 60, 120]


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance가 멀티인덱스 컬럼을 줄 경우 단일 컬럼으로 정리."""
    if isinstance(df.columns, pd.MultiIndex):
        # 보통 (Price, Ticker) 구조이므로 첫 번째 레벨만 사용
        df.columns = [c[0] for c in df.columns]
    return df


def download_data(ticker: str) -> pd.DataFrame:
    df = yf.download(
        ticker,
        period="max",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    df = flatten_columns(df)
    if df.empty:
        raise ValueError(f"{ticker}: 다운로드된 데이터가 없습니다.")

    # Adj Close 우선 사용, 없으면 Close 사용
    if "Adj Close" in df.columns:
        df["Price"] = df["Adj Close"]
    else:
        df["Price"] = df["Close"]

    required = ["Open", "High", "Low", "Close", "Volume", "Price"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{ticker}: 필요한 컬럼이 없습니다: {missing}")

    df = df.dropna(subset=["Price", "Volume"]).copy()
    return df


def calc_rsi(price: pd.Series, window: int = 14) -> pd.Series:
    delta = price.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    # loss가 0이면 RSI=100으로 처리
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100)
    # gain/loss 둘 다 0이면 50으로 처리
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50)
    return rsi


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    price = out["Price"]

    # 수익률
    out["ret_1d"] = price.pct_change()

    # RSI
    out["rsi14"] = calc_rsi(price, RSI_WINDOW)

    # 볼린저밴드
    bb_mid = price.rolling(BB_WINDOW).mean()
    bb_std = price.rolling(BB_WINDOW).std(ddof=0)
    bb_upper = bb_mid + BB_STD * bb_std
    bb_lower = bb_mid - BB_STD * bb_std
    out["bb_mid"] = bb_mid
    out["bb_upper"] = bb_upper
    out["bb_lower"] = bb_lower
    band_width = (bb_upper - bb_lower).replace(0, np.nan)
    out["bb_position"] = (price - bb_lower) / band_width
    out["bb_width_pct"] = band_width / bb_mid.replace(0, np.nan)

    # 이동평균선 및 이격률
    for w in MA_WINDOWS:
        out[f"ma{w}"] = price.rolling(w).mean()
        out[f"ma{w}_gap"] = (price - out[f"ma{w}"]) / out[f"ma{w}"].replace(0, np.nan)

    # 거래량 정규화
    out["vol_ma20"] = out["Volume"].rolling(VOL_WINDOW).mean()
    out["vol_ratio20"] = out["Volume"] / out["vol_ma20"].replace(0, np.nan)

    return out


def find_streak_events(df: pd.DataFrame, min_streak: int = 3) -> pd.DataFrame:
    out = df.copy()
    sign = np.sign(out["ret_1d"].fillna(0))
    sign = sign.replace(0, np.nan)

    out["direction"] = sign

    # 같은 방향 구간 번호 부여
    segment_id = (sign != sign.shift()).cumsum()
    out["segment_id"] = segment_id

    events: List[dict] = []
    for _, seg in out.groupby("segment_id"):
        seg = seg.dropna(subset=["direction"])
        if seg.empty:
            continue
        direction = int(seg["direction"].iloc[0])
        streak_len = len(seg)
        if streak_len >= min_streak:
            end_row = seg.iloc[-1]
            label = "UP" if direction > 0 else "DOWN"
            events.append(
                {
                    "date": seg.index[-1],
                    "event_type": label,
                    "streak_len": streak_len,
                    "ret_sum": seg["ret_1d"].sum(),
                    "rsi14": end_row["rsi14"],
                    "bb_position": end_row["bb_position"],
                    "bb_width_pct": end_row["bb_width_pct"],
                    "ma5_gap": end_row["ma5_gap"],
                    "ma20_gap": end_row["ma20_gap"],
                    "ma60_gap": end_row["ma60_gap"],
                    "ma120_gap": end_row["ma120_gap"],
                    "vol_ratio20": end_row["vol_ratio20"],
                    "close": end_row["Price"],
                }
            )

    events_df = pd.DataFrame(events)
    if not events_df.empty:
        events_df = events_df.set_index("date").sort_index()
    return events_df


def mann_whitney_summary(up: pd.Series, down: pd.Series) -> Tuple[float, float]:
    up = pd.to_numeric(up, errors="coerce").dropna()
    down = pd.to_numeric(down, errors="coerce").dropna()
    if len(up) < 5 or len(down) < 5:
        return np.nan, np.nan
    stat, pvalue = mannwhitneyu(up, down, alternative="two-sided")
    return stat, pvalue


def cliffs_delta(x: pd.Series, y: pd.Series) -> float:
    """효과크기 대체 지표. 계산량이 커질 수 있으므로 표본이 너무 크면 샘플링."""
    x = pd.to_numeric(x, errors="coerce").dropna().to_numpy()
    y = pd.to_numeric(y, errors="coerce").dropna().to_numpy()
    if len(x) == 0 or len(y) == 0:
        return np.nan

    max_n = 2500
    rng = np.random.default_rng(42)
    if len(x) > max_n:
        x = rng.choice(x, size=max_n, replace=False)
    if len(y) > max_n:
        y = rng.choice(y, size=max_n, replace=False)

    diff = np.subtract.outer(x, y)
    gt = np.sum(diff > 0)
    lt = np.sum(diff < 0)
    return (gt - lt) / diff.size


def effect_size_label(delta: float) -> str:
    if pd.isna(delta):
        return "판단 불가"
    ad = abs(delta)
    if ad < 0.147:
        return "매우 작음"
    if ad < 0.33:
        return "작음"
    if ad < 0.474:
        return "중간"
    return "큼"


def compare_groups(events_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    metrics = [
        "rsi14",
        "bb_position",
        "ma20_gap",
        "ma60_gap",
        "vol_ratio20",
        "streak_len",
        "ret_sum",
    ]

    up_df = events_df[events_df["event_type"] == "UP"]
    down_df = events_df[events_df["event_type"] == "DOWN"]

    rows = []
    for metric in metrics:
        up = up_df[metric].dropna()
        down = down_df[metric].dropna()
        _, pvalue = mann_whitney_summary(up, down)
        delta = cliffs_delta(up, down)
        rows.append(
            {
                "ticker": ticker,
                "metric": metric,
                "n_up": len(up),
                "n_down": len(down),
                "up_mean": up.mean() if len(up) else np.nan,
                "down_mean": down.mean() if len(down) else np.nan,
                "up_median": up.median() if len(up) else np.nan,
                "down_median": down.median() if len(down) else np.nan,
                "diff_mean_up_minus_down": (up.mean() - down.mean()) if len(up) and len(down) else np.nan,
                "pvalue_mannwhitney": pvalue,
                "cliffs_delta": delta,
                "effect_size": effect_size_label(delta),
            }
        )

    return pd.DataFrame(rows)


def make_boxplot_figure(events_df: pd.DataFrame, ticker: str, out_dir: Path) -> None:
    metrics = [
        ("rsi14", "RSI(14)"),
        ("bb_position", "Bollinger Position"),
        ("ma20_gap", "MA20 Gap"),
        ("vol_ratio20", "Volume / 20D Avg"),
    ]

    up_df = events_df[events_df["event_type"] == "UP"]
    down_df = events_df[events_df["event_type"] == "DOWN"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.ravel()

    for ax, (metric, title) in zip(axes, metrics):
        data = [down_df[metric].dropna(), up_df[metric].dropna()]
        ax.boxplot(data, labels=["DOWN>=3", "UP>=3"], showfliers=False)
        ax.set_title(f"{ticker} - {title}")
        ax.grid(alpha=0.3)

    fig.suptitle(f"{ticker}: 3일 이상 상승 vs 3일 이상 하락 이벤트 비교", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_dir / f"{ticker}_boxplots.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def make_mean_diff_figure(summary_df: pd.DataFrame, out_dir: Path) -> None:
    metrics = ["rsi14", "bb_position", "ma20_gap", "ma60_gap", "vol_ratio20"]
    plot_df = summary_df[summary_df["metric"].isin(metrics)].copy()

    n_metrics = len(metrics)
    fig, axes = plt.subplots(n_metrics, 1, figsize=(12, 3 * n_metrics), sharex=True)
    if n_metrics == 1:
        axes = [axes]

    for ax, metric in zip(axes, metrics):
        temp = plot_df[plot_df["metric"] == metric].copy()
        temp = temp.set_index("ticker").reindex(TICKERS).reset_index()
        ax.bar(temp["ticker"], temp["diff_mean_up_minus_down"])
        ax.axhline(0, linestyle="--", linewidth=1)
        ax.set_title(f"평균 차이 (UP - DOWN): {metric}")
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("종목별 평균 차이 비교", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_dir / "all_tickers_mean_diff.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def interpret_metric(row: pd.Series) -> str:
    metric_map = {
        "rsi14": "RSI",
        "bb_position": "볼린저 밴드 내 위치",
        "ma20_gap": "20일 이동평균 이격률",
        "ma60_gap": "60일 이동평균 이격률",
        "vol_ratio20": "거래량/20일 평균거래량",
        "streak_len": "연속일수",
        "ret_sum": "구간 누적수익률",
    }
    name = metric_map.get(row["metric"], row["metric"])
    pvalue = row["pvalue_mannwhitney"]
    diff = row["diff_mean_up_minus_down"]
    eff = row["effect_size"]

    if pd.isna(diff):
        return f"- {name}: 표본 부족으로 판단 불가"

    direction = "상승 구간에서 더 큼" if diff > 0 else "하락 구간에서 더 큼"
    sig = "통계적으로 뚜렷함" if pd.notna(pvalue) and pvalue < 0.05 else "통계적으로 뚜렷하지 않음"
    return f"- {name}: {direction} / 평균차이={diff:.4f} / p={pvalue:.4g if pd.notna(pvalue) else np.nan} / 효과크기={eff} / {sig}"


def save_interpretation(summary_df: pd.DataFrame, out_dir: Path) -> None:
    lines: List[str] = []
    for ticker in TICKERS:
        lines.append(f"\n===== {ticker} =====")
        temp = summary_df[summary_df["ticker"] == ticker].copy()
        if temp.empty:
            lines.append("분석 결과 없음")
            continue

        core_metrics = ["rsi14", "bb_position", "ma20_gap", "ma60_gap", "vol_ratio20"]
        temp_core = temp[temp["metric"].isin(core_metrics)].copy()
        for _, row in temp_core.iterrows():
            # format issue 회피용 수동 작성
            pvalue = row["pvalue_mannwhitney"]
            diff = row["diff_mean_up_minus_down"]
            eff = row["effect_size"]
            metric_name = {
                "rsi14": "RSI",
                "bb_position": "볼린저 밴드 내 위치",
                "ma20_gap": "20일 이동평균 이격률",
                "ma60_gap": "60일 이동평균 이격률",
                "vol_ratio20": "거래량/20일 평균거래량",
            }[row["metric"]]
            if pd.isna(diff):
                lines.append(f"- {metric_name}: 표본 부족으로 판단 불가")
                continue
            direction = "상승 구간이 더 높음" if diff > 0 else "하락 구간이 더 높음"
            sig = "유의" if pd.notna(pvalue) and pvalue < 0.05 else "비유의"
            ptxt = f"{pvalue:.4g}" if pd.notna(pvalue) else "nan"
            lines.append(
                f"- {metric_name}: {direction}, 평균차이={diff:.4f}, p={ptxt}, 효과크기={eff}, {sig}"
            )

        # 요약 코멘트
        sig_rows = temp_core[temp_core["pvalue_mannwhitney"] < 0.05].copy()
        if sig_rows.empty:
            lines.append("요약: 상승 3일 이상 구간과 하락 3일 이상 구간의 차이가 뚜렷하지 않거나, 표본/분포상 확신이 약함.")
        else:
            biggest = sig_rows.iloc[sig_rows["cliffs_delta"].abs().argmax()]
            key_metric = {
                "rsi14": "RSI",
                "bb_position": "볼린저 밴드 위치",
                "ma20_gap": "20일선 이격",
                "ma60_gap": "60일선 이격",
                "vol_ratio20": "거래량 비율",
            }[biggest["metric"]]
            direction = "상승 구간 우위" if biggest["diff_mean_up_minus_down"] > 0 else "하락 구간 우위"
            lines.append(f"요약: 가장 두드러진 차이는 {key_metric}이며, {direction} 패턴이 관찰됨.")

    (out_dir / "interpretation.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    all_summary = []
    event_counts = []

    for ticker in TICKERS:
        print(f"[1/4] {ticker} 다운로드 및 지표 계산 중...")
        try:
            df = download_data(ticker)
            df = add_indicators(df)
            events_df = find_streak_events(df, MIN_STREAK)

            if events_df.empty:
                print(f"  - {ticker}: 이벤트가 없습니다.")
                continue

            # 개별 저장
            df.to_csv(OUT_DIR / f"{ticker}_daily_with_indicators.csv", encoding="utf-8-sig")
            events_df.to_csv(OUT_DIR / f"{ticker}_events.csv", encoding="utf-8-sig")

            up_n = int((events_df["event_type"] == "UP").sum())
            down_n = int((events_df["event_type"] == "DOWN").sum())
            event_counts.append(
                {
                    "ticker": ticker,
                    "start_date": df.index.min().date(),
                    "end_date": df.index.max().date(),
                    "rows": len(df),
                    "up_events": up_n,
                    "down_events": down_n,
                }
            )

            summary_df = compare_groups(events_df, ticker)
            all_summary.append(summary_df)
            make_boxplot_figure(events_df, ticker, OUT_DIR)
            print(f"  - {ticker}: 완료 (UP={up_n}, DOWN={down_n})")

        except Exception as e:
            print(f"  - {ticker}: 오류 발생 -> {e}")

    if not all_summary:
        print("분석 가능한 종목이 없습니다.")
        return

    summary_all = pd.concat(all_summary, ignore_index=True)
    counts_df = pd.DataFrame(event_counts)

    counts_df.to_csv(OUT_DIR / "event_counts.csv", index=False, encoding="utf-8-sig")
    summary_all.to_csv(OUT_DIR / "comparison_summary.csv", index=False, encoding="utf-8-sig")
    make_mean_diff_figure(summary_all, OUT_DIR)
    save_interpretation(summary_all, OUT_DIR)

    print("\n=== 분석 완료 ===")
    print(f"결과 폴더: {OUT_DIR.resolve()}")
    print("생성 파일:")
    print("- 종목별 일봉+지표 CSV")
    print("- 종목별 이벤트 CSV")
    print("- 종목별 박스플롯 PNG")
    print("- 전체 요약 comparison_summary.csv")
    print("- 전체 평균차이 그래프 all_tickers_mean_diff.png")
    print("- 해석 파일 interpretation.txt")


if __name__ == "__main__":
    main()
