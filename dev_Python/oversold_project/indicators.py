import numpy as np
import pandas as pd


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def add_indicators(
    df: pd.DataFrame,
    rsi_period: int,
    price_drop_window: int,
    volume_ma_window: int,
    high_window: int
) -> pd.DataFrame:
    out = df.copy()

    out["MA20"] = out["Close"].rolling(20).mean()
    out["RSI14"] = compute_rsi(out["Close"], period=rsi_period)

    out[f"Ret_{price_drop_window}d"] = out["Close"].pct_change(price_drop_window) * 100

    out[f"Vol_MA_{volume_ma_window}"] = out["Volume"].rolling(volume_ma_window).mean()
    out["Vol_Ratio"] = out["Volume"] / out[f"Vol_MA_{volume_ma_window}"]

    out[f"Rolling_High_{high_window}"] = out["Close"].rolling(high_window).max()
    out["Drawdown_from_High"] = (
        (out["Close"] - out[f"Rolling_High_{high_window}"])
        / out[f"Rolling_High_{high_window}"]
        * 100
    )

    return out