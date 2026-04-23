
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant
from statsmodels.tsa.stattools import adfuller, coint, kpss


st.set_page_config(page_title="Pairs Trading Pro v3", layout="wide")


@dataclass
class PairDiagnostics:
    y: str
    x: str
    corr_returns: float
    hedge_ratio: float
    coint_pvalue: float
    coint_stat: float
    spread_adf_pvalue: float
    spread_adf_stat: float
    spread_kpss_pvalue: float
    half_life: float
    hurst: float
    score: float
    is_candidate: bool


def safe_float(x, default=np.nan):
    try:
        return float(x)
    except Exception:
        return default


def annualization_factor(interval: str) -> float:
    if interval == "1d":
        return 252.0
    if interval == "1h":
        return 252.0 * 6.5
    return 252.0


@st.cache_data(ttl=300, show_spinner=False)
def load_prices(tickers: List[str], period: str, interval: str) -> pd.DataFrame:
    data = yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    if data.empty:
        raise ValueError("가격 데이터를 불러오지 못했습니다.")
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"].copy()
    else:
        close = data[["Close"]].copy()
        close.columns = tickers[:1]
    return close.dropna(how="all").ffill().dropna()


def estimate_hedge_ratio(y: pd.Series, x: pd.Series, use_log: bool = True) -> Tuple[float, float]:
    if use_log:
        y_ = np.log(y)
        x_ = np.log(x)
    else:
        y_, x_ = y.copy(), x.copy()
    model = OLS(y_, add_constant(x_)).fit()
    alpha = safe_float(model.params.iloc[0])
    beta = safe_float(model.params.iloc[1])
    return alpha, beta


def compute_spread(y: pd.Series, x: pd.Series, alpha: float, beta: float, use_log: bool = True) -> pd.Series:
    if use_log:
        return np.log(y) - (alpha + beta * np.log(x))
    return y - (alpha + beta * x)


def run_adf(series: pd.Series) -> Dict[str, float]:
    s = series.dropna()
    if len(s) < 30:
        return {"stat": np.nan, "pvalue": np.nan}
    stat, pvalue, *_ = adfuller(s, autolag="AIC")
    return {"stat": stat, "pvalue": pvalue}


def run_kpss(series: pd.Series) -> Dict[str, float]:
    s = series.dropna()
    if len(s) < 30:
        return {"stat": np.nan, "pvalue": np.nan}
    try:
        stat, pvalue, *_ = kpss(s, regression="c", nlags="auto")
        return {"stat": stat, "pvalue": pvalue}
    except Exception:
        return {"stat": np.nan, "pvalue": np.nan}


def run_coint(y: pd.Series, x: pd.Series) -> Dict[str, float]:
    yy = np.log(y)
    xx = np.log(x)
    stat, pvalue, crit = coint(yy, xx, trend="c", autolag="aic")
    return {"stat": stat, "pvalue": pvalue, "crit_1%": crit[0], "crit_5%": crit[1], "crit_10%": crit[2]}


def estimate_half_life(spread: pd.Series) -> float:
    s = spread.dropna()
    if len(s) < 30:
        return np.nan
    lagged = s.shift(1)
    delta = s.diff()
    reg = pd.concat([lagged, delta], axis=1).dropna()
    reg.columns = ["lagged", "delta"]
    if len(reg) < 20:
        return np.nan
    model = OLS(reg["delta"], add_constant(reg["lagged"])).fit()
    phi = safe_float(model.params["lagged"])
    if np.isnan(phi) or phi >= 0:
        return np.nan
    hl = -np.log(2.0) / phi
    if np.isinf(hl) or hl <= 0:
        return np.nan
    return float(hl)


def hurst_exponent(series: pd.Series, max_lag: int = 20) -> float:
    s = series.dropna().values
    if len(s) < max_lag + 10:
        return np.nan
    lags = np.arange(2, max_lag)
    tau = []
    for lag in lags:
        diff = s[lag:] - s[:-lag]
        val = np.sqrt(np.std(diff))
        tau.append(val if np.isfinite(val) and val > 0 else np.nan)
    tau = np.array(tau)
    valid = np.isfinite(tau) & (tau > 0)
    if valid.sum() < 5:
        return np.nan
    poly = np.polyfit(np.log(lags[valid]), np.log(tau[valid]), 1)
    return float(poly[0] * 2.0)


def diagnostic_score(coint_p: float, adf_p: float, kpss_p: float, hl: float, hurst: float) -> float:
    score = 0.0
    if np.isfinite(coint_p):
        score += max(0, 30 * (0.10 - coint_p) / 0.10)
    if np.isfinite(adf_p):
        score += max(0, 25 * (0.10 - adf_p) / 0.10)
    if np.isfinite(kpss_p):
        score += max(0, 15 * min(kpss_p, 0.10) / 0.10)
    if np.isfinite(hl):
        if 3 <= hl <= 60:
            score += 20
        elif 1 <= hl < 3 or 60 < hl <= 120:
            score += 10
    if np.isfinite(hurst):
        if hurst < 0.45:
            score += 10
        elif hurst < 0.55:
            score += 5
    return float(score)


def analyze_pair(prices: pd.DataFrame, y_ticker: str, x_ticker: str, use_log: bool = True) -> PairDiagnostics:
    pair = prices[[y_ticker, x_ticker]].dropna()
    y, x = pair[y_ticker], pair[x_ticker]
    alpha, beta = estimate_hedge_ratio(y, x, use_log=use_log)
    spread = compute_spread(y, x, alpha, beta, use_log=use_log)
    coint_res = run_coint(y, x)
    adf_res = run_adf(spread)
    kpss_res = run_kpss(spread)
    hl = estimate_half_life(spread)
    hurst = hurst_exponent(spread)
    corr = y.pct_change().corr(x.pct_change())
    score = diagnostic_score(coint_res["pvalue"], adf_res["pvalue"], kpss_res["pvalue"], hl, hurst)
    is_candidate = (
        np.isfinite(coint_res["pvalue"]) and coint_res["pvalue"] < 0.05
        and np.isfinite(adf_res["pvalue"]) and adf_res["pvalue"] < 0.05
        and (not np.isfinite(kpss_res["pvalue"]) or kpss_res["pvalue"] > 0.05)
    )
    return PairDiagnostics(
        y=y_ticker,
        x=x_ticker,
        corr_returns=safe_float(corr),
        hedge_ratio=beta,
        coint_pvalue=coint_res["pvalue"],
        coint_stat=coint_res["stat"],
        spread_adf_pvalue=adf_res["pvalue"],
        spread_adf_stat=adf_res["stat"],
        spread_kpss_pvalue=kpss_res["pvalue"],
        half_life=hl,
        hurst=hurst,
        score=score,
        is_candidate=is_candidate,
    )


def scan_all_pairs(prices: pd.DataFrame, use_log: bool = True) -> pd.DataFrame:
    rows = []
    for y, x in combinations(prices.columns.tolist(), 2):
        try:
            d = analyze_pair(prices, y, x, use_log=use_log)
            rows.append(d.__dict__)
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.sort_values(["score", "coint_pvalue", "spread_adf_pvalue"], ascending=[False, True, True]).reset_index(drop=True)


def walkforward_backtest(
    prices: pd.DataFrame,
    y_ticker: str,
    x_ticker: str,
    formation_window: int = 252,
    z_window: int = 60,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    stop_z: float = 4.0,
    coint_p_threshold: float = 0.05,
    adf_p_threshold: float = 0.10,
    transaction_cost_bps: float = 5.0,
    rebalance_every: int = 5,
    use_log: bool = True,
    interval: str = "1d",
) -> Tuple[pd.DataFrame, Dict]:
    pair = prices[[y_ticker, x_ticker]].dropna().copy()
    y = pair[y_ticker]
    x = pair[x_ticker]
    if len(pair) < formation_window + z_window + 10:
        raise ValueError("데이터 길이가 부족합니다.")

    df = pair.copy()
    df.columns = ["y", "x"]
    df["ret_y"] = df["y"].pct_change().fillna(0.0)
    df["ret_x"] = df["x"].pct_change().fillna(0.0)

    alpha_series = pd.Series(index=df.index, dtype=float)
    beta_series = pd.Series(index=df.index, dtype=float)
    valid_series = pd.Series(index=df.index, dtype=float)
    spread_series = pd.Series(index=df.index, dtype=float)
    z_series = pd.Series(index=df.index, dtype=float)

    position = 0
    position_list = []
    trades = 0

    alpha_curr, beta_curr = np.nan, np.nan
    valid_curr = np.nan

    for i in range(len(df)):
        idx = df.index[i]

        if i >= formation_window and (i - formation_window) % rebalance_every == 0:
            train = df.iloc[i - formation_window:i]
            alpha_curr, beta_curr = estimate_hedge_ratio(train["y"], train["x"], use_log=use_log)
            train_spread = compute_spread(train["y"], train["x"], alpha_curr, beta_curr, use_log=use_log)
            coint_res = run_coint(train["y"], train["x"])
            adf_res = run_adf(train_spread)
            valid_curr = float(
                np.isfinite(coint_res["pvalue"]) and coint_res["pvalue"] < coint_p_threshold
                and np.isfinite(adf_res["pvalue"]) and adf_res["pvalue"] < adf_p_threshold
            )

        alpha_series.loc[idx] = alpha_curr
        beta_series.loc[idx] = beta_curr
        valid_series.loc[idx] = valid_curr

        if i >= formation_window and np.isfinite(alpha_curr) and np.isfinite(beta_curr):
            spread_val = compute_spread(
                pd.Series([df["y"].iloc[i]]),
                pd.Series([df["x"].iloc[i]]),
                alpha_curr,
                beta_curr,
                use_log=use_log,
            ).iloc[0]
            spread_series.loc[idx] = spread_val

            hist = spread_series.iloc[max(0, i - z_window + 1):i + 1].dropna()
            if len(hist) >= max(20, z_window // 2):
                mu = hist.mean()
                sd = hist.std(ddof=0)
                zt = (spread_val - mu) / sd if sd and np.isfinite(sd) and sd > 0 else np.nan
            else:
                zt = np.nan
            z_series.loc[idx] = zt

            if valid_curr == 1 and np.isfinite(zt):
                if position == 0:
                    if zt > entry_z:
                        position = -1
                        trades += 1
                    elif zt < -entry_z:
                        position = 1
                        trades += 1
                elif position == 1:
                    if abs(zt) < exit_z or abs(zt) > stop_z or valid_curr != 1:
                        position = 0
                elif position == -1:
                    if abs(zt) < exit_z or abs(zt) > stop_z or valid_curr != 1:
                        position = 0
            else:
                if position != 0:
                    position = 0
        else:
            position = 0

        position_list.append(position)

    df["alpha"] = alpha_series
    df["beta"] = beta_series
    df["valid_pair"] = valid_series
    df["spread"] = spread_series
    df["z"] = z_series
    df["position"] = pd.Series(position_list, index=df.index)
    df["position_lag"] = df["position"].shift(1).fillna(0.0)

    abs_beta = df["beta"].abs().replace(0, np.nan)
    gross = 1.0 + abs_beta
    w_y = 1.0 / gross
    w_x = abs_beta / gross

    sign_beta = np.sign(df["beta"]).replace(0, 1).fillna(1.0)
    df["raw_ret"] = df["position_lag"] * (w_y * df["ret_y"] - sign_beta * w_x * df["ret_x"])
    turnover = df["position"].diff().abs().fillna(0.0)
    df["cost"] = (turnover > 0).astype(float) * (transaction_cost_bps / 10000.0)
    df["strategy_ret"] = df["raw_ret"].fillna(0.0) - df["cost"]
    df["equity_curve"] = (1.0 + df["strategy_ret"]).cumprod()

    ann = annualization_factor(interval)
    total_return = df["equity_curve"].iloc[-1] - 1.0
    ann_return = df["strategy_ret"].mean() * ann
    ann_vol = df["strategy_ret"].std() * np.sqrt(ann)
    sharpe = ann_return / ann_vol if np.isfinite(ann_vol) and ann_vol > 0 else np.nan
    max_dd = (df["equity_curve"] / df["equity_curve"].cummax() - 1.0).min()
    trade_returns = df.loc[df["strategy_ret"] != 0, "strategy_ret"]
    win_rate = safe_float((trade_returns > 0).mean(), np.nan)
    exposure = safe_float((df["position"] != 0).mean(), np.nan)

    meta = {
        "total_return": total_return,
        "annualized_return": ann_return,
        "annualized_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "trades": int(trades),
        "win_rate": win_rate,
        "exposure": exposure,
        "last_z": safe_float(df["z"].iloc[-1]),
        "last_valid_pair": safe_float(df["valid_pair"].iloc[-1]),
        "last_beta": safe_float(df["beta"].iloc[-1]),
    }
    return df, meta


def portfolio_backtest_from_top_pairs(
    prices: pd.DataFrame,
    scan_df: pd.DataFrame,
    top_n: int,
    formation_window: int,
    z_window: int,
    entry_z: float,
    exit_z: float,
    stop_z: float,
    coint_p_threshold: float,
    adf_p_threshold: float,
    transaction_cost_bps: float,
    rebalance_every: int,
    use_log: bool = True,
    interval: str = "1d",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if scan_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    members = []
    reports = []
    for _, row in scan_df.head(top_n).iterrows():
        try:
            bt, meta = walkforward_backtest(
                prices=prices,
                y_ticker=row["y"],
                x_ticker=row["x"],
                formation_window=formation_window,
                z_window=z_window,
                entry_z=entry_z,
                exit_z=exit_z,
                stop_z=stop_z,
                coint_p_threshold=coint_p_threshold,
                adf_p_threshold=adf_p_threshold,
                transaction_cost_bps=transaction_cost_bps,
                rebalance_every=rebalance_every,
                use_log=use_log,
                interval=interval,
            )
            members.append(bt["strategy_ret"].rename(f"{row['y']}/{row['x']}"))
            reports.append({"pair": f"{row['y']}/{row['x']}", "score": row["score"], **meta})
        except Exception:
            continue

    if not members:
        return pd.DataFrame(), pd.DataFrame()

    portfolio = pd.concat(members, axis=1).fillna(0.0)
    portfolio["portfolio_ret_equal_weight"] = portfolio.mean(axis=1)
    portfolio["portfolio_equity"] = (1.0 + portfolio["portfolio_ret_equal_weight"]).cumprod()
    return portfolio, pd.DataFrame(reports)


def sensitivity_grid(
    prices: pd.DataFrame,
    y_ticker: str,
    x_ticker: str,
    formation_window: int,
    z_window: int,
    entry_grid: List[float],
    exit_grid: List[float],
    stop_z: float,
    coint_p_threshold: float,
    adf_p_threshold: float,
    transaction_cost_bps: float,
    rebalance_every: int,
    use_log: bool = True,
    interval: str = "1d",
) -> pd.DataFrame:
    rows = []
    for entry_val, exit_val in product(entry_grid, exit_grid):
        if exit_val >= entry_val:
            continue
        try:
            _, meta = walkforward_backtest(
                prices=prices,
                y_ticker=y_ticker,
                x_ticker=x_ticker,
                formation_window=formation_window,
                z_window=z_window,
                entry_z=entry_val,
                exit_z=exit_val,
                stop_z=stop_z,
                coint_p_threshold=coint_p_threshold,
                adf_p_threshold=adf_p_threshold,
                transaction_cost_bps=transaction_cost_bps,
                rebalance_every=rebalance_every,
                use_log=use_log,
                interval=interval,
            )
            rows.append({"entry_z": entry_val, "exit_z": exit_val, **meta})
        except Exception:
            continue
    return pd.DataFrame(rows)


def latest_signal_text(last_z: float, valid_pair: float, entry_z: float, exit_z: float) -> str:
    if not np.isfinite(last_z):
        return "현재 Z-score 계산이 불안정합니다. 관찰 기간이 짧거나 분산이 거의 없습니다."
    if valid_pair != 1:
        return "현재 시점 기준으로 formation window 안에서 pair validity가 성립하지 않았습니다. 관망이 맞습니다."
    if last_z >= entry_z:
        return f"현재 Z-score가 +{entry_z:.1f} 이상입니다. 일반적 mean reversion 규칙에서는 short spread 후보입니다."
    if last_z <= -entry_z:
        return f"현재 Z-score가 -{entry_z:.1f} 이하입니다. 일반적 mean reversion 규칙에서는 long spread 후보입니다."
    if abs(last_z) <= exit_z:
        return f"현재 Z-score가 평균 부근({exit_z:.1f} 이내)입니다. 신규 진입보다 청산 또는 관망 구간으로 보는 편이 맞습니다."
    return "현재는 평균회귀 관찰 구간이지만, 진입 임계값에 도달하지는 않았습니다."


def draw_pair_monitor(bt: pd.DataFrame, y_label: str, x_label: str, entry_z: float, exit_z: float) -> go.Figure:
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.30, 0.22, 0.22, 0.26],
        subplot_titles=("정규화 가격", "워크포워드 스프레드", "Z-score", "누적 수익곡선"),
    )
    norm_y = bt["y"] / bt["y"].dropna().iloc[0]
    norm_x = bt["x"] / bt["x"].dropna().iloc[0]
    fig.add_trace(go.Scatter(x=bt.index, y=norm_y, name=y_label), row=1, col=1)
    fig.add_trace(go.Scatter(x=bt.index, y=norm_x, name=x_label), row=1, col=1)
    fig.add_trace(go.Scatter(x=bt.index, y=bt["spread"], name="Spread"), row=2, col=1)
    fig.add_trace(go.Scatter(x=bt.index, y=bt["z"], name="Z-score"), row=3, col=1)
    fig.add_hline(y=entry_z, line_dash="dash", row=3, col=1)
    fig.add_hline(y=-entry_z, line_dash="dash", row=3, col=1)
    fig.add_hline(y=exit_z, line_dash="dot", row=3, col=1)
    fig.add_hline(y=-exit_z, line_dash="dot", row=3, col=1)
    fig.add_hline(y=0.0, line_dash="dot", row=3, col=1)
    fig.add_trace(go.Scatter(x=bt.index, y=bt["equity_curve"], name="Equity"), row=4, col=1)
    fig.update_layout(height=980, legend_orientation="h")
    return fig


def draw_portfolio_chart(portfolio_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=portfolio_df.index, y=portfolio_df["portfolio_equity"], name="Equal-weight portfolio"))
    fig.update_layout(height=380, title="멀티페어 포트폴리오 누적 수익곡선")
    return fig


def draw_sensitivity_heatmap(df: pd.DataFrame, metric: str) -> go.Figure:
    pivot = df.pivot(index="exit_z", columns="entry_z", values=metric).sort_index()
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[str(c) for c in pivot.columns],
        y=[str(i) for i in pivot.index],
        hoverongaps=False,
        colorbar_title=metric,
    ))
    fig.update_layout(height=420, title=f"파라미터 민감도: {metric}")
    return fig


st.title("Pairs Trading Pro v3")
st.caption("공적분 기반 페어 탐색, 워크포워드 백테스트, 멀티페어 포트폴리오, 민감도 분석")

with st.sidebar:
    st.header("입력")
    tickers_text = st.text_input(
        "티커 입력 (2~5개)",
        value="KO,PEP,MDLZ,PG,CL",
        help="비슷한 산업이나 유사 사업 구조 종목군을 넣는 것이 맞습니다.",
    )
    tickers = [t.strip().upper() for t in tickers_text.split(",") if t.strip()]
    tickers = list(dict.fromkeys(tickers))[:5]

    period = st.selectbox("데이터 기간", ["1y", "2y", "3y", "5y"], index=2)
    interval = st.selectbox("데이터 주기", ["1d", "1h"], index=0)
    use_log = st.checkbox("로그 가격 기반", value=True)

    st.header("전략")
    formation_window = st.slider("Formation window", 60, 504, 252, 21)
    z_window = st.slider("Z-score window", 20, 180, 60, 5)
    entry_z = st.slider("진입 Z", 0.5, 4.0, 2.0, 0.1)
    exit_z = st.slider("청산 Z", 0.0, 2.0, 0.5, 0.1)
    stop_z = st.slider("손절 Z", 1.5, 6.0, 4.0, 0.1)
    coint_p_threshold = st.slider("공적분 p-value 기준", 0.01, 0.20, 0.05, 0.01)
    adf_p_threshold = st.slider("스프레드 ADF p-value 기준", 0.01, 0.20, 0.10, 0.01)
    rebalance_every = st.slider("재추정 주기", 1, 20, 5, 1)
    transaction_cost_bps = st.slider("거래비용 (bps)", 0.0, 30.0, 5.0, 1.0)

    st.header("포트폴리오")
    top_n_pairs = st.slider("상위 페어 수", 1, 6, 3, 1)

if len(tickers) < 2:
    st.warning("최소 2개 티커가 필요합니다.")
    st.stop()

prices = load_prices(tickers, period, interval)
if len(prices) < formation_window + z_window + 10:
    st.error("현재 데이터 길이로는 설정한 formation window / z-window를 돌리기 부족합니다. 기간을 늘리거나 창을 줄이세요.")
    st.stop()

scan_df = scan_all_pairs(prices, use_log=use_log)
if scan_df.empty:
    st.error("스캔 가능한 페어를 찾지 못했습니다.")
    st.stop()

tabs = st.tabs([
    "후보 스캔",
    "단일 페어 모니터링",
    "멀티페어 포트폴리오",
    "파라미터 민감도",
    "사용법",
    "해석 기준",
    "주의사항 / 한계",
])

with tabs[0]:
    st.subheader("후보 스캔 결과")
    st.markdown("""
이 표는 입력한 종목들에서 가능한 모든 2개 조합을 검사한 결과입니다.

**핵심**
- 높은 상관계수만으로는 부족합니다.
- 공적분과 스프레드 정상성이 같이 나와야 mean reversion 가정이 그나마 설득력을 가집니다.
- score는 보조 점수일 뿐이고, 최종 판단은 p-value, 반감기, 사업 구조를 함께 봐야 합니다.
""")
    st.dataframe(scan_df, use_container_width=True)
    st.subheader("최근 가격")
    st.dataframe(prices.tail(20), use_container_width=True)
    best = scan_df.iloc[0]
    st.info(
        f"현재 내부 점수 기준 상위 후보는 {best['y']} / {best['x']} 입니다. "
        "하지만 점수가 높아도 구조 변화가 있으면 실전 페어가 아닐 수 있습니다."
    )

with tabs[1]:
    st.subheader("단일 페어 워크포워드 모니터링")
    pair_labels = [f"{r['y']} / {r['x']}" for _, r in scan_df.iterrows()]
    chosen = st.selectbox("분석할 페어", pair_labels, index=0)
    row = scan_df.iloc[pair_labels.index(chosen)]
    y_ticker, x_ticker = row["y"], row["x"]

    bt_df, bt_meta = walkforward_backtest(
        prices=prices,
        y_ticker=y_ticker,
        x_ticker=x_ticker,
        formation_window=formation_window,
        z_window=z_window,
        entry_z=entry_z,
        exit_z=exit_z,
        stop_z=stop_z,
        coint_p_threshold=coint_p_threshold,
        adf_p_threshold=adf_p_threshold,
        transaction_cost_bps=transaction_cost_bps,
        rebalance_every=rebalance_every,
        use_log=use_log,
        interval=interval,
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("총수익", f"{bt_meta['total_return']:.2%}")
    c2.metric("연환산 수익", f"{bt_meta['annualized_return']:.2%}")
    c3.metric("Sharpe", "N/A" if np.isnan(bt_meta["sharpe"]) else f"{bt_meta['sharpe']:.2f}")
    c4.metric("최대낙폭", f"{bt_meta['max_drawdown']:.2%}")
    c5.metric("거래 횟수", f"{bt_meta['trades']}")
    c6.metric("노출 비중", f"{bt_meta['exposure']:.2%}" if np.isfinite(bt_meta["exposure"]) else "N/A")

    s1, s2, s3 = st.columns(3)
    s1.metric("현재 Z", "N/A" if np.isnan(bt_meta["last_z"]) else f"{bt_meta['last_z']:.2f}")
    s2.metric("현재 β", "N/A" if np.isnan(bt_meta["last_beta"]) else f"{bt_meta['last_beta']:.3f}")
    s3.metric("현재 pair validity", "YES" if bt_meta["last_valid_pair"] == 1 else "NO")

    st.plotly_chart(draw_pair_monitor(bt_df, y_ticker, x_ticker, entry_z, exit_z), use_container_width=True)

    st.markdown("### 현재 신호 해석")
    st.write(latest_signal_text(bt_meta["last_z"], bt_meta["last_valid_pair"], entry_z, exit_z))

    with st.expander("상세 데이터 보기"):
        st.dataframe(bt_df.tail(250), use_container_width=True)

    st.markdown("### 이 페어를 어떻게 봐야 하나")
    st.markdown(
        f"""
- 후보 적합성: coint p-value={row['coint_pvalue']:.4f}, ADF p-value={row['spread_adf_pvalue']:.4f}, KPSS p-value={row['spread_kpss_pvalue']:.4f}
- 반감기: {row['half_life']:.2f}
- Hurst: {row['hurst']:.3f}

해석은 단순합니다.
1. 공적분과 ADF가 나쁘면 mean reversion 전제가 약합니다.
2. 반감기가 지나치게 길면 신호가 느리고, 너무 짧으면 노이즈일 수 있습니다.
3. Hurst가 0.5보다 충분히 낮으면 평균회귀 성향의 보조 근거가 됩니다.
4. 마지막 필터는 결국 사업 구조입니다.
"""
    )

with tabs[2]:
    st.subheader("상위 페어 기반 멀티페어 포트폴리오")
    portfolio_df, pair_report_df = portfolio_backtest_from_top_pairs(
        prices=prices,
        scan_df=scan_df,
        top_n=top_n_pairs,
        formation_window=formation_window,
        z_window=z_window,
        entry_z=entry_z,
        exit_z=exit_z,
        stop_z=stop_z,
        coint_p_threshold=coint_p_threshold,
        adf_p_threshold=adf_p_threshold,
        transaction_cost_bps=transaction_cost_bps,
        rebalance_every=rebalance_every,
        use_log=use_log,
        interval=interval,
    )

    if portfolio_df.empty:
        st.warning("포트폴리오를 만들 수 있는 유효 페어가 부족합니다.")
    else:
        st.plotly_chart(draw_portfolio_chart(portfolio_df), use_container_width=True)
        st.dataframe(pair_report_df, use_container_width=True)

        ann = annualization_factor(interval)
        port_ret = portfolio_df["portfolio_ret_equal_weight"]
        port_total = portfolio_df["portfolio_equity"].iloc[-1] - 1.0
        port_ann = port_ret.mean() * ann
        port_vol = port_ret.std() * np.sqrt(ann)
        port_sharpe = port_ann / port_vol if np.isfinite(port_vol) and port_vol > 0 else np.nan
        port_mdd = (portfolio_df["portfolio_equity"] / portfolio_df["portfolio_equity"].cummax() - 1.0).min()

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("포트폴리오 총수익", f"{port_total:.2%}")
        p2.metric("포트폴리오 연환산", f"{port_ann:.2%}")
        p3.metric("포트폴리오 Sharpe", "N/A" if np.isnan(port_sharpe) else f"{port_sharpe:.2f}")
        p4.metric("포트폴리오 최대낙폭", f"{port_mdd:.2%}")

        st.markdown("""
왜 멀티페어를 보나
- 단일 페어 하나에 베팅하면 특정 기업 이벤트 하나로 전략이 망가질 수 있습니다.
- 상위 여러 페어를 동일가중으로 섞으면 일부 개별 리스크를 줄일 수 있습니다.
- 다만 같은 업종 리스크를 공유하면 분산 효과는 제한적입니다.
""")

with tabs[3]:
    st.subheader("파라미터 민감도 분석")
    pair_labels = [f"{r['y']} / {r['x']}" for _, r in scan_df.iterrows()]
    chosen2 = st.selectbox("민감도 분석 페어", pair_labels, index=0, key="sens_pair")
    row2 = scan_df.iloc[pair_labels.index(chosen2)]
    y2, x2 = row2["y"], row2["x"]

    sens_df = sensitivity_grid(
        prices=prices,
        y_ticker=y2,
        x_ticker=x2,
        formation_window=formation_window,
        z_window=z_window,
        entry_grid=[1.5, 2.0, 2.5, 3.0],
        exit_grid=[0.25, 0.5, 0.75, 1.0],
        stop_z=stop_z,
        coint_p_threshold=coint_p_threshold,
        adf_p_threshold=adf_p_threshold,
        transaction_cost_bps=transaction_cost_bps,
        rebalance_every=rebalance_every,
        use_log=use_log,
        interval=interval,
    )

    if sens_df.empty:
        st.warning("민감도 결과를 계산하지 못했습니다.")
    else:
        metric = st.selectbox("Heatmap 지표", ["sharpe", "total_return", "max_drawdown", "trades"], index=0)
        st.plotly_chart(draw_sensitivity_heatmap(sens_df, metric), use_container_width=True)
        st.dataframe(sens_df.sort_values(metric, ascending=False), use_container_width=True)
        st.markdown("""
해석 원칙
- 특정 한 점만 유난히 좋으면 과최적화 가능성이 큽니다.
- 근처 파라미터에서도 비슷한 성과가 나오는지 봐야 합니다.
- Sharpe가 높아도 거래 수가 지나치게 적으면 신뢰성이 약합니다.
""")

with tabs[4]:
    st.subheader("사용법")
    st.markdown("""
### 1) 종목 입력
- 같은 산업 또는 유사 사업 구조 종목을 2~5개 넣습니다.
- 예:
  - KO, PEP, MNST
  - XOM, CVX, COP
  - V, MA, AXP
  - JPM, BAC, WFC

### 2) 후보 스캔 확인
- 공적분 p-value, ADF p-value, KPSS p-value, 반감기를 먼저 확인합니다.

### 3) 단일 페어 모니터링
- 상위 페어를 선택하고 워크포워드 스프레드와 Z-score를 봅니다.

### 4) 포트폴리오 확인
- 상위 몇 개 페어를 동시에 운용했을 때 성과가 어떤지 확인합니다.

### 5) 민감도 확인
- 특정 파라미터에서만 성과가 좋다면 과최적화일 가능성이 큽니다.

### 6) 실제 활용
- 이 앱은 연구/검증용입니다.
- 실제 주문 전에는 공매도 가능 여부, 체결 가능성, 슬리피지, 수수료, 이벤트 리스크를 별도로 확인해야 합니다.
""")

with tabs[5]:
    st.subheader("해석 기준")
    st.markdown("""
### 공적분 p-value
- 낮을수록 두 시계열이 장기적으로 함께 묶여 있을 가능성을 시사합니다.

### ADF p-value
- 스프레드의 단위근 귀무가설을 검정합니다.
- 낮을수록 스프레드 정상성 가능성이 높습니다.

### KPSS p-value
- 정상성 귀무가설을 검정합니다.
- 높을수록 정상성 가정과 충돌이 덜합니다.
- ADF와 같이 봐야 합니다.

### 반감기
- 스프레드가 평균으로 되돌아오는 속도입니다.

### Hurst exponent
- 0.5보다 낮으면 평균회귀 성향의 보조 근거로 볼 수 있습니다.

### Z-score
- 현재 스프레드가 최근 평균에서 몇 표준편차 떨어졌는지 보여줍니다.
- 일반적으로:
  - |Z| < exit_z: 평균 부근
  - |Z| >= entry_z: 진입 후보
  - |Z| > stop_z: 비정상적 이탈 가능성
""")

with tabs[6]:
    st.subheader("주의사항 / 한계")
    st.markdown("""
### 이 앱이 해결하지 못하는 것
1. 구조 변화
   - 사업 구조가 변하면 과거 공적분 관계는 쉽게 깨집니다.

2. 실전 체결
   - yfinance는 브로커 체결용 실시간 데이터가 아닙니다.

3. 공매도 제약
   - 페어 트레이딩은 대체로 long/short 구조인데 실제 시장에서는 공매도 제약이 큽니다.

4. 슬리피지와 수수료
   - 현재는 단순 bps 비용만 넣었습니다.

5. 과최적화
   - entry/exit/window를 많이 만질수록 과거 데이터에 맞춘 전략이 됩니다.

### 실전 전 체크리스트
- 실제로 같은 경제적 드라이버를 공유하는가
- 최근 사업 구조 변화가 없는가
- 공매도와 대차가 가능한가
- 이벤트 일정이 가까운가
- 결과가 out-of-sample에서도 유지되는가

### 가장 흔한 오해
- 상관이 높으니 페어다 → 틀릴 가능성이 큽니다.
- 백테스트 수익이 났으니 실전 가능하다 → 전혀 충분하지 않습니다.
- Z-score가 2를 넘었으니 무조건 진입 → 구조 변화 구간이면 손실이 커질 수 있습니다.
""")

st.download_button(
    "현재 스캔 결과 CSV 다운로드",
    data=scan_df.to_csv(index=False).encode("utf-8-sig"),
    file_name="pair_scan_results.csv",
    mime="text/csv",
)

st.caption("본 앱은 연구/학습/검증 목적 예시입니다. 투자 조언이 아니며, 실거래 전 별도 검증이 필요합니다.")
