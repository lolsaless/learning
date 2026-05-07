
from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant
from statsmodels.tsa.stattools import adfuller, coint


st.set_page_config(page_title="Simple Pair Trading Monitor", layout="wide")


# -----------------------------
# Data
# -----------------------------
@st.cache_data(ttl=300, show_spinner=False)
def load_prices(ticker1: str, ticker2: str, period: str, interval: str) -> pd.DataFrame:
    data = yf.download(
        tickers=[ticker1, ticker2],
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
        close.columns = [ticker1]
    close = close.dropna(how="all").ffill().dropna()
    return close[[ticker1, ticker2]].dropna()


# -----------------------------
# Stats
# -----------------------------
def estimate_alpha_beta(y: pd.Series, x: pd.Series, use_log: bool = True) -> Tuple[float, float]:
    if use_log:
        y_ = np.log(y)
        x_ = np.log(x)
    else:
        y_, x_ = y.copy(), x.copy()
    model = OLS(y_, add_constant(x_)).fit()
    alpha = float(model.params.iloc[0])
    beta = float(model.params.iloc[1])
    return alpha, beta


def compute_spread(y: pd.Series, x: pd.Series, alpha: float, beta: float, use_log: bool = True) -> pd.Series:
    if use_log:
        return np.log(y) - (alpha + beta * np.log(x))
    return y - (alpha + beta * x)


def compute_pair_quality(y: pd.Series, x: pd.Series, spread: pd.Series) -> Dict[str, float]:
    ret_corr = y.pct_change().corr(x.pct_change())
    coint_stat, coint_pvalue, _ = coint(np.log(y), np.log(x), trend="c", autolag="aic")
    adf_stat, adf_pvalue, *_ = adfuller(spread.dropna(), autolag="AIC")
    ready = (coint_pvalue < 0.05) and (adf_pvalue < 0.05)
    return {
        "ret_corr": float(ret_corr),
        "coint_stat": float(coint_stat),
        "coint_pvalue": float(coint_pvalue),
        "adf_stat": float(adf_stat),
        "adf_pvalue": float(adf_pvalue),
        "ready": ready,
    }


def zscore(series: pd.Series, window: int) -> pd.Series:
    mu = series.rolling(window).mean()
    sd = series.rolling(window).std(ddof=0).replace(0, np.nan)
    return (series - mu) / sd


# -----------------------------
# Signal + Backtest
# -----------------------------
def generate_signals(
    prices: pd.DataFrame,
    ticker1: str,
    ticker2: str,
    z_window: int,
    entry_z: float,
    exit_z: float,
    use_log: bool = True,
):
    y = prices[ticker1]
    x = prices[ticker2]

    alpha, beta = estimate_alpha_beta(y, x, use_log=use_log)
    spread = compute_spread(y, x, alpha, beta, use_log=use_log)
    z = zscore(spread, z_window)

    df = prices.copy()
    df["spread"] = spread
    df["zscore"] = z
    df["signal"] = "HOLD"
    df["position"] = 0  # +1: long spread, -1: short spread
    df["entry_flag"] = ""
    df["exit_flag"] = ""

    position = 0
    for i in range(len(df)):
        zt = df["zscore"].iloc[i]
        if np.isnan(zt):
            df.iloc[i, df.columns.get_loc("position")] = position
            continue

        if position == 0:
            if zt >= entry_z:
                position = -1
                df.iloc[i, df.columns.get_loc("signal")] = "SELL_SPREAD"
                df.iloc[i, df.columns.get_loc("entry_flag")] = "ENTRY"
            elif zt <= -entry_z:
                position = 1
                df.iloc[i, df.columns.get_loc("signal")] = "BUY_SPREAD"
                df.iloc[i, df.columns.get_loc("entry_flag")] = "ENTRY"
        else:
            if abs(zt) <= exit_z:
                df.iloc[i, df.columns.get_loc("signal")] = "EXIT"
                df.iloc[i, df.columns.get_loc("exit_flag")] = "EXIT"
                position = 0

        df.iloc[i, df.columns.get_loc("position")] = position

    return df, alpha, beta


def backtest_signals(
    df: pd.DataFrame,
    ticker1: str,
    ticker2: str,
    beta: float,
    initial_capital: float,
    transaction_cost_bps: float,
):
    bt = df.copy()
    bt["ret_y"] = bt[ticker1].pct_change().fillna(0.0)
    bt["ret_x"] = bt[ticker2].pct_change().fillna(0.0)
    bt["position_lag"] = bt["position"].shift(1).fillna(0.0)

    gross = 1.0 + abs(beta)
    w_y = 1.0 / gross
    w_x = abs(beta) / gross
    sign_beta = 1.0 if beta >= 0 else -1.0

    bt["strategy_ret_before_cost"] = bt["position_lag"] * (w_y * bt["ret_y"] - sign_beta * w_x * bt["ret_x"])

    turnover = bt["position"].diff().abs().fillna(0.0)
    bt["cost"] = (turnover > 0).astype(float) * (transaction_cost_bps / 10000.0)
    bt["strategy_ret"] = bt["strategy_ret_before_cost"] - bt["cost"]

    bt["equity"] = initial_capital * (1.0 + bt["strategy_ret"]).cumprod()

    trade_rows = bt[(bt["signal"] != "HOLD")].copy()
    trade_rows = trade_rows[[ticker1, ticker2, "spread", "zscore", "signal", "equity"]]

    total_return = bt["equity"].iloc[-1] / initial_capital - 1.0
    max_drawdown = (bt["equity"] / bt["equity"].cummax() - 1.0).min()
    trade_count = int((bt["signal"].isin(["SELL_SPREAD", "BUY_SPREAD"])).sum())

    return bt, trade_rows, {
        "final_equity": float(bt["equity"].iloc[-1]),
        "total_return": float(total_return),
        "max_drawdown": float(max_drawdown),
        "trade_count": trade_count,
    }


# -----------------------------
# Chart
# -----------------------------
def make_chart(bt: pd.DataFrame, ticker1: str, ticker2: str, entry_z: float):
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.42, 0.28, 0.30],
        subplot_titles=("정규화 가격 흐름", "Spread Z-score", "전략 자산가치"),
    )

    norm1 = bt[ticker1] / bt[ticker1].iloc[0]
    norm2 = bt[ticker2] / bt[ticker2].iloc[0]

    fig.add_trace(go.Scatter(x=bt.index, y=norm1, name=ticker1), row=1, col=1)
    fig.add_trace(go.Scatter(x=bt.index, y=norm2, name=ticker2), row=1, col=1)

    entries = bt[bt["signal"].isin(["SELL_SPREAD", "BUY_SPREAD"])]
    exits = bt[bt["signal"] == "EXIT"]

    if not entries.empty:
        fig.add_trace(
            go.Scatter(
                x=entries.index,
                y=(entries[ticker1] / bt[ticker1].iloc[0]),
                mode="markers",
                name="진입 신호",
                marker=dict(size=9, symbol="triangle-up"),
            ),
            row=1,
            col=1,
        )

    if not exits.empty:
        fig.add_trace(
            go.Scatter(
                x=exits.index,
                y=(exits[ticker1] / bt[ticker1].iloc[0]),
                mode="markers",
                name="청산 신호",
                marker=dict(size=8, symbol="x"),
            ),
            row=1,
            col=1,
        )

    fig.add_trace(go.Scatter(x=bt.index, y=bt["zscore"], name="Z-score"), row=2, col=1)
    fig.add_hline(y=entry_z, line_dash="dash", row=2, col=1)
    fig.add_hline(y=-entry_z, line_dash="dash", row=2, col=1)
    fig.add_hline(y=0.0, line_dash="dot", row=2, col=1)

    fig.add_trace(go.Scatter(x=bt.index, y=bt["equity"], name="Equity"), row=3, col=1)

    fig.update_layout(height=900, legend_orientation="h")
    return fig


# -----------------------------
# UI
# -----------------------------
st.title("Simple Pair Trading Monitor")
st.caption("두 종목이 실제로 페어 후보인지 확인하고, 괴리 신호와 수익률만 간단히 봅니다.")

with st.sidebar:
    st.header("입력")
    ticker1 = st.text_input("종목 1", value="KO").strip().upper()
    ticker2 = st.text_input("종목 2", value="PEP").strip().upper()

    period = st.selectbox("기간", ["6mo", "1y", "2y", "3y", "5y"], index=2)
    interval = st.selectbox("주기", ["1d", "1h"], index=0)

    st.header("신호 기준")
    z_window = st.slider("Z-score window", 20, 120, 60, 5)
    entry_z = st.slider("진입 기준 Z", 0.5, 4.0, 2.0, 0.1)
    exit_z = st.slider("청산 기준 Z", 0.0, 2.0, 0.5, 0.1)

    st.header("투자 설정")
    initial_capital = st.number_input("초기 투자금", min_value=1000.0, value=1000000.0, step=1000.0)
    transaction_cost_bps = st.slider("거래비용 (bps)", 0.0, 30.0, 5.0, 1.0)

    use_log = st.checkbox("로그 가격 사용", value=True)

if ticker1 == ticker2:
    st.error("서로 다른 두 종목을 입력해야 합니다.")
    st.stop()

prices = load_prices(ticker1, ticker2, period, interval)

signal_df, alpha, beta = generate_signals(
    prices=prices,
    ticker1=ticker1,
    ticker2=ticker2,
    z_window=z_window,
    entry_z=entry_z,
    exit_z=exit_z,
    use_log=use_log,
)

quality = compute_pair_quality(prices[ticker1], prices[ticker2], signal_df["spread"])

bt, trades, summary = backtest_signals(
    df=signal_df,
    ticker1=ticker1,
    ticker2=ticker2,
    beta=beta,
    initial_capital=initial_capital,
    transaction_cost_bps=transaction_cost_bps,
)

st.subheader("1) 두 종목이 실제로 비슷한 흐름인지")
c1, c2, c3, c4 = st.columns(4)
c1.metric("수익률 상관계수", f"{quality['ret_corr']:.3f}")
c2.metric("공적분 p-value", f"{quality['coint_pvalue']:.4f}")
c3.metric("스프레드 ADF p-value", f"{quality['adf_pvalue']:.4f}")
c4.metric("페어 준비 상태", "READY" if quality["ready"] else "NOT READY")

if quality["ready"]:
    st.success(
        "이 두 종목은 현재 데이터 기준으로 페어 트레이딩을 검토할 최소 조건을 대체로 만족합니다. "
        "다만 이것이 미래에도 유지된다는 보장은 없습니다."
    )
else:
    st.warning(
        "이 두 종목은 현재 데이터 기준으로 신뢰할 만한 페어라고 보기 어렵습니다. "
        "상관이 높아 보여도 공적분/정상성이 약하면 평균회귀 전략은 쉽게 깨집니다."
    )

st.markdown(
    """
**해석**
- 수익률 상관계수: 단기적으로 얼마나 비슷하게 움직였는지
- 공적분 p-value: 장기적으로 같이 묶여 있는지
- 스프레드 ADF p-value: 가격 차이가 평균으로 되돌아오는 성격이 있는지

보통 `공적분 p-value < 0.05` 그리고 `ADF p-value < 0.05`이면 최소한의 준비가 되었다고 봅니다.
"""
)

st.subheader("2) 괴리 신호와 전략 성과")
m1, m2, m3 = st.columns(3)
m1.metric("최종 자산", f"{summary['final_equity']:,.0f}")
m2.metric("총수익률", f"{summary['total_return']:.2%}")
m3.metric("최대낙폭", f"{summary['max_drawdown']:.2%}")

m4, m5 = st.columns(2)
m4.metric("진입 횟수", f"{summary['trade_count']}")
m5.metric("현재 Z-score", f"{bt['zscore'].iloc[-1]:.2f}" if np.isfinite(bt["zscore"].iloc[-1]) else "N/A")

st.plotly_chart(make_chart(bt, ticker1, ticker2, entry_z), use_container_width=True)

st.markdown(
    """
**신호 규칙**
- `Z-score >= 진입 기준` → `SELL_SPREAD`
- `Z-score <= -진입 기준` → `BUY_SPREAD`
- `|Z-score| <= 청산 기준` → `EXIT`

여기서
- `BUY_SPREAD`는 상대적으로 과하게 벌어진 차이가 다시 줄어들 것이라고 보고 진입하는 것
- `SELL_SPREAD`는 반대로 반대 방향의 평균회귀를 기대하는 것

지금은 가장 단순한 규칙만 남겨 두었습니다.
"""
)

st.subheader("3) 신호 발생 데이터 표")
if trades.empty:
    st.info("신호가 아직 발생하지 않았습니다. 기간을 늘리거나 진입 기준을 낮춰 보세요.")
else:
    st.dataframe(trades, use_container_width=True)

st.subheader("4) 사용법 요약")
st.markdown(
    """
1. 두 종목을 입력합니다. 가능하면 같은 산업, 비슷한 사업 구조의 종목이 낫습니다.  
2. 먼저 `READY / NOT READY`를 봅니다. `NOT READY`면 페어 트레이딩 전제 자체가 약합니다.  
3. `READY`라면 그래프에서 Z-score가 크게 벌어질 때 신호가 찍히는지 봅니다.  
4. 아래 표에서 신호가 발생한 날짜와 당시 데이터, 그리고 전략 자산 변화를 확인합니다.  
5. 초기 투자금은 원하는 금액으로 바꿀 수 있습니다.  

이 앱은 일부러 단순화했습니다. 복잡한 최적화보다, 먼저 **두 종목이 페어가 될 자격이 있는지**와 **신호가 실제로 어떻게 나오는지**를 직관적으로 보는 용도입니다.
"""
)

st.caption("연구/학습용 예시입니다. 실거래 전에는 슬리피지, 공매도 가능 여부, 이벤트 리스크를 별도로 검토해야 합니다.")
