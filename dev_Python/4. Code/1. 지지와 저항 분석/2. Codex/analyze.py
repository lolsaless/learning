#!/usr/bin/env python3
"""Reusable technical analysis for a ticker downloaded from Yahoo Finance.

Technical indicators are lagging measurements.  The output is intended as a
risk-management reference, not as a prediction or investment recommendation.
"""

from __future__ import annotations

import argparse
import html
import math
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DISCLAIMER = (
    "주의: 기술적 지표는 후행지표이며, 미래 가격을 보장하는 예측 도구나 "
    "투자 권유가 아닙니다. 리스크 관리용 참고자료로만 사용하세요."
)

DEFAULT_CONFIG = Path(__file__).with_name("settings.txt")
CONFIG_KEYS = {
    "종목코드": "ticker",
    "데이터기간": "period",
    "처음표시기간": "initial_range",
    "저장파일": "output",
    "스윙기간": "swing_window",
    "구간허용오차": "level_tolerance",
    "최소터치횟수": "min_touches",
    "브라우저자동열기": "open_browser",
}
INITIAL_RANGES = ("1mo", "3mo", "6mo", "ytd", "1y", "3y", "all")


@dataclass(frozen=True)
class PriceLevel:
    """A support/resistance price zone derived from clustered swing points."""

    price: float
    touches: int
    last_touched: pd.Timestamp
    kind: str


def download_ohlcv(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """Download daily OHLCV data and normalize yfinance's output shape."""
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance가 없습니다. `pip install -r requirements.txt`를 실행하세요.") from exc

    try:
        data = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception as exc:
        raise RuntimeError(f"{ticker} 데이터 다운로드에 실패했습니다: {exc}") from exc

    if data is None or data.empty:
        raise ValueError(f"{ticker}의 가격 데이터가 없습니다. 티커와 기간을 확인하세요.")

    # Recent yfinance versions return a MultiIndex even for one ticker.
    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(-1):
            data = data.xs(ticker, axis=1, level=-1, drop_level=True)
        else:
            data.columns = data.columns.get_level_values(0)

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"필수 OHLCV 열이 없습니다: {', '.join(missing)}")

    result = data[required].copy()
    for column in required:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=["Open", "High", "Low", "Close"])
    result.index = pd.to_datetime(result.index).tz_localize(None)
    result.index.name = "Date"
    if len(result) < 2:
        raise ValueError("분석하려면 최소 2거래일의 데이터가 필요합니다.")
    return result.sort_index()


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Wilder's RSI using exponentially smoothed gains and losses."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    relative_strength = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + relative_strength))
    # A run with gains but no losses is RSI 100; the inverse is RSI 0.
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss > 0), 0.0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss == 0), 50.0)
    return rsi


def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """Add moving averages, RSI, Bollinger Bands, MACD and volume average."""
    frame = data.copy()
    close = frame["Close"]
    for window in (20, 50, 200):
        frame[f"SMA{window}"] = close.rolling(window, min_periods=window).mean()

    frame["RSI14"] = calculate_rsi(close, 14)
    frame["BB_Middle"] = close.rolling(20, min_periods=20).mean()
    rolling_std = close.rolling(20, min_periods=20).std(ddof=0)
    frame["BB_Upper"] = frame["BB_Middle"] + 2 * rolling_std
    frame["BB_Lower"] = frame["BB_Middle"] - 2 * rolling_std

    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    frame["MACD"] = ema12 - ema26
    frame["MACD_Signal"] = frame["MACD"].ewm(span=9, adjust=False, min_periods=9).mean()
    frame["MACD_Hist"] = frame["MACD"] - frame["MACD_Signal"]
    frame["Volume_MA20"] = frame["Volume"].rolling(20, min_periods=20).mean()
    return frame


def _swing_points(data: pd.DataFrame, swing_window: int = 3) -> list[tuple[float, pd.Timestamp, str]]:
    """Return centered local highs/lows without requiring scipy."""
    size = swing_window * 2 + 1
    rolling_high = data["High"].rolling(size, center=True).max()
    rolling_low = data["Low"].rolling(size, center=True).min()
    highs = data.loc[data["High"].eq(rolling_high), "High"]
    lows = data.loc[data["Low"].eq(rolling_low), "Low"]
    points = [(float(value), pd.Timestamp(date), "high") for date, value in highs.items()]
    points.extend((float(value), pd.Timestamp(date), "low") for date, value in lows.items())
    return sorted(points, key=lambda item: item[0])


def find_support_resistance(
    data: pd.DataFrame,
    swing_window: int = 3,
    tolerance_pct: float = 0.015,
    minimum_touches: int = 2,
) -> tuple[list[PriceLevel], list[PriceLevel]]:
    """Cluster swing prices into reaction zones and classify around current price.

    A cluster is formed when a pivot is within ``tolerance_pct`` of the running
    cluster center. Clusters with repeated touches are preferred. If none have
    enough touches, single-pivot levels are retained as a transparent fallback.
    """
    if swing_window < 1:
        raise ValueError("swing_window는 1 이상이어야 합니다.")
    if not 0 < tolerance_pct < 0.25:
        raise ValueError("tolerance_pct는 0과 0.25 사이여야 합니다.")

    points = _swing_points(data, swing_window)
    if not points:
        return [], []

    clusters: list[list[tuple[float, pd.Timestamp, str]]] = []
    for point in points:
        price = point[0]
        if not clusters:
            clusters.append([point])
            continue
        center = float(np.mean([existing[0] for existing in clusters[-1]]))
        if abs(price - center) / center <= tolerance_pct:
            clusters[-1].append(point)
        else:
            clusters.append([point])

    eligible = [cluster for cluster in clusters if len(cluster) >= minimum_touches]
    selected = eligible if eligible else clusters
    current = float(data["Close"].iloc[-1])
    supports: list[PriceLevel] = []
    resistances: list[PriceLevel] = []

    for cluster in selected:
        # Median is less sensitive than a mean to a wick at the edge of a zone.
        level_price = float(np.median([point[0] for point in cluster]))
        last_touched = max(point[1] for point in cluster)
        if level_price <= current:
            supports.append(PriceLevel(level_price, len(cluster), last_touched, "support"))
        else:
            resistances.append(PriceLevel(level_price, len(cluster), last_touched, "resistance"))

    # Nearest first; touches remain explicit so repeated reactions are visible.
    supports.sort(key=lambda level: current - level.price)
    resistances.sort(key=lambda level: level.price - current)
    return supports, resistances


def _value(frame: pd.DataFrame, column: str) -> float | None:
    value = frame[column].iloc[-1]
    return None if pd.isna(value) else float(value)


def _slope(frame: pd.DataFrame, column: str, sessions: int = 5) -> float | None:
    series = frame[column].dropna()
    if len(series) <= sessions or math.isclose(float(series.iloc[-sessions - 1]), 0.0):
        return None
    return float(series.iloc[-1] / series.iloc[-sessions - 1] - 1)


def evaluate_trends(data: pd.DataFrame) -> dict[str, object]:
    """Evaluate short and medium/long trends with human-readable evidence."""
    close = float(data["Close"].iloc[-1])
    sma20, sma50, sma200 = (_value(data, name) for name in ("SMA20", "SMA50", "SMA200"))
    rsi = _value(data, "RSI14")
    macd, signal = (_value(data, name) for name in ("MACD", "MACD_Signal"))
    volume = float(data["Volume"].iloc[-1])
    volume_ma = _value(data, "Volume_MA20")

    short_score = 0
    short_reasons: list[str] = []
    for name, average in (("20일선", sma20), ("50일선", sma50)):
        if average is None:
            short_reasons.append(f"{name} 계산 데이터 부족")
        elif close > average:
            short_score += 1
            short_reasons.append(f"현재가가 {name} 위")
        else:
            short_score -= 1
            short_reasons.append(f"현재가가 {name} 아래")

    sma20_slope = _slope(data, "SMA20")
    if sma20_slope is not None:
        if sma20_slope > 0:
            short_score += 1
            short_reasons.append(f"20일선 5거래일 기울기 상승({sma20_slope:+.1%})")
        elif sma20_slope < 0:
            short_score -= 1
            short_reasons.append(f"20일선 5거래일 기울기 하락({sma20_slope:+.1%})")

    if rsi is not None:
        if rsi >= 70:
            short_reasons.append(f"RSI {rsi:.1f}로 과매수권(상승 피로 가능)")
        elif rsi <= 30:
            short_reasons.append(f"RSI {rsi:.1f}로 과매도권(하락 과도 가능)")
        elif rsi >= 55:
            short_score += 1
            short_reasons.append(f"RSI {rsi:.1f}로 상승 모멘텀 우세")
        elif rsi <= 45:
            short_score -= 1
            short_reasons.append(f"RSI {rsi:.1f}로 하락 모멘텀 우세")
        else:
            short_reasons.append(f"RSI {rsi:.1f}로 중립")

    if macd is not None and signal is not None:
        if macd > signal:
            short_score += 1
            short_reasons.append("MACD가 시그널선 위")
        else:
            short_score -= 1
            short_reasons.append("MACD가 시그널선 아래")

    if volume_ma and volume_ma > 0:
        ratio = volume / volume_ma
        direction = "상승일" if data["Close"].iloc[-1] >= data["Close"].iloc[-2] else "하락일"
        if ratio >= 1.2:
            short_reasons.append(f"최근 거래량이 20일 평균의 {ratio:.2f}배인 {direction}(추세 신뢰도 강화 가능)")
        else:
            short_reasons.append(f"최근 거래량이 20일 평균의 {ratio:.2f}배(강한 거래량 확인 없음)")

    short_label = "상승" if short_score >= 2 else "하락" if short_score <= -2 else "중립/혼조"

    medium_score = 0
    medium_reasons: list[str] = []
    if sma20 is not None and sma50 is not None:
        if sma20 > sma50:
            medium_score += 1
            medium_reasons.append("20일선이 50일선 위")
        else:
            medium_score -= 1
            medium_reasons.append("20일선이 50일선 아래")
    else:
        medium_reasons.append("20일선/50일선 배열 판단 데이터 부족")

    if sma20 is not None and sma50 is not None and sma200 is not None:
        if sma20 > sma50 > sma200:
            medium_score += 2
            medium_reasons.append("20일 > 50일 > 200일 정배열")
        elif sma20 < sma50 < sma200:
            medium_score -= 2
            medium_reasons.append("20일 < 50일 < 200일 역배열")
        else:
            medium_reasons.append("이동평균선 혼조 배열")
    else:
        medium_reasons.append("200일선 데이터 부족으로 장기 배열 평가는 제한적")

    if sma200 is not None:
        if close > sma200:
            medium_score += 1
            medium_reasons.append("현재가가 200일선 위")
        else:
            medium_score -= 1
            medium_reasons.append("현재가가 200일선 아래")
        slope200 = _slope(data, "SMA200", 10)
        if slope200 is not None:
            if slope200 > 0:
                medium_score += 1
                medium_reasons.append(f"200일선 10거래일 기울기 상승({slope200:+.1%})")
            elif slope200 < 0:
                medium_score -= 1
                medium_reasons.append(f"200일선 10거래일 기울기 하락({slope200:+.1%})")

    medium_label = "상승" if medium_score >= 2 else "하락" if medium_score <= -2 else "중립/판단 제한"
    return {
        "short_label": short_label,
        "short_reasons": short_reasons,
        "medium_label": medium_label,
        "medium_reasons": medium_reasons,
    }


def rsi_interpretation(value: float | None) -> str:
    if value is None:
        return "계산 불가(데이터 부족)"
    if value >= 70:
        return "과매수"
    if value <= 30:
        return "과매도"
    return "중립"


def _format_levels(levels: Iterable[PriceLevel], limit: int = 3) -> str:
    chosen = list(levels)[:limit]
    if not chosen:
        return "후보 없음"
    return ", ".join(f"{level.price:,.2f} ({level.touches}회 터치)" for level in chosen)


def print_summary(
    ticker: str,
    data: pd.DataFrame,
    supports: list[PriceLevel],
    resistances: list[PriceLevel],
    trend: dict[str, object],
) -> None:
    current = float(data["Close"].iloc[-1])
    previous = float(data["Close"].iloc[-2])
    change = (current / previous - 1) * 100 if previous else float("nan")
    rsi = _value(data, "RSI14")

    print(f"\n{'=' * 64}")
    print(f"{ticker.upper()} 기술적 분석 | 기준일 {data.index[-1].date()}")
    print(f"{'=' * 64}")
    print(f"현재가: {current:,.2f} | 전일 대비: {change:+.2f}%")
    print(f"가까운 지지선: {_format_levels(supports)}")
    print(f"가까운 저항선: {_format_levels(resistances)}")
    print(f"RSI(14): {rsi:.2f} ({rsi_interpretation(rsi)})" if rsi is not None else "RSI(14): 계산 불가")
    print(f"\n단기 추세: {trend['short_label']}")
    for reason in trend["short_reasons"]:
        print(f"  - {reason}")
    print(f"\n중장기 추세: {trend['medium_label']}")
    for reason in trend["medium_reasons"]:
        print(f"  - {reason}")

    unavailable = [name for name in ("SMA20", "SMA50", "SMA200") if _value(data, name) is None]
    if unavailable:
        print(f"\n데이터 부족 지표: {', '.join(unavailable)} (더 긴 --period를 사용하세요.)")
    print(f"\n{DISCLAIMER}\n")


def create_chart(
    ticker: str,
    data: pd.DataFrame,
    supports: list[PriceLevel],
    resistances: list[PriceLevel],
    output_path: Path,
    initial_range: str = "6mo",
) -> None:
    """Create a self-contained, interactive Plotly analysis dashboard."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as exc:
        raise RuntimeError("plotly가 없습니다. `pip install -r requirements.txt`를 실행하세요.") from exc

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.62, 0.18, 0.20],
        subplot_titles=(f"{ticker.upper()} 일봉", "거래량", "RSI(14)"),
    )
    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="일봉",
            increasing=dict(line=dict(color="#e53935", width=1), fillcolor="#e53935"),
            decreasing=dict(line=dict(color="#1976d2", width=1), fillcolor="#1976d2"),
            whiskerwidth=0.45,
            hoverlabel=dict(namelength=0),
        ),
        row=1,
        col=1,
    )

    colors = {"SMA20": "#f59e0b", "SMA50": "#2563eb", "SMA200": "#7c3aed"}
    for column, color in colors.items():
        if data[column].notna().any():
            fig.add_trace(
                go.Scatter(x=data.index, y=data[column], name=column, line=dict(width=1.4, color=color)),
                row=1,
                col=1,
            )

    if data["BB_Upper"].notna().any():
        fig.add_trace(
            go.Scatter(x=data.index, y=data["BB_Upper"], name="BB 상단", line=dict(color="#94a3b8", width=1)),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data["BB_Lower"],
                name="BB 하단",
                line=dict(color="#94a3b8", width=1),
                fill="tonexty",
                fillcolor="rgba(148,163,184,0.10)",
            ),
            row=1,
            col=1,
        )

    # A zone is more realistic than a single exact price. Its width is based on
    # recent volatility, with conservative price-relative bounds.
    previous_close = data["Close"].shift(1)
    true_range = pd.concat(
        [
            data["High"] - data["Low"],
            (data["High"] - previous_close).abs(),
            (data["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    recent_atr = float(true_range.tail(20).median())
    pivots = _swing_points(data)

    def zone_half_width(level: PriceLevel) -> float:
        return min(max(level.price * 0.0035, recent_atr * 0.35), level.price * 0.012)

    for rank, level in enumerate(supports[:3], start=1):
        half_width = zone_half_width(level)
        strength = min(level.touches, 5)
        fig.add_hrect(
            y0=level.price - half_width,
            y1=level.price + half_width,
            fillcolor="#00a896",
            opacity=0.055 + strength * 0.018,
            line_width=0,
            row=1,
            col=1,
        )
        fig.add_hline(
            y=level.price,
            line_dash="dot",
            line_width=1.0 + strength * 0.25,
            line_color="#00897b",
            opacity=0.9,
            annotation_text=f"S{rank}  {level.price:,.2f} · {level.touches}회",
            annotation_position="bottom right",
            row=1,
            col=1,
        )
        touched = [point for point in pivots if abs(point[0] - level.price) <= half_width]
        if touched:
            fig.add_trace(
                go.Scatter(
                    x=[point[1] for point in touched],
                    y=[point[0] for point in touched],
                    mode="markers",
                    name=f"지지 S{rank} 터치",
                    marker=dict(symbol="triangle-up", size=8, color="#00897b"),
                    hovertemplate="지지 반응<br>%{x|%Y-%m-%d}<br>%{y:,.2f}<extra></extra>",
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

    for rank, level in enumerate(resistances[:3], start=1):
        half_width = zone_half_width(level)
        strength = min(level.touches, 5)
        fig.add_hrect(
            y0=level.price - half_width,
            y1=level.price + half_width,
            fillcolor="#ff9800",
            opacity=0.05 + strength * 0.018,
            line_width=0,
            row=1,
            col=1,
        )
        fig.add_hline(
            y=level.price,
            line_dash="dot",
            line_width=1.0 + strength * 0.25,
            line_color="#f57c00",
            opacity=0.9,
            annotation_text=f"R{rank}  {level.price:,.2f} · {level.touches}회",
            annotation_position="top right",
            row=1,
            col=1,
        )
        touched = [point for point in pivots if abs(point[0] - level.price) <= half_width]
        if touched:
            fig.add_trace(
                go.Scatter(
                    x=[point[1] for point in touched],
                    y=[point[0] for point in touched],
                    mode="markers",
                    name=f"저항 R{rank} 터치",
                    marker=dict(symbol="triangle-down", size=8, color="#f57c00"),
                    hovertemplate="저항 반응<br>%{x|%Y-%m-%d}<br>%{y:,.2f}<extra></extra>",
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

    current_price = float(data["Close"].iloc[-1])
    fig.add_hline(
        y=current_price,
        line_color="#64748b",
        line_width=1,
        opacity=0.75,
        annotation_text=f"현재가 {current_price:,.2f}",
        annotation_position="top left",
        row=1,
        col=1,
    )

    # Korean market convention: rising sessions are red, falling sessions blue.
    is_rising = data["Close"] >= data["Open"]
    volume_colors = np.where(is_rising, "rgba(229,57,53,0.72)", "rgba(25,118,210,0.72)")
    fig.add_trace(
        go.Bar(
            x=data.index,
            y=data["Volume"],
            name="거래량",
            marker_color=volume_colors,
            hovertemplate="%{x|%Y-%m-%d}<br>거래량 %{y:,.0f}<extra></extra>",
        ),
        row=2,
        col=1,
    )
    if data["Volume_MA20"].notna().any():
        fig.add_trace(
            go.Scatter(x=data.index, y=data["Volume_MA20"], name="거래량 MA20", line=dict(color="#f59e0b")),
            row=2,
            col=1,
        )

    fig.add_trace(
        go.Scatter(x=data.index, y=data["RSI14"], name="RSI(14)", line=dict(color="#7c3aed")),
        row=3,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="#dc2626", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#16a34a", row=3, col=1)
    fig.update_yaxes(range=[0, 100], row=3, col=1)
    fig.update_layout(
        template="plotly_white",
        height=900,
        hovermode="x unified",
        hoverdistance=80,
        spikedistance=-1,
        dragmode="pan",
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.015,
            xanchor="left",
            x=0,
            groupclick="toggleitem",
        ),
        margin=dict(l=62, r=80, t=62, b=45),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Pretendard, Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", color="#172033"),
        hoverlabel=dict(bgcolor="#111827", bordercolor="#334155", font=dict(color="#f8fafc")),
    )
    fig.update_xaxes(
        showgrid=False,
        rangebreaks=[dict(bounds=["sat", "mon"])],
        showspikes=True,
        spikecolor="#94a3b8",
        spikethickness=1,
        spikedash="dot",
        spikesnap="cursor",
        showline=True,
        linecolor="#d8dee9",
    )
    fig.update_yaxes(
        side="right",
        showgrid=True,
        gridcolor="#e8edf4",
        zeroline=False,
        showspikes=True,
        spikecolor="#94a3b8",
        spikethickness=1,
        spikedash="dot",
        separatethousands=True,
    )

    first_date = data.index[0].strftime("%Y-%m-%d")
    last_date = data.index[-1].strftime("%Y-%m-%d")
    previous_price = float(data["Close"].iloc[-2])
    price_change = (current_price / previous_price - 1) * 100 if previous_price else 0.0
    change_class = "up" if price_change >= 0 else "down"
    nearest_support = f"{supports[0].price:,.2f}" if supports else "없음"
    nearest_resistance = f"{resistances[0].price:,.2f}" if resistances else "없음"

    chart_fragment = fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        div_id="technical-chart",
        config={
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "toImageButtonOptions": {"format": "png", "filename": f"{ticker.upper()}_chart", "scale": 2},
        },
    )
    safe_ticker = html.escape(ticker.upper())
    safe_disclaimer = html.escape(DISCLAIMER)
    page = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_ticker} 기술적 분석</title>
  <style>
    :root {{ color-scheme: light; --bg:#f4f6fa; --surface:#fff; --text:#172033; --muted:#687386; --line:#dfe5ee; --up:#e53935; --down:#1976d2; --accent:#3859d6; --shadow:0 18px 45px rgba(30,46,80,.10); }}
    body.dark {{ color-scheme:dark; --bg:#0d111a; --surface:#151b27; --text:#edf2f7; --muted:#9aa7ba; --line:#2a3445; --accent:#8ea2ff; --shadow:0 18px 48px rgba(0,0,0,.32); }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font-family:Pretendard,Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    .shell {{ width:min(1500px,calc(100% - 28px)); margin:22px auto; }}
    .topbar {{ display:flex; justify-content:space-between; align-items:flex-start; gap:18px; margin-bottom:14px; }}
    h1 {{ margin:0 0 5px; font-size:clamp(22px,3vw,32px); font-weight:700; letter-spacing:-.02em; }}
    .subtitle {{ margin:0; color:var(--muted); font-size:14px; }}
    .panel {{ background:var(--surface); border:1px solid var(--line); border-radius:18px; box-shadow:var(--shadow); overflow:hidden; }}
    .stats {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1px; background:var(--line); border-bottom:1px solid var(--line); }}
    .stat {{ background:var(--surface); padding:14px 18px; }}
    .label {{ display:block; color:var(--muted); font-size:12px; margin-bottom:4px; }}
    .value {{ font-size:19px; font-weight:700; font-variant-numeric:tabular-nums; }}
    .up {{ color:var(--up); }} .down {{ color:var(--down); }}
    .controls {{ display:flex; flex-wrap:wrap; align-items:end; gap:10px 14px; padding:14px 18px; border-bottom:1px solid var(--line); }}
    .quick {{ display:flex; flex-wrap:wrap; gap:6px; }}
    button,input {{ min-height:38px; border:1px solid var(--line); background:var(--surface); color:var(--text); border-radius:9px; font:inherit; }}
    button {{ padding:7px 12px; cursor:pointer; }} button:hover {{ border-color:var(--accent); }}
    button.active {{ color:#fff; background:var(--accent); border-color:var(--accent); }}
    .field {{ display:grid; gap:4px; }} .field label {{ color:var(--muted); font-size:11px; }} .field input {{ padding:6px 9px; }}
    #period-error {{ color:var(--up); font-size:12px; min-height:18px; align-self:center; }}
    .theme {{ margin-left:auto; }}
    #technical-chart {{ width:100%; min-height:760px; }}
    .note {{ margin:12px 4px 0; color:var(--muted); font-size:12px; line-height:1.6; }}
    @media (max-width:720px) {{ .shell {{ width:min(100% - 12px,1500px); margin:8px auto; }} .topbar {{ padding:8px; }} .stats {{ grid-template-columns:1fr; }} .controls {{ padding:12px; }} .theme {{ margin-left:0; }} #technical-chart {{ min-height:680px; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div><h1>{safe_ticker} 기술적 분석</h1><p class="subtitle">기준일 {last_date} · 붉은색 상승 / 파란색 하락</p></div>
    </header>
    <section class="panel" aria-label="기술적 분석 대시보드">
      <div class="stats">
        <div class="stat"><span class="label">현재가</span><span class="value {change_class}">{current_price:,.2f} <small>{price_change:+.2f}%</small></span></div>
        <div class="stat"><span class="label">가까운 지지 구간 중심</span><span class="value">{nearest_support}</span></div>
        <div class="stat"><span class="label">가까운 저항 구간 중심</span><span class="value">{nearest_resistance}</span></div>
      </div>
      <div class="controls" aria-label="조회 기간 설정">
        <div class="quick" aria-label="빠른 기간 선택">
          <button type="button" data-range="1mo">1개월</button><button type="button" data-range="3mo">3개월</button><button type="button" data-range="6mo">6개월</button><button type="button" data-range="ytd">올해</button><button type="button" data-range="1y">1년</button><button type="button" data-range="3y">3년</button><button type="button" data-range="all">전체</button>
        </div>
        <div class="field"><label for="date-start">시작일</label><input id="date-start" type="date" min="{first_date}" max="{last_date}"></div>
        <div class="field"><label for="date-end">종료일</label><input id="date-end" type="date" min="{first_date}" max="{last_date}" value="{last_date}"></div>
        <button type="button" id="apply-period">기간 적용</button>
        <span id="period-error" role="alert"></span>
        <button type="button" id="theme-toggle" class="theme" aria-pressed="false">어두운 화면</button>
      </div>
      {chart_fragment}
    </section>
    <p class="note">S는 지지, R은 저항입니다. 색 띠는 변동성을 반영한 가격 구간이며, 삼각형은 실제 반응 지점, 선의 굵기는 반복 터치 강도를 나타냅니다. {safe_disclaimer}</p>
  </main>
  <script>
    (() => {{
      const chart = document.getElementById('technical-chart');
      const startInput = document.getElementById('date-start');
      const endInput = document.getElementById('date-end');
      const error = document.getElementById('period-error');
      const minDate = new Date('{first_date}T00:00:00');
      const maxDate = new Date('{last_date}T00:00:00');
      const initialRange = '{initial_range}';
      const iso = d => d.toISOString().slice(0, 10);
      const clamp = d => new Date(Math.max(minDate.getTime(), Math.min(maxDate.getTime(), d.getTime())));

      function startFor(range) {{
        const d = new Date(maxDate);
        if (range === '1mo') d.setMonth(d.getMonth() - 1);
        else if (range === '3mo') d.setMonth(d.getMonth() - 3);
        else if (range === '6mo') d.setMonth(d.getMonth() - 6);
        else if (range === '1y') d.setFullYear(d.getFullYear() - 1);
        else if (range === '3y') d.setFullYear(d.getFullYear() - 3);
        else if (range === 'ytd') return clamp(new Date(maxDate.getFullYear(), 0, 1));
        else return minDate;
        return clamp(d);
      }}
      function applyDates(start, end, activeRange='') {{
        const from = clamp(start), to = clamp(end);
        if (from > to) {{ error.textContent = '시작일은 종료일보다 빨라야 합니다.'; return; }}
        error.textContent = '';
        startInput.value = iso(from); endInput.value = iso(to);
        document.querySelectorAll('[data-range]').forEach(btn => btn.classList.toggle('active', btn.dataset.range === activeRange));
        Plotly.relayout(chart, {{'xaxis.range':[iso(from), iso(to)], 'xaxis.autorange':false}});
      }}
      document.querySelectorAll('[data-range]').forEach(btn => btn.addEventListener('click', () => applyDates(startFor(btn.dataset.range), maxDate, btn.dataset.range)));
      document.getElementById('apply-period').addEventListener('click', () => {{
        if (!startInput.value || !endInput.value) {{ error.textContent = '시작일과 종료일을 모두 선택하세요.'; return; }}
        applyDates(new Date(startInput.value + 'T00:00:00'), new Date(endInput.value + 'T00:00:00'));
      }});
      document.getElementById('theme-toggle').addEventListener('click', event => {{
        const dark = document.body.classList.toggle('dark');
        event.currentTarget.textContent = dark ? '밝은 화면' : '어두운 화면';
        event.currentTarget.setAttribute('aria-pressed', String(dark));
        const colors = dark
          ? {{paper_bgcolor:'#151b27', plot_bgcolor:'#151b27', font:{{color:'#edf2f7'}}, 'xaxis.linecolor':'#2a3445', 'xaxis2.linecolor':'#2a3445', 'xaxis3.linecolor':'#2a3445'}}
          : {{paper_bgcolor:'#ffffff', plot_bgcolor:'#ffffff', font:{{color:'#172033'}}, 'xaxis.linecolor':'#d8dee9', 'xaxis2.linecolor':'#d8dee9', 'xaxis3.linecolor':'#d8dee9'}};
        const grid = dark ? '#273244' : '#e8edf4';
        colors['yaxis.gridcolor']=grid; colors['yaxis2.gridcolor']=grid; colors['yaxis3.gridcolor']=grid;
        Plotly.relayout(chart, colors);
      }});
      window.addEventListener('load', () => applyDates(startFor(initialRange), maxDate, initialRange));
    }})();
  </script>
</body>
</html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")


def load_settings(path: Path) -> dict[str, str]:
    """Read simple ``key = value`` settings written for non-technical users."""
    if not path.exists():
        return {}

    settings: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path.name} {line_number}번째 줄에 '='가 없습니다: {raw_line}")
        raw_key, value = (part.strip() for part in line.split("=", 1))
        key = CONFIG_KEYS.get(raw_key)
        if key is None:
            valid = ", ".join(CONFIG_KEYS)
            raise ValueError(f"{path.name} {line_number}번째 줄의 설정 이름이 잘못되었습니다: {raw_key}\n사용 가능: {valid}")
        if not value:
            raise ValueError(f"{path.name} {line_number}번째 줄의 값이 비어 있습니다: {raw_key}")
        settings[key] = value
    return settings


def _setting_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"예", "네", "yes", "true", "1", "on"}:
        return True
    if normalized in {"아니오", "아니요", "no", "false", "0", "off"}:
        return False
    raise ValueError(f"{name} 값은 '예' 또는 '아니오'로 입력하세요.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yahoo Finance 일봉 기반 기술적 분석")
    parser.add_argument("ticker", nargs="?", help="Yahoo Finance 티커 (생략하면 settings.txt 사용)")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="설정 파일 경로 (기본: 프로그램과 같은 폴더의 settings.txt)",
    )
    parser.add_argument(
        "--period",
        default=None,
        help="HTML에 포함할 데이터 기간 (기본: 5y, 예: 1y, 2y, max)",
    )
    parser.add_argument(
        "--initial-range",
        choices=INITIAL_RANGES,
        default=None,
        help="HTML을 처음 열 때 표시할 기간 (기본: 6mo)",
    )
    parser.add_argument("--output", type=Path, help="HTML 저장 경로 (기본: <TICKER>_technical_analysis.html)")
    parser.add_argument("--swing-window", type=int, default=None, help="로컬 고점/저점 양쪽 비교 거래일 수 (기본: 3)")
    parser.add_argument(
        "--level-tolerance",
        type=float,
        default=None,
        help="같은 지지/저항 가격대로 묶을 허용 오차 %% (기본: 1.5)",
    )
    parser.add_argument("--min-touches", type=int, default=None, help="주요 가격대 최소 터치 수 (기본: 2)")
    parser.add_argument("--open", action="store_true", help="생성된 HTML을 기본 브라우저로 열기")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = load_settings(args.config)
        ticker = (args.ticker or settings.get("ticker", "")).strip().upper()
        if not ticker:
            raise ValueError("종목코드가 없습니다. settings.txt의 '종목코드'를 입력하세요.")

        period = args.period or settings.get("period", "5y")
        initial_range = args.initial_range or settings.get("initial_range", "6mo").lower()
        if initial_range not in INITIAL_RANGES:
            raise ValueError(f"처음표시기간은 {', '.join(INITIAL_RANGES)} 중 하나여야 합니다.")

        default_output = Path(f"{ticker.replace('^', '')}_technical_analysis.html")
        configured_output = Path(settings["output"]) if not args.ticker and settings.get("output") else default_output
        output = args.output or configured_output
        swing_window = args.swing_window if args.swing_window is not None else int(settings.get("swing_window", "3"))
        level_tolerance = (
            args.level_tolerance
            if args.level_tolerance is not None
            else float(settings.get("level_tolerance", "1.5"))
        )
        min_touches = args.min_touches if args.min_touches is not None else int(settings.get("min_touches", "2"))
        open_browser = args.open or _setting_bool(settings.get("open_browser", "아니오"), "브라우저자동열기")

        print(f"설정 파일: {args.config.resolve() if args.config.exists() else '사용 안 함'}")
        print(f"분석 시작: {ticker} | 데이터 {period} | 첫 화면 {initial_range}")
        raw = download_ohlcv(ticker, period)
        analyzed = calculate_indicators(raw)
        supports, resistances = find_support_resistance(
            analyzed,
            swing_window=swing_window,
            tolerance_pct=level_tolerance / 100,
            minimum_touches=min_touches,
        )
        trend = evaluate_trends(analyzed)
        print_summary(ticker, analyzed, supports, resistances, trend)
        create_chart(ticker, analyzed, supports, resistances, output, initial_range)
        print(f"인터랙티브 차트 저장: {output.resolve()}")
        if open_browser:
            webbrowser.open(output.resolve().as_uri())
            print("기본 브라우저에서 차트를 열었습니다.")
        return 0
    except (ValueError, RuntimeError, OSError, TypeError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n사용자가 작업을 중단했습니다.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
