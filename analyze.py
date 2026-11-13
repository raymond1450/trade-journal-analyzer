"""Trade Journal Analyzer

Reads a CSV of trades and prints the numbers that matter: win rate,
average R, expectancy, profit factor, drawdown, and breakdowns by
pair, session, direction and weekday.

Usage:
    python analyze.py sample_trades.csv
    python analyze.py my_trades.csv --chart equity_curve.png
"""

import argparse
import sys

import pandas as pd

REQUIRED_COLUMNS = ["opened_at", "pair", "direction", "entry", "stop_loss", "exit"]


def load_trades(path):
    """Read the CSV and check it has the columns we need."""
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError("Missing column(s): " + ", ".join(missing))
    df["opened_at"] = pd.to_datetime(df["opened_at"])
    df["direction"] = df["direction"].str.strip().str.lower()
    if not df["direction"].isin(["long", "short"]).all():
        raise ValueError("direction must be 'long' or 'short' on every row")
    return df.sort_values("opened_at").reset_index(drop=True)


def session_for_hour(hour):
    """Map an hour (0-23, UTC) to a rough forex session."""
    if 0 <= hour < 7:
        return "Asian"
    if 7 <= hour < 12:
        return "London"
    if 12 <= hour < 16:
        return "London/NY overlap"
    if 16 <= hour < 21:
        return "New York"
    return "Off-hours"


def add_metrics(df):
    """Add R-multiple, win flag, session and weekday columns.

    R-multiple = profit or loss divided by the amount you risked.
    A trade that makes twice what you risked is +2R; a full stop-out is -1R.
    """
    df = df.copy()
    risk = (df["entry"] - df["stop_loss"]).abs()
    if (risk == 0).any():
        raise ValueError("Some trades have entry equal to stop_loss, so risk is zero")
    direction = df["direction"].map({"long": 1, "short": -1})
    df["r"] = (df["exit"] - df["entry"]) * direction / risk
    df["win"] = df["r"] > 0
    df["session"] = df["opened_at"].dt.hour.map(session_for_hour)
    df["weekday"] = df["opened_at"].dt.day_name()
    return df


def longest_losing_streak(wins):
    """Longest run of consecutive non-winning trades."""
    longest = current = 0
    for won in wins:
        current = 0 if won else current + 1
        longest = max(longest, current)
    return longest


def summarize(df):
    """Headline numbers for the whole journal."""
    wins = df.loc[df["r"] > 0, "r"]
    losses = df.loc[df["r"] <= 0, "r"]
    cumulative = df["r"].cumsum()
    peak = cumulative.cummax().clip(lower=0)
    gross_loss = abs(losses.sum())
    return {
        "trades": len(df),
        "win_rate": df["win"].mean(),
        "avg_win_r": wins.mean() if len(wins) else 0.0,
        "avg_loss_r": losses.mean() if len(losses) else 0.0,
        "expectancy_r": df["r"].mean(),
        "profit_factor": wins.sum() / gross_loss if gross_loss > 0 else float("inf"),
        "total_r": df["r"].sum(),
        "max_drawdown_r": (peak - cumulative).max(),
        "longest_losing_streak": longest_losing_streak(df["win"]),
        "best_trade_r": df["r"].max(),
        "worst_trade_r": df["r"].min(),
    }


def breakdown(df, column):
    """Performance grouped by a column such as pair or session."""
    grouped = df.groupby(column).agg(
        trades=("r", "size"),
        win_rate=("win", "mean"),
        avg_r=("r", "mean"),
        total_r=("r", "sum"),
    )
    grouped["win_rate"] = (grouped["win_rate"] * 100).round(1)
    return grouped.round(2).sort_values("total_r", ascending=False)


def print_report(df):
    s = summarize(df)
    print("=== Summary ===")
    print(f"Trades:                 {s['trades']}")
    print(f"Win rate:               {s['win_rate']:.1%}")
    print(f"Average win:            {s['avg_win_r']:+.2f}R")
    print(f"Average loss:           {s['avg_loss_r']:+.2f}R")
    print(f"Expectancy per trade:   {s['expectancy_r']:+.2f}R")
    print(f"Profit factor:          {s['profit_factor']:.2f}")
    print(f"Total result:           {s['total_r']:+.2f}R")
    print(f"Max drawdown:           {s['max_drawdown_r']:.2f}R")
    print(f"Longest losing streak:  {s['longest_losing_streak']}")
    print(f"Best / worst trade:     {s['best_trade_r']:+.2f}R / {s['worst_trade_r']:+.2f}R")
    for column, title in [
        ("pair", "By pair"),
        ("session", "By session (UTC)"),
        ("direction", "By direction"),
        ("weekday", "By weekday"),
    ]:
        print(f"\n=== {title} ===")
        print(breakdown(df, column).to_string())
    if s["trades"] < 30:
        print(
            "\nNote: fewer than 30 trades. Treat these numbers as a rough "
            "guide, not a verdict."
        )


def save_equity_curve(df, path):
    """Save a chart of cumulative R after each trade."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cumulative = df["r"].cumsum()
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(range(1, len(cumulative) + 1), cumulative, linewidth=2)
    ax.axhline(0, color="grey", linewidth=1)
    ax.set_xlabel("Trade number")
    ax.set_ylabel("Cumulative R")
    ax.set_title("Equity curve (in R)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Analyze a CSV trade journal.")
    parser.add_argument("csv_path", help="Path to your trades CSV")
    parser.add_argument("--chart", metavar="PNG", help="Save an equity curve image here")
    args = parser.parse_args()

    try:
        df = add_metrics(load_trades(args.csv_path))
    except (OSError, ValueError) as err:
        sys.exit(f"Error: {err}")

    print_report(df)
    if args.chart:
        save_equity_curve(df, args.chart)
        print(f"\nSaved equity curve to {args.chart}")


if __name__ == "__main__":
    main()
