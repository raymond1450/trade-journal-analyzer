import pandas as pd
import pytest

from analyze import add_metrics, longest_losing_streak, session_for_hour, summarize

COLUMNS = ["opened_at", "pair", "direction", "entry", "stop_loss", "exit"]


def make_trades(rows):
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["opened_at"] = pd.to_datetime(df["opened_at"])
    return df


def test_long_winner_is_plus_two_r():
    df = add_metrics(make_trades([["2026-01-05 09:00", "EURUSD", "long", 1.1000, 1.0950, 1.1100]]))
    assert df.loc[0, "r"] == pytest.approx(2.0)


def test_short_stop_out_is_minus_one_r():
    df = add_metrics(make_trades([["2026-01-05 09:00", "EURUSD", "short", 1.1000, 1.1050, 1.1050]]))
    assert df.loc[0, "r"] == pytest.approx(-1.0)


def test_zero_risk_is_rejected():
    with pytest.raises(ValueError):
        add_metrics(make_trades([["2026-01-05 09:00", "EURUSD", "long", 1.1000, 1.1000, 1.1100]]))


def test_summary_numbers():
    df = add_metrics(
        make_trades(
            [
                ["2026-01-05 09:00", "EURUSD", "long", 1.1000, 1.0950, 1.1100],   # +2R
                ["2026-01-06 09:00", "EURUSD", "short", 1.1000, 1.1050, 1.1050],  # -1R
            ]
        )
    )
    s = summarize(df)
    assert s["win_rate"] == pytest.approx(0.5)
    assert s["expectancy_r"] == pytest.approx(0.5)
    assert s["profit_factor"] == pytest.approx(2.0)
    assert s["max_drawdown_r"] == pytest.approx(1.0)


def test_longest_losing_streak():
    assert longest_losing_streak([True, False, False, False, True, False]) == 3


def test_session_for_hour():
    assert session_for_hour(3) == "Asian"
    assert session_for_hour(9) == "London"
    assert session_for_hour(14) == "London/NY overlap"
    assert session_for_hour(18) == "New York"
    assert session_for_hour(22) == "Off-hours"
