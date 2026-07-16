from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FALLBACK_RXRX_OHLCV = [
    # Source checked 2026-07-09 KST:
    # https://stockanalysis.com/stocks/rxrx/history/
    # Historical data provider shown on page: S&P Global Market Intelligence.
    ("2026-06-10", 3.15, 3.28, 3.03, 3.04, 19_534_855),
    ("2026-06-11", 3.00, 3.16, 2.95, 3.15, 25_424_806),
    ("2026-06-12", 3.20, 3.30, 3.12, 3.15, 14_837_646),
    ("2026-06-15", 3.30, 3.39, 3.23, 3.29, 15_393_576),
    ("2026-06-16", 3.27, 3.34, 3.16, 3.18, 15_477_040),
    ("2026-06-17", 3.18, 3.34, 3.07, 3.11, 22_173_125),
    ("2026-06-18", 3.18, 3.28, 3.11, 3.23, 24_853_721),
    ("2026-06-22", 3.20, 3.32, 3.11, 3.18, 14_444_897),
    ("2026-06-23", 3.10, 3.27, 3.09, 3.16, 11_169_433),
    ("2026-06-24", 3.20, 3.38, 3.16, 3.23, 15_304_675),
    ("2026-06-25", 3.24, 3.38, 3.19, 3.34, 15_562_243),
    ("2026-06-26", 3.29, 3.62, 3.28, 3.52, 42_027_521),
    ("2026-06-29", 3.62, 3.74, 3.55, 3.69, 22_827_048),
    ("2026-06-30", 3.68, 3.72, 3.57, 3.67, 23_055_708),
    ("2026-07-01", 3.65, 4.04, 3.61, 3.67, 35_638_910),
    ("2026-07-02", 3.75, 3.91, 3.70, 3.80, 32_543_230),
    ("2026-07-06", 3.78, 4.09, 3.66, 3.96, 37_974_665),
    ("2026-07-07", 3.95, 4.05, 3.81, 3.84, 28_753_865),
    ("2026-07-08", 3.72, 3.81, 3.63, 3.72, 22_653_988),
]


def convert_numbers_to_xlsx(input_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    expected = output_dir / f"{input_path.stem}.xlsx"
    if expected.exists():
        return expected

    cmd = [
        "soffice",
        "--headless",
        "-env:UserInstallation=file:///tmp/lo-ark-recursion",
        "--convert-to",
        "xlsx",
        "--outdir",
        str(output_dir),
        str(input_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("LibreOffice/soffice is required to read .numbers files.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Numbers conversion failed:\n{exc.stderr or exc.stdout}") from exc

    if not expected.exists():
        candidates = sorted(output_dir.glob("*.xlsx"))
        if not candidates:
            raise RuntimeError("Numbers conversion finished, but no .xlsx file was created.")
        return candidates[0]
    return expected


def load_ark_trades(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".numbers":
        path = convert_numbers_to_xlsx(path, Path("ark_recursion_work/converted"))

    raw = pd.read_excel(path)
    raw = raw.rename(columns={raw.columns[0]: "date", "매도": "sell_shares", "매수": "buy_shares"})
    raw["date"] = pd.to_datetime(raw["date"])
    raw["buy_shares"] = pd.to_numeric(raw["buy_shares"], errors="coerce").fillna(0)
    raw["sell_shares"] = pd.to_numeric(raw["sell_shares"], errors="coerce").fillna(0)
    raw["net_shares"] = raw["buy_shares"] - raw["sell_shares"]

    by_date = (
        raw.groupby("date", as_index=False)
        .agg(
            buy_shares=("buy_shares", "sum"),
            sell_shares=("sell_shares", "sum"),
            net_shares=("net_shares", "sum"),
            etfs=("ETF", lambda x: ", ".join(sorted(set(map(str, x))))),
        )
        .sort_values("date")
    )
    return by_date


def load_rxrx_ohlcv(start: pd.Timestamp, end: pd.Timestamp, force_fallback: bool = False) -> pd.DataFrame:
    if not force_fallback:
        try:
            import yfinance as yf

            px = yf.download("RXRX", start=start.date(), end=(end + pd.Timedelta(days=2)).date(), auto_adjust=False)
            if not px.empty:
                px = px.reset_index()
                px.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower() for c in px.columns]
                return px.rename(columns={"date": "date"})[["date", "open", "high", "low", "close", "volume"]]
        except Exception as exc:
            print(f"[info] yfinance unavailable; using embedded StockAnalysis snapshot. Reason: {exc}")

    px = pd.DataFrame(FALLBACK_RXRX_OHLCV, columns=["date", "open", "high", "low", "close", "volume"])
    px["date"] = pd.to_datetime(px["date"])
    return px[(px["date"] >= start) & (px["date"] <= end)].copy()


def build_dataset(trades: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    data = prices.merge(trades, on="date", how="left")
    for col in ["buy_shares", "sell_shares", "net_shares"]:
        data[col] = data[col].fillna(0)
    data["etfs"] = data["etfs"].fillna("")
    data["daily_return"] = data["close"].pct_change()
    data["next_day_return"] = data["close"].pct_change().shift(-1)
    data["ark_participation"] = data["net_shares"] / data["volume"]
    data["ark_abs_participation"] = data["net_shares"].abs() / data["volume"]
    data["ark_dollar_flow_at_close"] = data["net_shares"] * data["close"]
    data["cum_net_shares"] = data["net_shares"].cumsum()
    data["cum_dollar_flow_at_close"] = data["ark_dollar_flow_at_close"].cumsum()
    data["volume_ma5"] = data["volume"].rolling(5, min_periods=1).mean()
    return data


def make_charts(data: pd.DataFrame, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    trade_days = data[data["net_shares"] != 0].copy()
    fig = plt.figure(figsize=(16, 12), constrained_layout=True)
    gs = fig.add_gridspec(3, 2, height_ratios=[1.25, 1, 1])

    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(data["date"], data["close"], color="#1f2937", lw=2.2, label="RXRX close")
    ax1.set_title("ARK RXRX Flow Overlay: Price, Volume, and Net Shares", fontsize=15, weight="bold")
    ax1.set_ylabel("Close price ($)")
    ax1.grid(alpha=0.22)

    ax1b = ax1.twinx()
    ax1b.bar(data["date"], data["volume"] / 1_000_000, color="#cbd5e1", width=0.75, alpha=0.45, label="Volume")
    ax1b.set_ylabel("Volume (million shares)")

    buys = trade_days[trade_days["net_shares"] > 0]
    sells = trade_days[trade_days["net_shares"] < 0]
    if not buys.empty:
        ax1.scatter(
            buys["date"],
            buys["close"],
            s=np.clip(buys["net_shares"].abs() / 1_000, 35, 950),
            color="#16a34a",
            alpha=0.72,
            edgecolor="white",
            linewidth=1,
            label="ARK net buy",
        )
    if not sells.empty:
        ax1.scatter(
            sells["date"],
            sells["close"],
            s=np.clip(sells["net_shares"].abs() / 1_000, 35, 950),
            color="#dc2626",
            alpha=0.72,
            edgecolor="white",
            linewidth=1,
            label="ARK net sell",
        )
    for _, row in trade_days.iterrows():
        ax1.annotate(
            f"{row['net_shares']/1000:+.0f}k",
            (row["date"], row["close"]),
            textcoords="offset points",
            xytext=(0, 9 if row["net_shares"] >= 0 else -15),
            ha="center",
            fontsize=8,
            color="#111827",
        )
    ax1.legend(loc="upper left")

    ax2 = fig.add_subplot(gs[1, 0])
    colors = trade_days["next_day_return"].fillna(0) * 100
    sc = ax2.scatter(
        trade_days["daily_return"].fillna(0) * 100,
        trade_days["ark_participation"] * 100,
        s=np.clip(trade_days["net_shares"].abs() / 900, 55, 1200),
        c=colors,
        cmap="RdYlGn",
        edgecolor="#111827",
        linewidth=0.6,
        alpha=0.86,
    )
    ax2.axvline(0, color="#64748b", lw=1)
    ax2.axhline(0, color="#64748b", lw=1)
    ax2.set_title("Liquidity Absorption Map", weight="bold")
    ax2.set_xlabel("Same-day RXRX return (%)")
    ax2.set_ylabel("ARK net shares / RXRX volume (%)")
    ax2.grid(alpha=0.22)
    cb = fig.colorbar(sc, ax=ax2)
    cb.set_label("Next trading-day return (%)")
    for _, row in trade_days.iterrows():
        ax2.annotate(row["date"].strftime("%m-%d"), (row["daily_return"] * 100 if pd.notna(row["daily_return"]) else 0, row["ark_participation"] * 100), fontsize=8, xytext=(4, 4), textcoords="offset points")

    ax3 = fig.add_subplot(gs[1, 1])
    ax3.bar(data["date"], data["buy_shares"] / 1_000, color="#16a34a", label="Buy")
    ax3.bar(data["date"], -data["sell_shares"] / 1_000, color="#dc2626", label="Sell")
    ax3.plot(data["date"], data["cum_net_shares"] / 1_000, color="#0f172a", lw=2.2, marker="o", ms=3, label="Cumulative net")
    ax3.axhline(0, color="#64748b", lw=1)
    ax3.set_title("Flow Regime: Buy/Sell and Cumulative Net", weight="bold")
    ax3.set_ylabel("Shares (thousand)")
    ax3.grid(alpha=0.22)
    ax3.legend()

    ax4 = fig.add_subplot(gs[2, 0])
    impact = trade_days.copy()
    impact["abs_participation_pct"] = impact["ark_abs_participation"] * 100
    bars = ax4.bar(
        impact["date"].dt.strftime("%m-%d"),
        impact["abs_participation_pct"],
        color=np.where(impact["net_shares"] >= 0, "#22c55e", "#ef4444"),
    )
    ax4.set_title("Market Footprint: ARK Flow as % of Daily Volume", weight="bold")
    ax4.set_ylabel("Absolute participation (%)")
    ax4.tick_params(axis="x", rotation=45)
    ax4.grid(axis="y", alpha=0.22)
    for bar, val in zip(bars, impact["abs_participation_pct"]):
        ax4.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{val:.1f}%", ha="center", va="bottom", fontsize=8)

    ax5 = fig.add_subplot(gs[2, 1])
    data["close_index"] = data["close"] / data["close"].iloc[0] * 100
    cum = data["cum_net_shares"]
    ax5.plot(data["date"], data["close_index"], color="#2563eb", lw=2.1, label="RXRX close indexed")
    ax5b = ax5.twinx()
    ax5b.fill_between(data["date"], cum / 1_000, color="#f59e0b", alpha=0.26, label="Cumulative ARK net shares")
    ax5b.plot(data["date"], cum / 1_000, color="#d97706", lw=2.0)
    ax5.set_title("Accumulation vs Price Base", weight="bold")
    ax5.set_ylabel("Close index, first date = 100")
    ax5b.set_ylabel("Cumulative net shares (thousand)")
    ax5.grid(alpha=0.22)

    for ax in [ax1, ax3, ax5]:
        ax.tick_params(axis="x", rotation=30)

    out = out_dir / "ark_rxrx_flow_dashboard.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out


def print_summary(data: pd.DataFrame) -> None:
    trade = data[data["net_shares"] != 0].copy()
    net = trade["net_shares"].sum()
    buy = trade["buy_shares"].sum()
    sell = trade["sell_shares"].sum()
    max_buy = trade.loc[trade["net_shares"].idxmax()]
    max_part = trade.loc[trade["ark_abs_participation"].idxmax()]

    print("\n=== ARK RXRX FLOW SUMMARY ===")
    print(f"Period: {data['date'].min().date()} to {data['date'].max().date()}")
    print(f"Total ARK buy shares: {buy:,.0f}")
    print(f"Total ARK sell shares: {sell:,.0f}")
    print(f"Net ARK shares: {net:,.0f}")
    print(f"Largest net buy: {max_buy['date'].date()} / {max_buy['net_shares']:,.0f} shares / close ${max_buy['close']:.2f}")
    print(f"Highest market footprint: {max_part['date'].date()} / {max_part['ark_abs_participation']*100:.2f}% of RXRX volume")
    print(f"RXRX close change over loaded price window: {(data['close'].iloc[-1]/data['close'].iloc[0]-1)*100:.2f}%")
    print(f"Trade-day median ARK footprint: {trade['ark_abs_participation'].median()*100:.2f}% of volume")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze ARK's RXRX trading record with RXRX close and volume.")
    parser.add_argument(
        "--input",
        default="/workspace/.cache/01-Ark-ETF-Recursion-.numbers",
        help="Path to ARK trading record. Supports .numbers converted by LibreOffice or .xlsx.",
    )
    parser.add_argument("--output-dir", default="/workspace/ark_recursion_work/outputs")
    parser.add_argument("--force-fallback-prices", action="store_true", help="Use embedded StockAnalysis snapshot instead of yfinance.")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.output_dir)

    trades = load_ark_trades(input_path)
    prices = load_rxrx_ohlcv(trades["date"].min() - pd.Timedelta(days=5), trades["date"].max(), args.force_fallback_prices)
    data = build_dataset(trades, prices)

    out_dir.mkdir(parents=True, exist_ok=True)
    merged_path = out_dir / "ark_rxrx_merged_dataset.csv"
    data.to_csv(merged_path, index=False)
    chart_path = make_charts(data, out_dir)

    print_summary(data)
    print(f"\nSaved chart: {chart_path}")
    print(f"Saved merged dataset: {merged_path}")


if __name__ == "__main__":
    main()
