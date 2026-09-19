#!/usr/bin/env python3
"""
주식 기술적 분석 자동화 스크립트

사용법:
    python analyze.py RXRX
    python analyze.py RXRX --months 6 --out rxrx_analysis.html

주의: 이 스크립트가 계산하는 모든 지표(이동평균, RSI, MACD, 볼린저밴드,
지지/저항 등)는 과거 가격에서 파생된 "후행지표"입니다. 미래 가격을 예측하는
도구가 아니라 현재 상황을 정리하고 리스크를 관리하기 위한 참고 자료로만
사용하세요. 투자 판단과 책임은 전적으로 사용자 본인에게 있습니다.
"""

import argparse
import html
import json
import sys
import webbrowser
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    sys.exit("yfinance가 설치되어 있지 않습니다. `pip install yfinance` 후 다시 실행하세요.")

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:
    sys.exit("plotly가 설치되어 있지 않습니다. `pip install plotly` 후 다시 실행하세요.")


# ---------------------------------------------------------------------------
# 색상 팔레트 (한국식: 상승=빨강, 하락=파랑)
# ---------------------------------------------------------------------------

COLOR_UP = "#e5484d"       # 상승(양봉) - 빨강
COLOR_DOWN = "#2f6fed"     # 하락(음봉) - 파랑
COLOR_SUPPORT = "#16a34a"  # 지지선 - 초록
COLOR_RESISTANCE = "#e5484d"  # 저항선 - 빨강 계열(경고색)
COLOR_BG = "#ffffff"
COLOR_GRID = "rgba(0,0,0,0.06)"
FONT_FAMILY = "'Pretendard', 'Apple SD Gothic Neo', 'Segoe UI', -apple-system, sans-serif"


# ---------------------------------------------------------------------------
# 1. 데이터 수집
# ---------------------------------------------------------------------------

def fetch_ohlcv(ticker: str, months: int = 6) -> pd.DataFrame:
    """yfinance로 일봉 OHLCV 데이터를 받아 DataFrame으로 정리한다.

    이동평균 200일선 등을 계산하려면 요청 기간보다 더 긴 과거 데이터가
    필요하므로, 표시/분석 대상 기간(months)과 별개로 여유 버퍼를 두고
    다운로드한다.
    """
    # 200일 SMA 등을 안정적으로 계산하기 위해 최소 1년 이상의 버퍼를 확보
    buffer_days = max(months * 31 + 250, 400)
    period_str = f"{buffer_days}d"

    try:
        raw = yf.download(
            ticker,
            period=period_str,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
    except Exception as e:
        raise RuntimeError(f"'{ticker}' 데이터 다운로드 중 오류 발생: {e}")

    if raw is None or raw.empty:
        raise ValueError(f"'{ticker}'에 대한 데이터를 찾을 수 없습니다. 티커를 확인하세요.")

    # yfinance가 멀티 티커 형식(MultiIndex 컬럼)을 반환하는 경우 평탄화
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(subset=["Close"], inplace=True)
    df.index.name = "Date"

    if len(df) < 30:
        raise ValueError(f"'{ticker}'의 데이터가 너무 적습니다 ({len(df)}개 캔들). 상장 기간이 짧거나 티커가 잘못되었을 수 있습니다.")

    return df


def slice_recent(df: pd.DataFrame, months: int) -> pd.DataFrame:
    """표시/지지저항 탐색용으로 최근 N개월 구간만 잘라낸다."""
    cutoff = df.index.max() - pd.DateOffset(months=months)
    sliced = df[df.index >= cutoff]
    return sliced if len(sliced) >= 20 else df.tail(max(20, len(df)))


# ---------------------------------------------------------------------------
# 2. 보조지표 계산
# ---------------------------------------------------------------------------

def compute_sma(df: pd.DataFrame, windows=(20, 50, 200)) -> pd.DataFrame:
    for w in windows:
        col = f"SMA_{w}"
        if len(df) >= w:
            df[col] = df["Close"].rolling(window=w).mean()
        else:
            df[col] = np.nan  # 데이터 부족 시 계산 불가 -> NaN 유지 (예외 없이 안전 처리)
    return df


def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)  # 초기 구간 등 계산 불가 시 중립값(50)으로 안전 처리
    df[f"RSI_{period}"] = rsi
    return df


def compute_bollinger(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = df["Close"].rolling(window=window).mean()
    std = df["Close"].rolling(window=window).std()
    df["BB_MID"] = mid
    df["BB_UPPER"] = mid + num_std * std
    df["BB_LOWER"] = mid - num_std * std
    return df


def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    df["MACD"] = macd_line
    df["MACD_SIGNAL"] = signal_line
    df["MACD_HIST"] = macd_line - signal_line
    return df


def compute_volume_ma(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    df[f"VOL_SMA_{window}"] = df["Volume"].rolling(window=window).mean()
    return df


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = compute_sma(df)
    df = compute_rsi(df)
    df = compute_bollinger(df)
    df = compute_macd(df)
    df = compute_volume_ma(df)
    return df


# ---------------------------------------------------------------------------
# 3. 지지/저항 구간 판단
# ---------------------------------------------------------------------------

@dataclass
class SRLevel:
    price: float
    touches: int
    kind: str  # "support" | "resistance"


def find_swing_points(series: pd.Series, order: int = 3):
    """단순 로컬 극값(swing high/low) 탐지: order 만큼 좌우보다 크거나/작으면 극값."""
    highs, lows = [], []
    values = series.values
    n = len(values)
    for i in range(order, n - order):
        window = values[i - order: i + order + 1]
        center = values[i]
        if center == window.max() and np.argmax(window) == order:
            highs.append((series.index[i], center))
        if center == window.min() and np.argmin(window) == order:
            lows.append((series.index[i], center))
    return highs, lows


def cluster_levels(points, price_tolerance_pct: float = 0.02):
    """비슷한 가격대(±tolerance)의 swing point를 하나의 레벨로 묶어서
    터치 횟수를 센다. 단순 최고/최저가 아니라 '여러 번 반응한 가격대'를
    우선순위로 삼기 위함이다."""
    if not points:
        return []

    prices = sorted(p for _, p in points)
    clusters = []
    current = [prices[0]]

    for p in prices[1:]:
        ref = np.mean(current)
        if abs(p - ref) / ref <= price_tolerance_pct:
            current.append(p)
        else:
            clusters.append(current)
            current = [p]
    clusters.append(current)

    return [{"price": float(np.mean(c)), "touches": len(c)} for c in clusters]


def find_support_resistance(df: pd.DataFrame, current_price: float, order: int = 3,
                             price_tolerance_pct: float = 0.02, top_n: int = 5):
    """swing high/low를 클러스터링해 터치 횟수 기준으로 지지/저항 후보를 뽑는다."""
    highs, lows = find_swing_points(df["Close"], order=order)

    high_clusters = cluster_levels(highs, price_tolerance_pct)
    low_clusters = cluster_levels(lows, price_tolerance_pct)

    resistance = sorted(
        [c for c in high_clusters if c["price"] > current_price] or high_clusters,
        key=lambda c: (-c["touches"], abs(c["price"] - current_price)),
    )[:top_n]

    support = sorted(
        [c for c in low_clusters if c["price"] < current_price] or low_clusters,
        key=lambda c: (-c["touches"], abs(c["price"] - current_price)),
    )[:top_n]

    resistance = sorted(resistance, key=lambda c: c["price"])
    support = sorted(support, key=lambda c: c["price"], reverse=True)

    return support, resistance


def nearest_level(levels, current_price: float, kind: str):
    if not levels:
        return None
    closest = min(levels, key=lambda c: abs(c["price"] - current_price))
    diff_pct = (closest["price"] - current_price) / current_price * 100
    return {
        "price": closest["price"],
        "touches": closest["touches"],
        "diff_pct": diff_pct,
        "kind": kind,
    }


# ---------------------------------------------------------------------------
# 4. 추세 판단 로직
# ---------------------------------------------------------------------------

def interpret_rsi(rsi_value: float) -> str:
    if rsi_value >= 70:
        return "과매수"
    if rsi_value <= 30:
        return "과매도"
    return "중립"


def analyze_trend(df: pd.DataFrame) -> dict:
    """단기/중장기 추세와 근거를 함께 산출한다."""
    last = df.iloc[-1]
    close = last["Close"]

    sma20 = last.get("SMA_20", np.nan)
    sma50 = last.get("SMA_50", np.nan)
    sma200 = last.get("SMA_200", np.nan)
    rsi = last.get("RSI_14", np.nan)

    vol = last.get("Volume", np.nan)
    vol_sma20 = last.get("VOL_SMA_20", np.nan)

    short_reasons = []
    mid_reasons = []

    # --- 단기 추세: SMA20 vs SMA50, 가격 vs SMA20, RSI, 최근 거래량 ---
    short_score = 0

    if not np.isnan(sma20):
        if close > sma20:
            short_score += 1
            short_reasons.append(f"현재가(${close:.2f})가 20일선(${sma20:.2f}) 위에 위치")
        else:
            short_score -= 1
            short_reasons.append(f"현재가(${close:.2f})가 20일선(${sma20:.2f}) 아래에 위치")

    if not np.isnan(sma20) and not np.isnan(sma50):
        if sma20 > sma50:
            short_score += 1
            short_reasons.append(f"20일선(${sma20:.2f})이 50일선(${sma50:.2f}) 위에서 정배열 흐름")
        else:
            short_score -= 1
            short_reasons.append(f"20일선(${sma20:.2f})이 50일선(${sma50:.2f}) 아래로 역배열 흐름")

    if not np.isnan(rsi):
        rsi_state = interpret_rsi(rsi)
        if rsi_state == "과매수":
            short_reasons.append(f"RSI {rsi:.1f}로 과매수 구간 (단기 되돌림 가능성 유의)")
        elif rsi_state == "과매도":
            short_reasons.append(f"RSI {rsi:.1f}로 과매도 구간 (단기 반등 가능성 유의)")
            short_score -= 0  # 방향성 판단에는 중립적으로 두되 근거로만 명시
        else:
            if rsi >= 50:
                short_score += 0.5
            short_reasons.append(f"RSI {rsi:.1f}로 중립 구간")

    if not np.isnan(vol) and not np.isnan(vol_sma20) and vol_sma20 > 0:
        vol_ratio = vol / vol_sma20
        if vol_ratio >= 1.2:
            short_reasons.append(f"최근 거래량이 20일 평균 대비 {vol_ratio:.1f}배로 증가 (추세 강도 확인 필요)")
        elif vol_ratio <= 0.8:
            short_reasons.append(f"최근 거래량이 20일 평균 대비 {vol_ratio:.1f}배로 감소 (추세 동력 약화 가능성)")
        else:
            short_reasons.append(f"거래량은 20일 평균과 비슷한 수준 ({vol_ratio:.1f}배)")

    if short_score > 0.5:
        short_trend = "단기 상승 추세"
    elif short_score < -0.5:
        short_trend = "단기 하락 추세"
    else:
        short_trend = "단기 방향성 불분명 (횡보 또는 혼조)"

    # --- 중장기 추세: SMA50 vs SMA200, 가격 vs SMA200, 정배열/역배열 ---
    mid_score = 0
    sma200_available = not np.isnan(sma200)

    if not sma200_available:
        mid_reasons.append("200일선을 계산하기에 데이터가 부족하여(상장/조회 기간 짧음) 중장기 판단의 신뢰도가 낮습니다.")

    if not np.isnan(sma50) and sma200_available:
        if sma50 > sma200:
            mid_score += 1
            mid_reasons.append(f"50일선(${sma50:.2f})이 200일선(${sma200:.2f}) 위에 위치 (골든크로스 구도)")
        else:
            mid_score -= 1
            mid_reasons.append(f"50일선(${sma50:.2f})이 200일선(${sma200:.2f}) 아래에 위치 (데드크로스 구도)")

    if sma200_available:
        if close > sma200:
            mid_score += 1
            mid_reasons.append(f"현재가(${close:.2f})가 200일선(${sma200:.2f}) 위에 위치")
        else:
            mid_score -= 1
            mid_reasons.append(f"현재가(${close:.2f})가 200일선(${sma200:.2f}) 아래에 위치")

    if not np.isnan(sma20) and not np.isnan(sma50) and sma200_available:
        if sma20 > sma50 > sma200:
            mid_reasons.append("이동평균선이 20>50>200 완전 정배열 상태")
            mid_score += 1
        elif sma20 < sma50 < sma200:
            mid_reasons.append("이동평균선이 20<50<200 완전 역배열 상태")
            mid_score -= 1

    macd_hist = last.get("MACD_HIST", np.nan)
    if not np.isnan(macd_hist):
        if macd_hist > 0:
            mid_reasons.append(f"MACD 히스토그램이 양수({macd_hist:.3f})로 상승 모멘텀 우위")
        else:
            mid_reasons.append(f"MACD 히스토그램이 음수({macd_hist:.3f})로 하락 모멘텀 우위")

    if not sma200_available:
        mid_trend = "중장기 판단 보류 (데이터 부족)"
    elif mid_score > 0.5:
        mid_trend = "중장기 상승 추세"
    elif mid_score < -0.5:
        mid_trend = "중장기 하락 추세"
    else:
        mid_trend = "중장기 방향성 불분명 (횡보 또는 혼조)"

    return {
        "short_trend": short_trend,
        "short_reasons": short_reasons,
        "mid_trend": mid_trend,
        "mid_reasons": mid_reasons,
        "rsi": rsi,
        "rsi_state": interpret_rsi(rsi) if not np.isnan(rsi) else "N/A",
    }


# ---------------------------------------------------------------------------
# 5. 시각화
# ---------------------------------------------------------------------------

def build_chart(chart_df: pd.DataFrame, ticker: str, support, resistance,
                 display_start=None, display_end=None):
    """Plotly Figure 객체를 만들어 반환한다 (파일 저장은 render_html_page가 담당).

    chart_df: 기간 컨트롤(빠른 버튼/직접 날짜 입력)로 자유롭게 탐색할 수 있도록,
              표시 대상 기간보다 넉넉한(버퍼 포함) 데이터를 통째로 전달한다.
    display_start/display_end: 처음 열었을 때 보여줄 기본 확대 구간(지지/저항을
              계산한 실제 분석 구간)이며, 페이지의 기간 컨트롤로 언제든 다른
              기간으로 재조정할 수 있다.
    """
    fig = make_subplots(
        rows=3, cols=2,
        shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2],
        column_widths=[0.78, 0.22],
        vertical_spacing=0.04,
        horizontal_spacing=0.02,
        specs=[
            [{"type": "xy"}, {"type": "table", "rowspan": 3}],
            [{"type": "xy"}, None],
            [{"type": "xy"}, None],
        ],
        subplot_titles=(f"<b>{ticker}</b> 일봉", "지지/저항 레벨", "거래량", "RSI(14)"),
    )

    df = chart_df

    # 캔들스틱 (한국식: 상승=빨강, 하락=파랑)
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="가격",
        increasing=dict(line=dict(color=COLOR_UP, width=1), fillcolor=COLOR_UP),
        decreasing=dict(line=dict(color=COLOR_DOWN, width=1), fillcolor=COLOR_DOWN),
    ), row=1, col=1)

    # 이동평균선
    for col, color in [("SMA_20", "#f5a623"), ("SMA_50", "#7c3aed"), ("SMA_200", "#0f172a")]:
        if col in df.columns and df[col].notna().any():
            fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col,
                                      line=dict(width=1.3, color=color)), row=1, col=1)

    # 볼린저 밴드
    if "BB_UPPER" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_UPPER"], name="BB Upper",
                                  line=dict(width=1, color="rgba(120,120,120,0.6)", dash="dot"),
                                  hoverinfo="skip"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_LOWER"], name="BB Lower",
                                  line=dict(width=1, color="rgba(120,120,120,0.6)", dash="dot"),
                                  fill="tonexty", fillcolor="rgba(150,150,150,0.07)",
                                  hoverinfo="skip"), row=1, col=1)

    # --- 지지/저항: 차트 위에는 아주 옅은 안내선만 남기고, 상세 정보는 오른쪽
    # '지지/저항 레벨' 테이블(호가창 스타일)에서 확인한다 ---
    current_price = df["Close"].iloc[-1]

    for lvl in support:
        fig.add_shape(type="line", xref="x domain", x0=0, x1=1, yref="y",
                      y0=lvl["price"], y1=lvl["price"],
                      line=dict(color=COLOR_SUPPORT, width=1, dash="dot"),
                      opacity=0.35, layer="below", row=1, col=1)
    for lvl in resistance:
        fig.add_shape(type="line", xref="x domain", x0=0, x1=1, yref="y",
                      y0=lvl["price"], y1=lvl["price"],
                      line=dict(color=COLOR_RESISTANCE, width=1, dash="dot"),
                      opacity=0.35, layer="below", row=1, col=1)

    # 현재가 기준선 (얇게, 라벨 없이)
    fig.add_shape(type="line", xref="x domain", x0=0, x1=1, yref="y",
                  y0=current_price, y1=current_price,
                  line=dict(color="#334155", width=1, dash="dot"),
                  opacity=0.6, layer="below", row=1, col=1)

    # --- 지지/저항 레벨 테이블 (호가창 스타일: 저항 위 → 현재가 → 지지 아래) ---
    rows = []
    for lvl in reversed(resistance):  # 먼 저항이 위, 가까운 저항이 현재가 바로 위
        diff_pct = (lvl["price"] - current_price) / current_price * 100
        rows.append(("저항", lvl["price"], diff_pct, lvl["touches"], COLOR_RESISTANCE, "#fff5f5", "#3a1c1e"))
    rows.append(("현재가", current_price, 0.0, None, "#ffffff", "#334155", "#334155"))
    for lvl in support:  # 가까운 지지가 위, 먼 지지가 아래
        diff_pct = (lvl["price"] - current_price) / current_price * 100
        rows.append(("지지", lvl["price"], diff_pct, lvl["touches"], COLOR_SUPPORT, "#f0fdf4", "#12271c"))

    if not rows:
        rows.append(("현재가", current_price, 0.0, None, "#ffffff", "#334155", "#334155"))

    col_type, col_price, col_diff, col_touch = [], [], [], []
    col_bg_light, col_bg_dark = [], []
    font_type, font_other_light, font_other_dark = [], [], []
    for kind, price, diff_pct, touches, text_color, bg_light, bg_dark in rows:
        col_type.append(f"<b>{kind}</b>")
        col_price.append(f"${price:,.2f}")
        col_diff.append("현재가" if kind == "현재가" else f"{diff_pct:+.2f}%")
        col_touch.append("-" if touches is None else f"{touches}회")
        col_bg_light.append(bg_light)
        col_bg_dark.append(bg_dark)
        font_type.append(text_color)
        font_other_light.append("#ffffff" if kind == "현재가" else "#1e293b")
        font_other_dark.append("#ffffff" if kind == "현재가" else "#e2e8f0")

    fig.add_trace(go.Table(
        columnwidth=[30, 30, 24, 16],
        header=dict(
            values=["구분", "가격", "현재가 대비", "터치"],
            fill_color="#0f172a", font=dict(color="white", size=11, family=FONT_FAMILY),
            align="center", height=26,
        ),
        cells=dict(
            values=[col_type, col_price, col_diff, col_touch],
            fill_color=[col_bg_light, col_bg_light, col_bg_light, col_bg_light],
            font=dict(color=[font_type, font_other_light, font_other_light, font_other_light],
                      size=11, family=FONT_FAMILY),
            align="center", height=26,
        ),
    ), row=1, col=2)

    # 다크모드 토글에서 테이블 배경/글자색을 함께 바꾸기 위한 팔레트
    table_theme = {
        "light": {"bg": col_bg_light, "font0": font_type, "fontOther": font_other_light,
                  "header": "#0f172a"},
        "dark": {"bg": col_bg_dark, "font0": font_type, "fontOther": font_other_dark,
                 "header": "#0b1220"},
    }

    # 거래량 (한국식: 상승=빨강, 하락=파랑)
    vol_colors = np.where(df["Close"] >= df["Open"], COLOR_UP, COLOR_DOWN)
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="거래량",
                          marker_color=vol_colors, opacity=0.55), row=2, col=1)
    if "VOL_SMA_20" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["VOL_SMA_20"], name="거래량 SMA20",
                                  line=dict(width=1.2, color="#0f172a")), row=2, col=1)

    # RSI (+ 과매수/과매도 구간 음영)
    if "RSI_14" in df.columns:
        fig.add_hrect(y0=70, y1=100, fillcolor=COLOR_UP, opacity=0.06, line_width=0,
                      row=3, col=1, exclude_empty_subplots=False)
        fig.add_hrect(y0=0, y1=30, fillcolor=COLOR_DOWN, opacity=0.06, line_width=0,
                      row=3, col=1, exclude_empty_subplots=False)
        fig.add_trace(go.Scatter(x=df.index, y=df["RSI_14"], name="RSI(14)",
                                  line=dict(width=1.4, color="#0d9488")), row=3, col=1)
        fig.add_hline(y=70, line=dict(color=COLOR_UP, width=1, dash="dot"),
                      row=3, col=1, exclude_empty_subplots=False)
        fig.add_hline(y=30, line=dict(color=COLOR_DOWN, width=1, dash="dot"),
                      row=3, col=1, exclude_empty_subplots=False)

    # 기간 선택은 플롯 내장 위젯 대신, 페이지의 커스텀 버튼/날짜 입력(JS)에서
    # Plotly.relayout으로 처리한다 (render_html_page 참고).
    # 주말(비거래일) 구간을 건너뛰어 캔들 사이 빈틈 없애기
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])

    # 기본 확대 구간(분석 대상 기간)으로 초기 뷰 설정
    if display_start is not None and display_end is not None:
        fig.update_xaxes(range=[display_start, display_end], row=1, col=1)

    fig.update_layout(
        template="plotly_white",
        font=dict(family=FONT_FAMILY, size=12, color="#1e293b"),
        plot_bgcolor=COLOR_BG,
        paper_bgcolor=COLOR_BG,
        height=880,
        margin=dict(l=20, r=60, t=50, b=30),
        hovermode="x unified",
        hoverdistance=80,
        spikedistance=-1,
        dragmode="pan",
        hoverlabel=dict(bgcolor="#111827", bordercolor="#334155",
                         font=dict(color="#f8fafc", family=FONT_FAMILY)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    bgcolor="rgba(255,255,255,0)", groupclick="toggleitem"),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor="#d8dee9",
                      showspikes=True, spikemode="across", spikesnap="cursor",
                      spikecolor="#94a3b8", spikethickness=1, spikedash="dot")
    # 한국식 관행: 가격 축을 오른쪽에 배치
    fig.update_yaxes(showgrid=True, gridcolor=COLOR_GRID, side="right",
                      showspikes=True, spikecolor="#94a3b8", spikethickness=1,
                      spikedash="dot", separatethousands=True)
    fig.update_yaxes(title_text="가격", row=1, col=1)
    fig.update_yaxes(title_text="거래량", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])

    return fig, table_theme


def render_html_page(fig, table_theme: dict, ticker: str, chart_df: pd.DataFrame,
                      display_start, display_end, support, resistance, out_path: str) -> str:
    """Plotly Figure를 감싸서, 상단 요약 카드 + 커스텀 기간 컨트롤 + 다크모드
    토글이 있는 완성된 대시보드 HTML 페이지를 만든다."""
    current_price = float(chart_df["Close"].iloc[-1])
    prev_price = float(chart_df["Close"].iloc[-2]) if len(chart_df) >= 2 else current_price
    change_pct = (current_price / prev_price - 1) * 100 if prev_price else 0.0
    change_class = "up" if change_pct >= 0 else "down"

    nearest_support = f"${support[0]['price']:,.2f}" if support else "없음"
    nearest_resistance = f"${resistance[0]['price']:,.2f}" if resistance else "없음"

    first_date = chart_df.index.min().strftime("%Y-%m-%d")
    last_date = chart_df.index.max().strftime("%Y-%m-%d")
    initial_start = pd.Timestamp(display_start).strftime("%Y-%m-%d") if display_start is not None else first_date
    initial_end = pd.Timestamp(display_end).strftime("%Y-%m-%d") if display_end is not None else last_date

    chart_fragment = fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        div_id="chart",
        config={
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "toImageButtonOptions": {"format": "png", "filename": f"{ticker}_chart", "scale": 2},
        },
    )

    safe_ticker = html.escape(ticker)
    disclaimer = html.escape(
        "이 페이지의 모든 지표(이동평균, RSI, MACD, 볼린저밴드, 지지/저항 등)는 과거 가격에서 "
        "파생된 후행지표이며, 미래 가격을 예측하는 도구가 아닙니다. 리스크 관리 참고용으로만 사용하세요."
    )
    table_theme_json = json.dumps(table_theme, ensure_ascii=False)

    page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_ticker} 기술적 분석</title>
<style>
  :root {{
    color-scheme: light;
    --bg:#f4f6fa; --surface:#fff; --text:#172033; --muted:#687386; --line:#dfe5ee;
    --up:{COLOR_UP}; --down:{COLOR_DOWN}; --accent:#3859d6;
    --shadow:0 18px 45px rgba(30,46,80,.10);
  }}
  body.dark {{
    color-scheme: dark;
    --bg:#0d111a; --surface:#151b27; --text:#edf2f7; --muted:#9aa7ba; --line:#2a3445;
    --accent:#8ea2ff; --shadow:0 18px 48px rgba(0,0,0,.32);
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
          font-family:{FONT_FAMILY}; }}
  .shell {{ width:min(1500px,calc(100% - 28px)); margin:22px auto; }}
  header.topbar {{ margin-bottom:14px; }}
  h1 {{ margin:0 0 5px; font-size:clamp(22px,3vw,32px); font-weight:700; letter-spacing:-.02em; }}
  .subtitle {{ margin:0; color:var(--muted); font-size:14px; }}
  .panel {{ background:var(--surface); border:1px solid var(--line); border-radius:18px;
            box-shadow:var(--shadow); overflow:hidden; }}
  .stats {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1px;
            background:var(--line); border-bottom:1px solid var(--line); }}
  .stat {{ background:var(--surface); padding:14px 18px; }}
  .label {{ display:block; color:var(--muted); font-size:12px; margin-bottom:4px; }}
  .value {{ font-size:19px; font-weight:700; font-variant-numeric:tabular-nums; }}
  .up {{ color:var(--up); }}
  .down {{ color:var(--down); }}
  .controls {{ display:flex; flex-wrap:wrap; align-items:end; gap:10px 14px;
               padding:14px 18px; border-bottom:1px solid var(--line); }}
  .quick {{ display:flex; flex-wrap:wrap; gap:6px; }}
  button, input {{ min-height:38px; border:1px solid var(--line); background:var(--surface);
                    color:var(--text); border-radius:9px; font:inherit; }}
  button {{ padding:7px 12px; cursor:pointer; }}
  button:hover {{ border-color:var(--accent); }}
  button.active {{ color:#fff; background:var(--accent); border-color:var(--accent); }}
  .field {{ display:grid; gap:4px; }}
  .field label {{ color:var(--muted); font-size:11px; }}
  .field input {{ padding:6px 9px; }}
  #period-error {{ color:var(--up); font-size:12px; min-height:18px; align-self:center; }}
  .theme {{ margin-left:auto; }}
  #chart {{ width:100%; min-height:760px; }}
  .note {{ margin:12px 4px 0; color:var(--muted); font-size:12px; line-height:1.6; }}
  @media (max-width:720px) {{
    .shell {{ width:calc(100% - 12px); margin:8px auto; }}
    .stats {{ grid-template-columns:1fr; }}
    .controls {{ padding:12px; }}
    .theme {{ margin-left:0; }}
    #chart {{ min-height:680px; }}
  }}
</style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <h1>{safe_ticker} 기술적 분석</h1>
      <p class="subtitle">기준일 {last_date} · 붉은색 상승 / 파란색 하락 (한국식)</p>
    </header>
    <section class="panel" aria-label="기술적 분석 대시보드">
      <div class="stats">
        <div class="stat"><span class="label">현재가</span>
          <span class="value {change_class}">${current_price:,.2f} <small>{change_pct:+.2f}%</small></span></div>
        <div class="stat"><span class="label">가장 가까운 지지</span>
          <span class="value">{nearest_support}</span></div>
        <div class="stat"><span class="label">가장 가까운 저항</span>
          <span class="value">{nearest_resistance}</span></div>
      </div>
      <div class="controls" aria-label="조회 기간 설정">
        <div class="quick" aria-label="빠른 기간 선택">
          <button type="button" data-range="1mo">1개월</button>
          <button type="button" data-range="3mo">3개월</button>
          <button type="button" data-range="6mo">6개월</button>
          <button type="button" data-range="1y">1년</button>
          <button type="button" data-range="all">전체</button>
        </div>
        <div class="field"><label for="date-start">시작일</label>
          <input id="date-start" type="date" min="{first_date}" max="{last_date}"></div>
        <div class="field"><label for="date-end">종료일</label>
          <input id="date-end" type="date" min="{first_date}" max="{last_date}" value="{last_date}"></div>
        <button type="button" id="apply-period">기간 적용</button>
        <span id="period-error" role="alert"></span>
        <button type="button" id="theme-toggle" class="theme" aria-pressed="false">어두운 화면</button>
      </div>
      {chart_fragment}
    </section>
    <p class="note">지지/저항 표는 오른쪽 상단부터 저항 → 현재가 → 지지 순으로, 실제 가격 위치 감각대로
      배치했습니다(터치 횟수가 많을수록 신뢰도가 높은 가격대입니다). {disclaimer}</p>
  </main>
  <script>
    (() => {{
      const chart = document.getElementById('chart');
      const startInput = document.getElementById('date-start');
      const endInput = document.getElementById('date-end');
      const error = document.getElementById('period-error');
      const minDate = new Date('{first_date}T00:00:00');
      const maxDate = new Date('{last_date}T00:00:00');
      const tableTheme = {table_theme_json};
      const iso = d => d.toISOString().slice(0, 10);
      const clamp = d => new Date(Math.max(minDate.getTime(), Math.min(maxDate.getTime(), d.getTime())));

      function startFor(range) {{
        const d = new Date(maxDate);
        if (range === '1mo') d.setMonth(d.getMonth() - 1);
        else if (range === '3mo') d.setMonth(d.getMonth() - 3);
        else if (range === '6mo') d.setMonth(d.getMonth() - 6);
        else if (range === '1y') d.setFullYear(d.getFullYear() - 1);
        else return minDate;
        return clamp(d);
      }}
      function applyDates(start, end, activeRange = '') {{
        const from = clamp(start), to = clamp(end);
        if (from > to) {{ error.textContent = '시작일은 종료일보다 빨라야 합니다.'; return; }}
        error.textContent = '';
        startInput.value = iso(from);
        endInput.value = iso(to);
        document.querySelectorAll('[data-range]').forEach(btn =>
          btn.classList.toggle('active', btn.dataset.range === activeRange));
        Plotly.relayout(chart, {{'xaxis.range': [iso(from), iso(to)], 'xaxis.autorange': false}});
      }}
      document.querySelectorAll('[data-range]').forEach(btn =>
        btn.addEventListener('click', () => applyDates(startFor(btn.dataset.range), maxDate, btn.dataset.range)));
      document.getElementById('apply-period').addEventListener('click', () => {{
        if (!startInput.value || !endInput.value) {{
          error.textContent = '시작일과 종료일을 모두 선택하세요.';
          return;
        }}
        applyDates(new Date(startInput.value + 'T00:00:00'), new Date(endInput.value + 'T00:00:00'));
      }});

      function findTableTraceIndex() {{
        const data = chart.data || [];
        for (let i = 0; i < data.length; i++) {{
          if (data[i].type === 'table') return i;
        }}
        return -1;
      }}

      document.getElementById('theme-toggle').addEventListener('click', event => {{
        const dark = document.body.classList.toggle('dark');
        event.currentTarget.textContent = dark ? '밝은 화면' : '어두운 화면';
        event.currentTarget.setAttribute('aria-pressed', String(dark));

        const layoutColors = dark
          ? {{paper_bgcolor:'#151b27', plot_bgcolor:'#151b27', font:{{color:'#edf2f7'}},
              'xaxis.linecolor':'#2a3445', 'xaxis2.linecolor':'#2a3445', 'xaxis3.linecolor':'#2a3445'}}
          : {{paper_bgcolor:'#ffffff', plot_bgcolor:'#ffffff', font:{{color:'#1e293b'}},
              'xaxis.linecolor':'#d8dee9', 'xaxis2.linecolor':'#d8dee9', 'xaxis3.linecolor':'#d8dee9'}};
        const grid = dark ? '#273244' : 'rgba(0,0,0,0.06)';
        layoutColors['yaxis.gridcolor'] = grid;
        layoutColors['yaxis2.gridcolor'] = grid;
        layoutColors['yaxis3.gridcolor'] = grid;
        Plotly.relayout(chart, layoutColors);

        const idx = findTableTraceIndex();
        if (idx !== -1) {{
          const theme = dark ? tableTheme.dark : tableTheme.light;
          Plotly.restyle(chart, {{
            'cells.fill.color': [[theme.bg, theme.bg, theme.bg, theme.bg]],
            'cells.font.color': [[theme.font0, theme.fontOther, theme.fontOther, theme.fontOther]],
            'header.fill.color': [theme.header],
          }}, [idx]);
        }}
      }});

      window.addEventListener('load', () => applyDates(new Date('{initial_start}T00:00:00'), new Date('{initial_end}T00:00:00')));
    }})();
  </script>
</body>
</html>"""

    Path(out_path).write_text(page, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# 6. 콘솔 출력
# ---------------------------------------------------------------------------

def print_summary(ticker: str, df: pd.DataFrame, support, resistance, trend: dict, chart_path: str):
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    close = last["Close"]
    change_pct = (close - prev["Close"]) / prev["Close"] * 100

    print("=" * 60)
    print(f" {ticker} 기술적 분석 요약")
    print("=" * 60)
    print(f"현재가: ${close:.2f}   전일 대비: {change_pct:+.2f}%")
    print()

    nearest_sup = nearest_level(support, close, "support")
    nearest_res = nearest_level(resistance, close, "resistance")

    print("[지지/저항 레벨]")
    if support:
        for lvl in support:
            print(f"  지지선: ${lvl['price']:.2f}  (터치 {lvl['touches']}회)")
    else:
        print("  지지선 후보를 찾지 못했습니다 (데이터 부족).")

    if resistance:
        for lvl in resistance:
            print(f"  저항선: ${lvl['price']:.2f}  (터치 {lvl['touches']}회)")
    else:
        print("  저항선 후보를 찾지 못했습니다 (데이터 부족).")

    print()
    if nearest_sup:
        print(f"  → 가장 가까운 지지선: ${nearest_sup['price']:.2f} (현재가 대비 {nearest_sup['diff_pct']:+.2f}%, 터치 {nearest_sup['touches']}회)")
    if nearest_res:
        print(f"  → 가장 가까운 저항선: ${nearest_res['price']:.2f} (현재가 대비 {nearest_res['diff_pct']:+.2f}%, 터치 {nearest_res['touches']}회)")

    print()
    print("[RSI]")
    if not np.isnan(trend["rsi"]):
        print(f"  RSI(14): {trend['rsi']:.1f} → {trend['rsi_state']}")
    else:
        print("  RSI 계산 불가 (데이터 부족)")

    print()
    print("[단기 추세]")
    print(f"  판단: {trend['short_trend']}")
    print("  근거:")
    for r in trend["short_reasons"]:
        print(f"   - {r}")

    print()
    print("[중장기 추세]")
    print(f"  판단: {trend['mid_trend']}")
    print("  근거:")
    for r in trend["mid_reasons"]:
        print(f"   - {r}")

    print()
    print(f"차트 저장 위치: {chart_path}")
    print()
    print("⚠️  주의: 위 지표들은 모두 과거 가격 데이터에서 계산된 후행지표입니다.")
    print("    미래를 예측하는 도구가 아니라 리스크 관리·참고용으로만 활용하세요.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# 7. 실행 진입점
# ---------------------------------------------------------------------------

def run_analysis(ticker: str, months: int = 6, out_path: str = None,
                  swing_order: int = 3, sr_tolerance_pct: float = 0.02,
                  open_browser: bool = True):
    ticker = ticker.upper().strip()
    out_path = out_path or f"{ticker}_analysis.html"

    full_df = fetch_ohlcv(ticker, months=months)
    full_df = compute_all_indicators(full_df)

    display_df = slice_recent(full_df, months=months)
    current_price = display_df["Close"].iloc[-1]

    support, resistance = find_support_resistance(
        display_df, current_price, order=swing_order, price_tolerance_pct=sr_tolerance_pct
    )

    trend = analyze_trend(full_df)  # 200일선 등 정확도를 위해 전체(버퍼 포함) 데이터로 판단
    # 차트는 버퍼 포함 전체 데이터로 그려서, HTML을 연 뒤 기간 버튼/직접 날짜 입력으로
    # 더 과거 구간까지 자유롭게 조회할 수 있게 한다. 초기 확대 구간은 분석 대상 기간.
    display_start, display_end = display_df.index.min(), display_df.index.max()
    fig, table_theme = build_chart(
        full_df, ticker, support, resistance,
        display_start=display_start, display_end=display_end,
    )
    chart_path = render_html_page(
        fig, table_theme, ticker, full_df, display_start, display_end,
        support, resistance, out_path,
    )

    print_summary(ticker, display_df, support, resistance, trend, chart_path)

    if open_browser:
        webbrowser.open(Path(chart_path).resolve().as_uri())

    return {
        "df": display_df,
        "support": support,
        "resistance": resistance,
        "trend": trend,
        "chart_path": chart_path,
    }


def main():
    parser = argparse.ArgumentParser(description="주식 기술적 분석 자동화 스크립트 (참고용, 투자 예측 도구 아님)")
    parser.add_argument("ticker", nargs="?", default=None, help="분석할 티커 심볼 (예: RXRX, AAPL). 생략하면 직접 입력받는다.")
    parser.add_argument("--months", type=int, default=None, help="분석 대상 기간(개월), 기본 6개월")
    parser.add_argument("--out", type=str, default=None, help="출력 HTML 파일 경로")
    parser.add_argument("--swing-order", type=int, default=3, help="swing high/low 탐지 좌우 폭 (기본 3)")
    parser.add_argument("--sr-tolerance", type=float, default=0.02, help="지지/저항 클러스터링 가격 허용 오차 비율 (기본 0.02 = 2%%)")
    parser.add_argument("--no-open", action="store_true", help="분석 후 브라우저에서 자동으로 HTML을 열지 않음")
    args = parser.parse_args()

    # 티커를 인자로 안 주고 더블클릭 등으로 실행한 경우, 터미널에서 직접 입력받는다.
    ticker = args.ticker
    if not ticker:
        ticker = input("분석할 티커를 입력하세요 (예: AAPL, RXRX, 005930.KS): ").strip()
        if not ticker:
            print("티커가 입력되지 않았습니다. 종료합니다.", file=sys.stderr)
            sys.exit(1)

    months = args.months
    if months is None:
        months_input = input("조회 기간(개월, 기본 6): ").strip() if not args.ticker else "6"
        months = int(months_input) if months_input.isdigit() else 6

    try:
        run_analysis(
            ticker,
            months=months,
            out_path=args.out,
            swing_order=args.swing_order,
            sr_tolerance_pct=args.sr_tolerance,
            open_browser=not args.no_open,
        )
    except (ValueError, RuntimeError) as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"예상치 못한 오류가 발생했습니다: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.ticker:
        input("\n분석이 완료되었습니다. 엔터를 누르면 창을 닫습니다...")


if __name__ == "__main__":
    main()
