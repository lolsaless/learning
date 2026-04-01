import pandas as pd


def make_score_table(df: pd.DataFrame, tail_n: int = 20) -> pd.DataFrame:
    cols = [
        "Close",
        "Volume",
        "RSI14",
        "Ret_5d",
        "Vol_Ratio",
        "Drawdown_from_High",
        "Price_Drop_Score",
        "Volume_Score",
        "RSI_Score",
        "Drawdown_Score",
        "Oversold_Score",
        "Oversold_Label"
    ]

    existing_cols = [c for c in cols if c in df.columns]
    table = df[existing_cols].tail(tail_n).copy()

    round_cols = [
        "Close", "RSI14", "Ret_5d", "Vol_Ratio", "Drawdown_from_High",
        "Price_Drop_Score", "Volume_Score", "RSI_Score",
        "Drawdown_Score", "Oversold_Score"
    ]

    for col in round_cols:
        if col in table.columns:
            table[col] = table[col].round(2)

    return table


def print_latest_summary(df: pd.DataFrame) -> None:
    latest = df.dropna().iloc[-1]

    print("\n[최신 시점 요약]")
    print(f"종가               : {latest['Close']:.2f}")
    print(f"RSI(14)            : {latest['RSI14']:.2f}")
    print(f"최근 5일 수익률     : {latest['Ret_5d']:.2f}%")
    print(f"거래량 비율         : {latest['Vol_Ratio']:.2f}배")
    print(f"최근 20일 고점 대비  : {latest['Drawdown_from_High']:.2f}%")
    print(f"과매도 점수         : {latest['Oversold_Score']:.2f} / 100")
    print(f"판정               : {latest['Oversold_Label']}")


def print_backtest_trades(trades_df: pd.DataFrame, tail_n: int = 20) -> None:
    print("\n[최근 백테스트 거래 내역]")
    if trades_df.empty:
        print("거래 없음")
        return
    print(trades_df.tail(tail_n).to_string(index=False))