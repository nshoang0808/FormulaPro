import pandas as pd
import pytest

import promo_intel as pi
from promo_intel.data import CANDIDATE_COLUMNS, KPI_KEYS, LEADERBOARD_COLUMNS, TIMESERIES_COLUMNS


@pytest.fixture(autouse=True)
def fixture_mode(monkeypatch):
    monkeypatch.setenv("USE_FIXTURES", "1")
    monkeypatch.delenv("GCP_PROJECT", raising=False)


def test_kpis():
    kpis = pi.get_kpis()
    assert list(kpis) == KPI_KEYS
    assert isinstance(kpis["losing_promo_count"], int)


def test_leaderboard():
    df = pi.get_leaderboard()
    assert list(df.columns) == LEADERBOARD_COLUMNS
    assert df["net_incremental_profit"].is_monotonic_decreasing
    assert {"Winner", "Margin Trap", "Cannibalizer", "Subsidy Dud"} <= set(df["verdict"])
    assert pd.api.types.is_datetime64_any_dtype(df["start_date"])


def test_timeseries():
    df = pi.get_promo_timeseries("PR01")
    assert list(df.columns) == TIMESERIES_COLUMNS
    assert len(df) == 42
    assert df["is_promo_day"].sum() == 14
    assert pi.get_promo_timeseries("NOPE").empty


def test_candidates():
    df = pi.get_next_candidates()
    assert list(df.columns) == CANDIDATE_COLUMNS
    assert df["score"].is_monotonic_decreasing


def test_analyze_promo():
    insight = pi.analyze_promo("PR01")
    assert isinstance(insight, pi.PromoInsight)
    assert insight.source == "fallback"
    with pytest.raises(ValueError):
        pi.analyze_promo("NOPE")


def test_recommend_next():
    recs = pi.recommend_next()
    assert 1 <= len(recs) <= 5
    assert all(isinstance(r, pi.NextPromoRec) for r in recs)
