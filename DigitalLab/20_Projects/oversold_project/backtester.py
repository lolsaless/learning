import pandas as pd
import numpy as np


def run_oversold_backtest(
    df: pd.DataFrame,
    entry_score_threshold: float = 70.0,
    exit_score_threshold: float = 45.0,
    max_hold_days: int = 10,
    stop_loss_pct: float = -5.0,
    take_profit_pct: float = 8.0,
    use_exit_score: bool = False
) -> tuple[pd.DataFrame, dict]:
    """
    단일 종목 long-only 백테스트
    진입: Oversold_Score >= entry_score_threshold
    청산:
      1) 손절 도달
      2) 익절 도달
      3) 최대 보유일 도달
      4) (선택) Oversold_Score <= exit_score_threshold
    """

    bt = df.copy().dropna(subset=["Close", "Oversold_Score"]).copy()
    bt = bt.sort_index()

    trades = []
    in_position = False

    entry_date = None
    entry_price = None
    entry_score = None
    holding_days = 0

    dates = bt.index.tolist()

    for i in range(len(bt)):
        current_date = dates[i]
        current_close = float(bt.iloc[i]["Close"])
        current_score = float(bt.iloc[i]["Oversold_Score"])

        if not in_position:
            if current_score >= entry_score_threshold:
                in_position = True
                entry_date = current_date
                entry_price = current_close
                entry_score = current_score
                holding_days = 0
            continue

        # 포지션 보유 중
        holding_days += 1
        ret_pct = (current_close / entry_price - 1.0) * 100.0

        exit_reason = None

        if ret_pct <= stop_loss_pct:
            exit_reason = "stop_loss"
        elif ret_pct >= take_profit_pct:
            exit_reason = "take_profit"
        elif use_exit_score and current_score <= exit_score_threshold:
            exit_reason = "score_exit"
        elif holding_days >= max_hold_days:
            exit_reason = "time_exit"

        if exit_reason is not None:
            trades.append({
                "entry_date": entry_date,
                "exit_date": current_date,
                "entry_price": round(entry_price, 4),
                "exit_price": round(current_close, 4),
                "entry_score": round(entry_score, 2),
                "exit_score": round(current_score, 2),
                "holding_days": holding_days,
                "return_pct": round(ret_pct, 2),
                "exit_reason": exit_reason
            })

            in_position = False
            entry_date = None
            entry_price = None
            entry_score = None
            holding_days = 0

    trades_df = pd.DataFrame(trades)

    summary = summarize_backtest(trades_df)
    return trades_df, summary


def summarize_backtest(trades_df: pd.DataFrame) -> dict:
    if trades_df.empty:
        return {
            "trade_count": 0,
            "win_rate_pct": 0.0,
            "avg_return_pct": 0.0,
            "median_return_pct": 0.0,
            "best_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
            "cumulative_return_pct_simple_sum": 0.0,
            "profit_factor": 0.0
        }

    returns = trades_df["return_pct"].astype(float)
    wins = returns[returns > 0]
    losses = returns[returns < 0]

    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf

    summary = {
        "trade_count": int(len(trades_df)),
        "win_rate_pct": round((returns > 0).mean() * 100, 2),
        "avg_return_pct": round(returns.mean(), 2),
        "median_return_pct": round(returns.median(), 2),
        "best_trade_pct": round(returns.max(), 2),
        "worst_trade_pct": round(returns.min(), 2),
        "cumulative_return_pct_simple_sum": round(returns.sum(), 2),
        "profit_factor": round(float(profit_factor), 2) if np.isfinite(profit_factor) else np.inf
    }
    return summary


def print_backtest_summary(summary: dict) -> None:
    print("\n[백테스트 요약]")
    print(f"총 거래 수         : {summary['trade_count']}")
    print(f"승률               : {summary['win_rate_pct']:.2f}%")
    print(f"평균 수익률         : {summary['avg_return_pct']:.2f}%")
    print(f"중앙값 수익률       : {summary['median_return_pct']:.2f}%")
    print(f"최고 거래 수익률    : {summary['best_trade_pct']:.2f}%")
    print(f"최저 거래 수익률    : {summary['worst_trade_pct']:.2f}%")
    print(f"단순 합산 수익률    : {summary['cumulative_return_pct_simple_sum']:.2f}%")
    print(f"Profit Factor      : {summary['profit_factor']}")