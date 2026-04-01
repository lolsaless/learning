import matplotlib.pyplot as plt
import pandas as pd


def plot_oversold_dashboard(df: pd.DataFrame, ticker: str) -> None:
    plot_df = df.dropna(subset=["RSI14", "Oversold_Score"]).copy()

    fig, axes = plt.subplots(
        4, 1,
        figsize=(14, 12),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1.5, 1.5, 1.5]}
    )

    axes[0].plot(plot_df.index, plot_df["Close"], label="Close")
    axes[0].plot(plot_df.index, plot_df["MA20"], label="MA20", linestyle="--")

    high_signal = plot_df["Oversold_Score"] >= 70
    axes[0].scatter(
        plot_df.index[high_signal],
        plot_df.loc[high_signal, "Close"],
        label="Oversold>=70",
        marker="o",
        s=30
    )
    axes[0].set_title(f"{ticker} | Price / Volume / RSI / Oversold Score")
    axes[0].set_ylabel("Price")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.3)

    axes[1].bar(plot_df.index, plot_df["Volume"], label="Volume")
    if "Vol_MA_20" in plot_df.columns:
        axes[1].plot(plot_df.index, plot_df["Vol_MA_20"], label="Volume MA20", linestyle="--")
    axes[1].set_ylabel("Volume")
    axes[1].legend(loc="upper left")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(plot_df.index, plot_df["RSI14"], label="RSI14")
    axes[2].axhline(30, linestyle="--", label="RSI 30")
    axes[2].axhline(70, linestyle="--", label="RSI 70")
    axes[2].set_ylabel("RSI")
    axes[2].set_ylim(0, 100)
    axes[2].legend(loc="upper left")
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(plot_df.index, plot_df["Oversold_Score"], label="Oversold Score")
    axes[3].axhline(60, linestyle="--", label="60")
    axes[3].axhline(80, linestyle="--", label="80")
    axes[3].set_ylabel("Score")
    axes[3].set_ylim(0, 100)
    axes[3].legend(loc="upper left")
    axes[3].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()