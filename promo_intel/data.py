"""Read-only access to promotion metrics in BigQuery, or to frozen fixtures when USE_FIXTURES=1."""
import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .config import get_settings

FIXTURES = Path(__file__).parent / "fixtures"

LEADERBOARD_COLUMNS = [
    "promo_id", "promo_name", "product_id", "product_name", "category", "list_price", "unit_cost",
    "discount_pct", "start_date", "end_date", "promo_days", "margin_pct", "baseline_daily_units",
    "expected_units", "actual_units", "actual_revenue", "actual_profit", "lift_pct",
    "breakeven_lift_pct", "incremental_revenue", "incremental_profit", "discount_spend",
    "subsidy_cost", "cannibalization_profit", "net_incremental_profit", "promo_roi", "verdict",
]
TIMESERIES_COLUMNS = [
    "promo_id", "date", "units", "net_revenue", "gross_profit", "baseline_daily_units", "is_promo_day",
]
CANDIDATE_COLUMNS = [
    "product_id", "product_name", "category", "list_price", "unit_cost", "margin_pct",
    "category_avg_lift", "baseline_daily_units", "score", "suggested_discount_pct",
    "projected_incremental_profit",
]
KPI_KEYS = ["total_revenue", "total_gross_profit", "total_discount_spend",
            "net_incremental_profit", "losing_promo_count"]

_SOURCES = {
    "leaderboard": ("v_promo_performance", LEADERBOARD_COLUMNS),
    "timeseries": ("v_promo_daily", TIMESERIES_COLUMNS),
    "candidates": ("v_next_promo_candidates", CANDIDATE_COLUMNS),
}
_DATE_COLUMNS = ("start_date", "end_date", "date")


@lru_cache(maxsize=1)
def _client():
    from google.cloud import bigquery

    return bigquery.Client(project=get_settings().project)


@lru_cache(maxsize=None)
def _query(sql: str) -> pd.DataFrame:
    return _client().query(sql.format(dataset=get_settings().dataset_ref)).to_dataframe()


@lru_cache(maxsize=None)
def _load(name: str, use_fixtures: bool) -> pd.DataFrame:
    view, columns = _SOURCES[name]
    if use_fixtures:
        df = pd.DataFrame(json.loads((FIXTURES / f"{name}.json").read_text()))
    else:
        df = _query(f"SELECT * FROM `{{dataset}}.{view}`")
    df = df[columns].copy()
    for col in _DATE_COLUMNS:
        if col in df:
            df[col] = pd.to_datetime(df[col].astype(str), utc=True).dt.tz_localize(None)
    return df


def _frame(name: str) -> pd.DataFrame:
    return _load(name, get_settings().use_fixtures).copy()


def get_leaderboard() -> pd.DataFrame:
    return _frame("leaderboard").sort_values("net_incremental_profit", ascending=False, ignore_index=True)


def get_promo_timeseries(promo_id: str) -> pd.DataFrame:
    df = _frame("timeseries")
    return df[df["promo_id"] == promo_id].sort_values("date", ignore_index=True)


def get_next_candidates() -> pd.DataFrame:
    return _frame("candidates").sort_values("score", ascending=False, ignore_index=True)


def get_kpis() -> dict:
    if get_settings().use_fixtures:
        return json.loads((FIXTURES / "kpis.json").read_text())
    totals = _query(
        "SELECT SUM(net_revenue) AS total_revenue, SUM(gross_profit) AS total_gross_profit, "
        "SUM(discount_amount) AS total_discount_spend FROM `{dataset}.v_product_daily`"
    ).iloc[0]
    leaderboard = get_leaderboard()
    return {
        "total_revenue": float(totals["total_revenue"]),
        "total_gross_profit": float(totals["total_gross_profit"]),
        "total_discount_spend": float(totals["total_discount_spend"]),
        "net_incremental_profit": float(leaderboard["net_incremental_profit"].sum()),
        "losing_promo_count": int((leaderboard["net_incremental_profit"] < 0).sum()),
    }
