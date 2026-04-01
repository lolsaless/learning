import numpy as np
import pandas as pd


def minmax_score(series: pd.Series, low: float, high: float, reverse: bool = False) -> pd.Series:
    clipped = series.clip(lower=min(low, high), upper=max(low, high))

    if reverse:
        score = (high - clipped) / (high - low) * 100
    else:
        score = (clipped - low) / (high - low) * 100

    return score.clip(0, 100)


def label_score(score: float, thresholds: dict) -> str:
    if score < thresholds["normal"]:
        return "정상 조정"
    if score < thresholds["weak_oversold"]:
        return "약한 과매도 후보"
    if score < thresholds["meaningful_oversold"]:
        return "의미 있는 과매도"
    return "투매/패닉 가능성"


def add_oversold_score(
    df: pd.DataFrame,
    weight_price: float,
    weight_volume: float,
    weight_rsi: float,
    weight_drawdown: float,
    thresholds: dict,
    price_drop_window: int = 5
) -> pd.DataFrame:
    out = df.copy()

    out["Price_Drop_Score"] = minmax_score(
        out[f"Ret_{price_drop_window}d"],
        low=-12,
        high=-2,
        reverse=True
    )

    out["Volume_Score"] = minmax_score(
        out["Vol_Ratio"],
        low=1.0,
        high=3.0,
        reverse=False
    )

    out["RSI_Score"] = minmax_score(
        out["RSI14"],
        low=15,
        high=50,
        reverse=True
    )

    out["Drawdown_Score"] = minmax_score(
        out["Drawdown_from_High"],
        low=-20,
        high=-3,
        reverse=True
    )

    out["Oversold_Score"] = (
        weight_price * out["Price_Drop_Score"] +
        weight_volume * out["Volume_Score"] +
        weight_rsi * out["RSI_Score"] +
        weight_drawdown * out["Drawdown_Score"]
    ).clip(0, 100)

    out["Oversold_Label"] = out["Oversold_Score"].apply(lambda x: label_score(x, thresholds))
    return out