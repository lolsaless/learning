import warnings
warnings.filterwarnings("ignore")

from config import (
    TICKER, START_DATE, END_DATE,
    RSI_PERIOD, PRICE_DROP_WINDOW, VOLUME_MA_WINDOW, HIGH_WINDOW,
    WEIGHT_PRICE, WEIGHT_VOLUME, WEIGHT_RSI, WEIGHT_DRAWDOWN,
    LABEL_THRESHOLDS,
    OUTPUT_DIR, SAVE_FULL_DATA_CSV, SAVE_SCORE_TABLE_CSV, SAVE_BACKTEST_CSV,
    BACKTEST_ENABLED, ENTRY_SCORE_THRESHOLD, EXIT_SCORE_THRESHOLD,
    MAX_HOLD_DAYS, STOP_LOSS_PCT, TAKE_PROFIT_PCT, USE_EXIT_SCORE
)
from data_loader import load_price_data
from indicators import add_indicators
from scorer import add_oversold_score
from report import make_score_table, print_latest_summary, print_backtest_trades
from plotter import plot_oversold_dashboard
from exporter import build_output_path, save_dataframe_csv
from backtester import run_oversold_backtest, print_backtest_summary


def main():
    df = load_price_data(TICKER, START_DATE, END_DATE)

    df = add_indicators(
        df,
        rsi_period=RSI_PERIOD,
        price_drop_window=PRICE_DROP_WINDOW,
        volume_ma_window=VOLUME_MA_WINDOW,
        high_window=HIGH_WINDOW
    )

    df = add_oversold_score(
        df,
        weight_price=WEIGHT_PRICE,
        weight_volume=WEIGHT_VOLUME,
        weight_rsi=WEIGHT_RSI,
        weight_drawdown=WEIGHT_DRAWDOWN,
        thresholds=LABEL_THRESHOLDS,
        price_drop_window=PRICE_DROP_WINDOW
    )

    print_latest_summary(df)

    score_table = make_score_table(df, tail_n=20)
    print("\n[최근 점수표]")
    print(score_table.to_string())

    if SAVE_FULL_DATA_CSV:
        full_data_path = build_output_path(OUTPUT_DIR, f"{TICKER}_full_data.csv")
        save_dataframe_csv(df, full_data_path)
        print(f"\n전체 데이터 CSV 저장 완료: {full_data_path}")

    if SAVE_SCORE_TABLE_CSV:
        score_table_path = build_output_path(OUTPUT_DIR, f"{TICKER}_score_table.csv")
        save_dataframe_csv(score_table, score_table_path)
        print(f"점수표 CSV 저장 완료: {score_table_path}")

    if BACKTEST_ENABLED:
        trades_df, summary = run_oversold_backtest(
            df=df,
            entry_score_threshold=ENTRY_SCORE_THRESHOLD,
            exit_score_threshold=EXIT_SCORE_THRESHOLD,
            max_hold_days=MAX_HOLD_DAYS,
            stop_loss_pct=STOP_LOSS_PCT,
            take_profit_pct=TAKE_PROFIT_PCT,
            use_exit_score=USE_EXIT_SCORE
        )

        print_backtest_summary(summary)
        print_backtest_trades(trades_df, tail_n=20)

        if SAVE_BACKTEST_CSV:
            trades_path = build_output_path(OUTPUT_DIR, f"{TICKER}_backtest_trades.csv")
            save_dataframe_csv(trades_df, trades_path)
            print(f"\n백테스트 거래내역 CSV 저장 완료: {trades_path}")

    plot_oversold_dashboard(df, TICKER)


if __name__ == "__main__":
    main()