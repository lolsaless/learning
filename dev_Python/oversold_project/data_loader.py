import pandas as pd
import yfinance as yf


def load_price_data(ticker: str, start: str, end: str | None = None) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False)

    if df.empty:
        raise ValueError(f"데이터를 가져오지 못했습니다: {ticker}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    required_cols = ["Close", "Volume"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"필수 컬럼 누락: {col}")

    df = df[["Close", "Volume"]].copy()
    df.dropna(inplace=True)
    return df