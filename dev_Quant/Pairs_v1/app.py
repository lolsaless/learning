
import math
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant
from statsmodels.tsa.stattools import adfuller, coint


st.set_page_config(page_title="Pairs Trading Lab", layout="wide")


# -----------------------------
# Utilities
# -----------------------------
@st.cache_data(ttl=300, show_spinner=False)
def load_price_data(tickers: List[str], period: str, interval: str) -> pd.DataFrame:
    df = yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    if df.empty:
        raise ValueError("가격 데이터를 불러오지 못했습니다.")
    if isinstance(df.columns, pd.MultiIndex):
        prices = df["Close"].copy()
    else:
        prices = df[["Close"]].copy()
        prices.columns = tickers[:1]
    prices = prices.dropna(how="all").ffill().dropna()
    return prices


def safe_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window).mean()
    std = series.rolling(window).std(ddof=0).replace(0, np.nan)
    return (series - mean) / std


def estimate_hedge_ratio(y: pd.Series, x: pd.Series, use_log: bool = True) -> float:
    y_, x_ = y.copy(), x.copy()
    if use_log:
        y_ = np.log(y_)
        x_ = np.log(x_)
    model = OLS(y_, add_constant(x_)).fit()
    return float(model.params.iloc[1])


def compute_spread(y: pd.Series, x: pd.Series, beta: float, use_log: bool = True) -> pd.Series:
    if use_log:
        return np.log(y) - beta * np.log(x)
    return y - beta * x


def adf_test(series: pd.Series) -> Dict[str, float]:
    series = series.dropna()
    stat, pvalue, usedlag, nobs, crit, _ = adfuller(series, autolag="AIC")
    return {
        "adf_stat": stat,
        "pvalue": pvalue,
        "used_lag": usedlag,
        "nobs": nobs,
        "crit_1%": crit["1%"],
        "crit_5%": crit["5%"],
        "crit_10%": crit["10%"],
    }


def engle_granger_test(y: pd.Series, x: pd.Series) -> Dict[str, float]:
    stat, pvalue, crit = coint(y, x, trend="c", autolag="aic")
    return {
        "coint_stat": stat,
        "pvalue": pvalue,
        "crit_1%": crit[0],
        "crit_5%": crit[1],
        "crit_10%": crit[2],
    }


def estimate_half_life(spread: pd.Series) -> float:
    s = spread.dropna()
    lagged = s.shift(1).dropna()
    delta = s.diff().dropna()
    aligned = pd.concat([lagged, delta], axis=1).dropna()
    aligned.columns = ["lagged", "delta"]
    if len(aligned) < 20:
        return np.nan
    model = OLS(aligned["delta"], add_constant(aligned["lagged"])).fit()
    phi = model.params["lagged"]
    if phi >= 0:
        return np.nan
    half_life = -np.log(2) / phi
    if np.isinf(half_life) or half_life <= 0:
        return np.nan
    return float(half_life)


def hurst_exponent(series: pd.Series, max_lag: int = 20) -> float:
    s = series.dropna().values
    if len(s) < max_lag + 5:
        return np.nan
    lags = range(2, max_lag)
    tau = [np.sqrt(np.std(np.subtract(s[lag:], s[:-lag]))) for lag in lags]
    poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
    return float(poly[0] * 2.0)


def pair_summary(prices: pd.DataFrame, t1: str, t2: str, use_log: bool = True) -> Dict:
    pair = prices[[t1, t2]].dropna()
    y, x = pair[t1], pair[t2]
    beta = estimate_hedge_ratio(y, x, use_log=use_log)
    spread = compute_spread(y, x, beta, use_log=use_log)
    coint_res = engle_granger_test(y, x)
    adf_res = adf_test(spread)
    hl = estimate_half_life(spread)
    hurst = hurst_exponent(spread)
    corr = y.pct_change().corr(x.pct_change())

    return {
        "y": t1,
        "x": t2,
        "corr_returns": corr,
        "hedge_ratio": beta,
        "coint_pvalue": coint_res["pvalue"],
        "coint_stat": coint_res["coint_stat"],
        "spread_adf_pvalue": adf_res["pvalue"],
        "spread_adf_stat": adf_res["adf_stat"],
        "half_life": hl,
        "hurst": hurst,
        "is_candidate": (coint_res["pvalue"] < 0.05) and (adf_res["pvalue"] < 0.05),
    }


def scan_pairs(prices: pd.DataFrame, use_log: bool = True) -> pd.DataFrame:
    rows = []
    for t1, t2 in combinations(prices.columns.tolist(), 2):
        try:
            rows.append(pair_summary(prices, t1, t2, use_log=use_log))
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values(
        ["is_candidate", "coint_pvalue", "spread_adf_pvalue", "half_life"],
        ascending=[False, True, True, True],
    )
    return df.reset_index(drop=True)


def backtest_pair(
    prices: pd.DataFrame,
    y_ticker: str,
    x_ticker: str,
    lookback: int = 60,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    stop_z: float = 4.0,
    transaction_cost_bps: float = 5.0,
    use_log: bool = True,
) -> Tuple[pd.DataFrame, Dict]:
    pair = prices[[y_ticker, x_ticker]].dropna().copy()
    y = pair[y_ticker]
    x = pair[x_ticker]

    beta = estimate_hedge_ratio(y, x, use_log=use_log)
    spread = compute_spread(y, x, beta, use_log=use_log)
    z = safe_zscore(spread, lookback)

    df = pd.DataFrame(index=pair.index)
    df["y"] = y
    df["x"] = x
    df["spread"] = spread
    df["z"] = z
    df["ret_y"] = y.pct_change().fillna(0.0)
    df["ret_x"] = x.pct_change().fillna(0.0)

    position = 0  # +1 long spread, -1 short spread
    positions = []
    trades = 0

    for i in range(len(df)):
        zi = df["z"].iloc[i]
        if np.isnan(zi):
            positions.append(0)
            continue

        if position == 0:
            if zi < -entry_z:
                position = 1
                trades += 1
            elif zi > entry_z:
                position = -1
                trades += 1
        elif position == 1:
            if abs(zi) < exit_z or abs(zi) > stop_z:
                position = 0
        elif position == -1:
            if abs(zi) < exit_z or abs(zi) > stop_z:
                position = 0

        positions.append(position)

    df["position"] = positions
    df["position_lag"] = df["position"].shift(1).fillna(0)

    # Dollar-neutral approximation:
    # Long spread = +1 in y and -beta in x
    gross = 1 + abs(beta)
    w_y = 1 / gross
    w_x = abs(beta) / gross

    df["strategy_ret"] = (
        df["position_lag"] * (w_y * df["ret_y"] - np.sign(beta) * w_x * df["ret_x"])
    )

    turnover = (df["position"].diff().abs().fillna(0) > 0).astype(float)
    cost = turnover * (transaction_cost_bps / 10000.0)
    df["strategy_ret_after_cost"] = df["strategy_ret"] - cost

    df["equity_curve"] = (1 + df["strategy_ret_after_cost"]).cumprod()

    total_return = df["equity_curve"].iloc[-1] - 1
    ann_factor = 252
    vol = df["strategy_ret_after_cost"].std() * np.sqrt(ann_factor)
    mean = df["strategy_ret_after_cost"].mean() * ann_factor
    sharpe = mean / vol if vol and not np.isnan(vol) else np.nan
    max_dd = (df["equity_curve"] / df["equity_curve"].cummax() - 1).min()

    stats = {
        "hedge_ratio": beta,
        "total_return": total_return,
        "annualized_return": mean,
        "annualized_vol": vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "trades": int(trades),
        "half_life": estimate_half_life(spread),
        "coint_pvalue": engle_granger_test(y, x)["pvalue"],
        "spread_adf_pvalue": adf_test(spread)["pvalue"],
    }
    return df, stats


def make_pair_chart(df: pd.DataFrame, title: str):
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.45, 0.25, 0.30],
        subplot_titles=("정규화 가격", "스프레드", "Z-score"),
    )
    norm_y = df["y"] / df["y"].iloc[0]
    norm_x = df["x"] / df["x"].iloc[0]
    fig.add_trace(go.Scatter(x=df.index, y=norm_y, name="Y"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=norm_x, name="X"), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["spread"], name="Spread"), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["z"], name="Z-score"), row=3, col=1)
    fig.add_hline(y=2.0, line_dash="dash", row=3, col=1)
    fig.add_hline(y=-2.0, line_dash="dash", row=3, col=1)
    fig.add_hline(y=0.0, line_dash="dot", row=3, col=1)

    fig.update_layout(title=title, height=850, legend_orientation="h")
    return fig


def make_equity_chart(df: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["equity_curve"], name="Equity Curve"))
    fig.update_layout(height=350, title="백테스트 누적 수익곡선")
    return fig


# -----------------------------
# Sidebar
# -----------------------------
st.title("Pairs Trading Lab")
st.caption("공적분 기반 페어 탐색, 실시간 모니터링, 통계 검정, 백테스트")

with st.sidebar:
    st.header("설정")
    default_tickers = "KO,PEP,PG,MDLZ"
    tickers_text = st.text_input(
        "티커 입력 (2~5개, 쉼표 구분)",
        value=default_tickers,
        help="예: KO, PEP 또는 XOM, CVX, COP",
    )
    tickers = [t.strip().upper() for t in tickers_text.split(",") if t.strip()]
    tickers = list(dict.fromkeys(tickers))[:5]

    period = st.selectbox("조회 기간", ["1y", "2y", "3y", "5y"], index=2)
    interval = st.selectbox("가격 주기", ["1d", "1h"], index=0)
    use_log = st.checkbox("로그 가격 사용", value=True)
    lookback = st.slider("Z-score rolling window", min_value=20, max_value=120, value=60, step=5)
    entry_z = st.slider("진입 Z", min_value=0.5, max_value=3.5, value=2.0, step=0.1)
    exit_z = st.slider("청산 Z", min_value=0.0, max_value=2.0, value=0.5, step=0.1)
    stop_z = st.slider("손절 Z", min_value=2.0, max_value=6.0, value=4.0, step=0.1)
    tc_bps = st.slider("거래비용 (bps)", min_value=0.0, max_value=30.0, value=5.0, step=1.0)

    scan_clicked = st.button("분석 실행", type="primary", use_container_width=True)

if len(tickers) < 2:
    st.warning("최소 2개 티커를 입력해야 합니다.")
    st.stop()

try:
    prices = load_price_data(tickers, period, interval)
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")
    st.stop()

st.subheader("가격 데이터")
st.dataframe(prices.tail(10), use_container_width=True)

scan_df = scan_pairs(prices, use_log=use_log)
if scan_df.empty:
    st.error("유효한 페어를 찾지 못했습니다.")
    st.stop()

st.subheader("페어 적합성 스캔")
st.markdown(
    """
**판단 기준 예시**
- `coint_pvalue < 0.05`: 두 가격 시계열이 장기 균형 관계일 가능성
- `spread_adf_pvalue < 0.05`: 스프레드가 정상성(stationary)을 가질 가능성
- `half_life`: 평균회귀 속도. 너무 짧거나 너무 길면 실전성이 떨어질 수 있음
- `hurst < 0.5`: 평균회귀 성향 시사
"""
)
st.dataframe(scan_df, use_container_width=True)

pair_options = [f"{row['y']} vs {row['x']}" for _, row in scan_df.iterrows()]
selected_pair_label = st.selectbox("분석할 페어 선택", pair_options, index=0)
selected_row = scan_df.iloc[pair_options.index(selected_pair_label)]
y_ticker = selected_row["y"]
x_ticker = selected_row["x"]

bt_df, bt_stats = backtest_pair(
    prices=prices,
    y_ticker=y_ticker,
    x_ticker=x_ticker,
    lookback=lookback,
    entry_z=entry_z,
    exit_z=exit_z,
    stop_z=stop_z,
    transaction_cost_bps=tc_bps,
    use_log=use_log,
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("공적분 p-value", f"{bt_stats['coint_pvalue']:.4f}")
c2.metric("스프레드 ADF p-value", f"{bt_stats['spread_adf_pvalue']:.4f}")
c3.metric("헤지비율 β", f"{bt_stats['hedge_ratio']:.4f}")
c4.metric("반감기", "N/A" if pd.isna(bt_stats["half_life"]) else f"{bt_stats['half_life']:.1f}")
c5.metric("거래 횟수", f"{bt_stats['trades']}")

fig_pair = make_pair_chart(bt_df, f"{y_ticker} / {x_ticker} 페어 모니터링")
st.plotly_chart(fig_pair, use_container_width=True)

st.subheader("백테스트 결과")
m1, m2, m3, m4 = st.columns(4)
m1.metric("총수익", f"{bt_stats['total_return']:.2%}")
m2.metric("연환산 수익", f"{bt_stats['annualized_return']:.2%}")
m3.metric("Sharpe", "N/A" if pd.isna(bt_stats["sharpe"]) else f"{bt_stats['sharpe']:.2f}")
m4.metric("최대낙폭", f"{bt_stats['max_drawdown']:.2%}")

st.plotly_chart(make_equity_chart(bt_df), use_container_width=True)

with st.expander("백테스트 상세 데이터"):
    st.dataframe(bt_df.tail(200), use_container_width=True)

with st.expander("해석 가이드"):
    st.markdown(
        """
1. **상관관계가 높다고 좋은 페어는 아닙니다.**
   단기 수익률 상관이 높아도 장기 균형 관계가 없으면 mean reversion 전략이 깨질 수 있습니다.

2. **공적분은 필요조건에 가깝고 충분조건은 아닙니다.**
   구조적 변화, 사업모델 변화, 이벤트 리스크가 생기면 과거의 관계는 쉽게 무너집니다.

3. **백테스트는 과최적화에 취약합니다.**
   lookback, entry/exit threshold를 여러 번 조정하면 성과가 좋아 보여도 실전에서는 재현되지 않을 수 있습니다.

4. **실전에는 체결비용/공매도 가능 여부/슬리피지/실시간 데이터 품질 검토가 필요합니다.**
        """
    )
