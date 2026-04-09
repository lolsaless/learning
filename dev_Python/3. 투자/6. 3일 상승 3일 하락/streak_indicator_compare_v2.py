import warnings
warnings.filterwarnings('ignore')

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu, ttest_ind, ks_2samp
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


# =========================
# 사용자 설정
# =========================
TICKERS = ["RXRX", "SDGR", "TEM", "GLUE", "INTC", "CRSP"]
OUT_DIR = Path("results_streak_compare_v2")
OUT_DIR.mkdir(exist_ok=True)

MIN_STREAK = 3
# 변화폭 기준: 0.01 = 1%
UP_THRESHOLD = 0.01
DOWN_THRESHOLD = -0.01

RSI_WINDOW = 14
BB_WINDOW = 20
BB_STD = 2
VOL_WINDOW = 20
MA_WINDOWS = [5, 20, 60, 120]
RANDOM_SEED = 42

METRIC_INFO = {
    "rsi14": "RSI(14)",
    "bb_position": "볼린저 밴드 위치",
    "bb_width_pct": "볼린저 밴드 폭%",
    "ma20_gap": "20일선 이격률",
    "ma60_gap": "60일선 이격률",
    "vol_ratio20": "거래량/20일 평균",
    "streak_len": "연속 일수",
    "ret_sum": "구간 누적수익률",
}

CORE_METRICS = [
    "rsi14",
    "bb_position",
    "bb_width_pct",
    "ma20_gap",
    "ma60_gap",
    "vol_ratio20",
    "streak_len",
    "ret_sum",
]


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
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

    if "Adj Close" in df.columns:
        df["Price"] = df["Adj Close"]
    else:
        df["Price"] = df["Close"]

    required = ["Open", "High", "Low", "Close", "Volume", "Price"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{ticker}: 필요한 컬럼이 없습니다: {missing}")

    df = df.dropna(subset=["Price", "Volume"]).copy()
    df.index = pd.to_datetime(df.index)
    return df


def calc_rsi(price: pd.Series, window: int = 14) -> pd.Series:
    delta = price.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100)
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50)
    return rsi


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    price = out["Price"]

    out["ret_1d"] = price.pct_change()
    out["rsi14"] = calc_rsi(price, RSI_WINDOW)

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

    for w in MA_WINDOWS:
        out[f"ma{w}"] = price.rolling(w).mean()
        out[f"ma{w}_gap"] = (price - out[f"ma{w}"]) / out[f"ma{w}"].replace(0, np.nan)

    out["vol_ma20"] = out["Volume"].rolling(VOL_WINDOW).mean()
    out["vol_ratio20"] = out["Volume"] / out["vol_ma20"].replace(0, np.nan)

    return out


def classify_move(ret: pd.Series, up_threshold: float, down_threshold: float) -> pd.Series:
    signal = pd.Series(np.nan, index=ret.index, dtype=float)
    signal.loc[ret >= up_threshold] = 1.0
    signal.loc[ret <= down_threshold] = -1.0
    return signal


def find_streak_events(
    df: pd.DataFrame,
    min_streak: int = 3,
    up_threshold: float = 0.01,
    down_threshold: float = -0.01,
) -> pd.DataFrame:
    out = df.copy()
    signal = classify_move(out["ret_1d"], up_threshold, down_threshold)
    out["direction"] = signal

    # 임계값 미만 구간은 끊긴 것으로 처리
    segment_break = (signal != signal.shift()) | signal.isna()
    out["segment_id"] = segment_break.cumsum()

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
                    "ret_mean": seg["ret_1d"].mean(),
                    "event_threshold": up_threshold if label == "UP" else abs(down_threshold),
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


def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").dropna()


def cliffs_delta(x: pd.Series, y: pd.Series) -> float:
    x = safe_numeric(x).to_numpy()
    y = safe_numeric(y).to_numpy()
    if len(x) == 0 or len(y) == 0:
        return np.nan

    rng = np.random.default_rng(RANDOM_SEED)
    max_n = 2500
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


def common_language_effect_size(x: pd.Series, y: pd.Series) -> float:
    x = safe_numeric(x).to_numpy()
    y = safe_numeric(y).to_numpy()
    if len(x) == 0 or len(y) == 0:
        return np.nan

    rng = np.random.default_rng(RANDOM_SEED)
    max_n = 2500
    if len(x) > max_n:
        x = rng.choice(x, size=max_n, replace=False)
    if len(y) > max_n:
        y = rng.choice(y, size=max_n, replace=False)

    diff = np.subtract.outer(x, y)
    return (np.sum(diff > 0) + 0.5 * np.sum(diff == 0)) / diff.size


def bootstrap_ci_mean_diff(x: pd.Series, y: pd.Series, n_boot: int = 2000) -> Tuple[float, float]:
    x = safe_numeric(x).to_numpy()
    y = safe_numeric(y).to_numpy()
    if len(x) < 5 or len(y) < 5:
        return np.nan, np.nan

    rng = np.random.default_rng(RANDOM_SEED)
    boot = []
    for _ in range(n_boot):
        xs = rng.choice(x, size=len(x), replace=True)
        ys = rng.choice(y, size=len(y), replace=True)
        boot.append(xs.mean() - ys.mean())
    return tuple(np.percentile(boot, [2.5, 97.5]))


def statistical_tests(up: pd.Series, down: pd.Series) -> Dict[str, float]:
    up = safe_numeric(up)
    down = safe_numeric(down)
    result = {
        "pvalue_mannwhitney": np.nan,
        "pvalue_welch_t": np.nan,
        "pvalue_ks": np.nan,
        "cliffs_delta": np.nan,
        "cles_up_gt_down": np.nan,
        "ci95_low": np.nan,
        "ci95_high": np.nan,
    }
    if len(up) < 5 or len(down) < 5:
        return result

    try:
        result["pvalue_mannwhitney"] = mannwhitneyu(up, down, alternative="two-sided").pvalue
    except Exception:
        pass

    try:
        result["pvalue_welch_t"] = ttest_ind(up, down, equal_var=False, nan_policy="omit").pvalue
    except Exception:
        pass

    try:
        result["pvalue_ks"] = ks_2samp(up, down, alternative="two-sided", method="auto").pvalue
    except Exception:
        pass

    result["cliffs_delta"] = cliffs_delta(up, down)
    result["cles_up_gt_down"] = common_language_effect_size(up, down)
    result["ci95_low"], result["ci95_high"] = bootstrap_ci_mean_diff(up, down)
    return result


def compare_groups(events_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    up_df = events_df[events_df["event_type"] == "UP"]
    down_df = events_df[events_df["event_type"] == "DOWN"]

    rows = []
    for metric in CORE_METRICS:
        up = safe_numeric(up_df[metric])
        down = safe_numeric(down_df[metric])
        tests = statistical_tests(up, down)

        rows.append(
            {
                "ticker": ticker,
                "metric": metric,
                "metric_label": METRIC_INFO[metric],
                "n_up": len(up),
                "n_down": len(down),
                "up_mean": up.mean() if len(up) else np.nan,
                "down_mean": down.mean() if len(down) else np.nan,
                "up_median": up.median() if len(up) else np.nan,
                "down_median": down.median() if len(down) else np.nan,
                "up_std": up.std(ddof=1) if len(up) > 1 else np.nan,
                "down_std": down.std(ddof=1) if len(down) > 1 else np.nan,
                "up_var": up.var(ddof=1) if len(up) > 1 else np.nan,
                "down_var": down.var(ddof=1) if len(down) > 1 else np.nan,
                "up_iqr": (up.quantile(0.75) - up.quantile(0.25)) if len(up) else np.nan,
                "down_iqr": (down.quantile(0.75) - down.quantile(0.25)) if len(down) else np.nan,
                "diff_mean_up_minus_down": (up.mean() - down.mean()) if len(up) and len(down) else np.nan,
                **tests,
                "effect_size": effect_size_label(tests["cliffs_delta"]),
            }
        )

    return pd.DataFrame(rows)


def build_display_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    display_rows = []
    for _, row in summary_df.iterrows():
        display_rows.append(
            {
                "ticker": row["ticker"],
                "지표": row["metric_label"],
                "상승 평균": row["up_mean"],
                "하락 평균": row["down_mean"],
                "평균 차이(상승-하락)": row["diff_mean_up_minus_down"],
                "상승 표준편차": row["up_std"],
                "하락 표준편차": row["down_std"],
                "상승 분산": row["up_var"],
                "하락 분산": row["down_var"],
                "상승 표본수": row["n_up"],
                "하락 표본수": row["n_down"],
                "Mann-Whitney p": row["pvalue_mannwhitney"],
                "Welch t-test p": row["pvalue_welch_t"],
                "KS test p": row["pvalue_ks"],
                "Cliff's delta": row["cliffs_delta"],
                "CLES(상승>하락)": row["cles_up_gt_down"],
                "95% CI Low": row["ci95_low"],
                "95% CI High": row["ci95_high"],
                "효과크기": row["effect_size"],
            }
        )
    return pd.DataFrame(display_rows)


def make_ticker_mean_std_chart(summary_df: pd.DataFrame, ticker: str, out_dir: Path) -> None:
    temp = summary_df[summary_df["ticker"] == ticker].copy()
    if temp.empty:
        return

    n = len(temp)
    fig, axes = plt.subplots(n, 1, figsize=(12, 2.5 * n), constrained_layout=True)
    if n == 1:
        axes = [axes]

    for ax, (_, row) in zip(axes, temp.iterrows()):
        means = [row["up_mean"], row["down_mean"]]
        errs = [row["up_std"], row["down_std"]]
        labels = ["상승", "하락"]
        x = np.arange(2)
        ax.bar(x, means, yerr=errs, capsize=5)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_title(f"{ticker} | {row['metric_label']}")
        ax.axhline(0, linestyle="--", linewidth=1)
        ax.grid(axis="y", alpha=0.3)
        for xi, yi in zip(x, means):
            if pd.notna(yi):
                ax.text(xi, yi, f" {yi:.4f}", va="bottom" if yi >= 0 else "top")

    fig.suptitle(f"{ticker}: 상승 vs 하락 평균 및 표준편차", fontsize=14)
    fig.savefig(out_dir / f"{ticker}_mean_std_bars.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def make_ticker_heatmap(summary_df: pd.DataFrame, ticker: str, out_dir: Path) -> None:
    temp = summary_df[summary_df["ticker"] == ticker].copy()
    if temp.empty:
        return

    temp = temp.set_index("metric_label")[[
        "up_mean",
        "down_mean",
        "diff_mean_up_minus_down",
        "up_std",
        "down_std",
        "pvalue_mannwhitney",
        "cliffs_delta",
    ]]
    temp.columns = [
        "상승 평균",
        "하락 평균",
        "평균 차이",
        "상승 표준편차",
        "하락 표준편차",
        "MW p값",
        "Cliff's d",
    ]

    data = temp.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(11, max(4, 0.8 * len(temp))))
    im = ax.imshow(data, aspect="auto")
    ax.set_xticks(np.arange(len(temp.columns)))
    ax.set_xticklabels(temp.columns, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(temp.index)))
    ax.set_yticklabels(temp.index)
    ax.set_title(f"{ticker}: 요약 통계 히트맵")

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            txt = "nan" if pd.isna(value) else f"{value:.3f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=8)

    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(out_dir / f"{ticker}_summary_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def make_cross_ticker_diff_chart(summary_df: pd.DataFrame, out_dir: Path) -> None:
    metrics = [m for m in CORE_METRICS if m in summary_df["metric"].unique()]
    fig, axes = plt.subplots(len(metrics), 1, figsize=(12, 3 * len(metrics)), sharex=True, constrained_layout=True)
    if len(metrics) == 1:
        axes = [axes]

    for ax, metric in zip(axes, metrics):
        temp = summary_df[summary_df["metric"] == metric].set_index("ticker").reindex(TICKERS).reset_index()
        ax.bar(temp["ticker"], temp["diff_mean_up_minus_down"])
        ax.axhline(0, linestyle="--", linewidth=1)
        ax.set_title(f"평균 차이(상승-하락) | {METRIC_INFO[metric]}")
        ax.grid(axis="y", alpha=0.3)
    fig.savefig(out_dir / "all_tickers_mean_diff.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def make_cross_ticker_heatmap(summary_df: pd.DataFrame, out_dir: Path) -> None:
    pivot = summary_df.pivot(index="ticker", columns="metric_label", values="diff_mean_up_minus_down")
    pivot = pivot.reindex(TICKERS)
    data = pivot.to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(14, 5))
    im = ax.imshow(data, aspect="auto")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("종목별 평균 차이(상승-하락) 히트맵")

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            txt = "nan" if pd.isna(value) else f"{value:.3f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=8)

    fig.colorbar(im, ax=ax, shrink=0.85)
    fig.tight_layout()
    fig.savefig(out_dir / "all_tickers_diff_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_text_interpretation(summary_df: pd.DataFrame, out_dir: Path) -> None:
    lines: List[str] = []
    lines.append("[분석 정의]")
    lines.append(f"- 상승 이벤트: 일일 수익률이 {UP_THRESHOLD:.2%} 이상인 날이 {MIN_STREAK}일 이상 연속된 구간의 마지막 날")
    lines.append(f"- 하락 이벤트: 일일 수익률이 {abs(DOWN_THRESHOLD):.2%} 이상 하락한 날이 {MIN_STREAK}일 이상 연속된 구간의 마지막 날")
    lines.append("- 평균 비교만이 아니라, 분산/표준편차/비모수 검정/분포 검정/효과크기를 함께 봄")
    lines.append("")
    lines.append("[검정 해석 기준]")
    lines.append("- Mann-Whitney p: 두 그룹의 중심 차이를 비모수적으로 비교")
    lines.append("- Welch t-test p: 평균 차이를 비교하되 분산이 달라도 허용")
    lines.append("- KS test p: 분포 전체 모양이 다른지 확인")
    lines.append("- Cliff's delta: 효과크기. 절댓값이 클수록 실제 차이가 큼")
    lines.append("- CLES: 임의의 상승 이벤트 값이 하락 이벤트 값보다 클 확률")
    lines.append("- 95% CI: 평균 차이의 부트스트랩 신뢰구간. 0을 포함하지 않으면 방향성 신뢰가 높음")

    for ticker in TICKERS:
        temp = summary_df[summary_df["ticker"] == ticker].copy()
        lines.append("")
        lines.append(f"===== {ticker} =====")
        if temp.empty:
            lines.append("- 분석 결과 없음")
            continue

        for _, row in temp.iterrows():
            diff = row["diff_mean_up_minus_down"]
            p_mw = row["pvalue_mannwhitney"]
            p_ks = row["pvalue_ks"]
            direction = "상승 쪽이 더 큼" if pd.notna(diff) and diff > 0 else "하락 쪽이 더 큼"
            mw_txt = f"{p_mw:.4g}" if pd.notna(p_mw) else "nan"
            ks_txt = f"{p_ks:.4g}" if pd.notna(p_ks) else "nan"
            ci_low = row["ci95_low"]
            ci_high = row["ci95_high"]
            ci_txt = "[nan, nan]" if pd.isna(ci_low) else f"[{ci_low:.4f}, {ci_high:.4f}]"
            lines.append(
                f"- {row['metric_label']}: {direction}, 평균차이={diff:.4f}, 상승평균={row['up_mean']:.4f}, 하락평균={row['down_mean']:.4f}, "
                f"상승표준편차={row['up_std']:.4f}, 하락표준편차={row['down_std']:.4f}, MW p={mw_txt}, KS p={ks_txt}, "
                f"Cliff's d={row['cliffs_delta']:.4f}, CLES={row['cles_up_gt_down']:.4f}, 95%CI={ci_txt}, 효과크기={row['effect_size']}"
            )

        sig = temp[(temp["pvalue_mannwhitney"] < 0.05) | (temp["pvalue_ks"] < 0.05)].copy()
        if sig.empty:
            lines.append("요약: 평균이나 분포 차이가 뚜렷하다고 보기 어려운 지표가 많음. 이 경우 특정 지표에 과도한 의미를 두면 안 됨.")
        else:
            strongest = sig.iloc[sig["cliffs_delta"].abs().argmax()]
            dir_text = "상승 이벤트가 더 높음" if strongest["diff_mean_up_minus_down"] > 0 else "하락 이벤트가 더 높음"
            lines.append(f"요약: 가장 눈에 띄는 차이는 '{strongest['metric_label']}'이며, {dir_text}.")

    (out_dir / "interpretation.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    all_summary = []
    event_counts = []

    print("=== 분석 시작 ===")
    print(f"상승 기준: 일일 수익률 >= {UP_THRESHOLD:.2%}")
    print(f"하락 기준: 일일 수익률 <= {DOWN_THRESHOLD:.2%}")
    print(f"최소 연속일수: {MIN_STREAK}일")

    for ticker in TICKERS:
        print(f"\n[{ticker}] 다운로드 및 분석 중...")
        try:
            df = download_data(ticker)
            df = add_indicators(df)
            events_df = find_streak_events(
                df,
                min_streak=MIN_STREAK,
                up_threshold=UP_THRESHOLD,
                down_threshold=DOWN_THRESHOLD,
            )

            if events_df.empty:
                print(f"  - {ticker}: 이벤트 없음")
                continue

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

            df.to_csv(OUT_DIR / f"{ticker}_daily_with_indicators.csv", encoding="utf-8-sig")
            events_df.to_csv(OUT_DIR / f"{ticker}_events.csv", encoding="utf-8-sig")
            print(f"  - {ticker}: 완료 (상승 이벤트={up_n}, 하락 이벤트={down_n})")

        except Exception as e:
            print(f"  - {ticker}: 오류 발생 -> {e}")

    if not all_summary:
        print("분석 가능한 종목이 없습니다.")
        return

    summary_all = pd.concat(all_summary, ignore_index=True)
    display_summary = build_display_summary(summary_all)
    counts_df = pd.DataFrame(event_counts)

    counts_df.to_csv(OUT_DIR / "event_counts.csv", index=False, encoding="utf-8-sig")
    summary_all.to_csv(OUT_DIR / "comparison_summary_raw.csv", index=False, encoding="utf-8-sig")
    display_summary.to_csv(OUT_DIR / "comparison_summary_display.csv", index=False, encoding="utf-8-sig")

    for ticker in TICKERS:
        make_ticker_mean_std_chart(summary_all, ticker, OUT_DIR)
        make_ticker_heatmap(summary_all, ticker, OUT_DIR)

    make_cross_ticker_diff_chart(summary_all, OUT_DIR)
    make_cross_ticker_heatmap(summary_all, OUT_DIR)
    save_text_interpretation(summary_all, OUT_DIR)

    print("\n=== 분석 완료 ===")
    print(f"결과 폴더: {OUT_DIR.resolve()}")
    print("생성 파일:")
    print("- 종목별 일봉+지표 CSV")
    print("- 종목별 이벤트 CSV")
    print("- comparison_summary_raw.csv")
    print("- comparison_summary_display.csv")
    print("- 종목별 mean_std_bars / summary_heatmap PNG")
    print("- all_tickers_mean_diff.png")
    print("- all_tickers_diff_heatmap.png")
    print("- interpretation.txt")


if __name__ == "__main__":
    main()
