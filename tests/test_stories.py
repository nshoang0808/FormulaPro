import pytest

from promo_intel.config import get_settings

pytestmark = pytest.mark.integration

EXPECTED_VERDICTS = {
    "PR01": "Margin Trap",
    "PR06": "Cannibalizer",
    "PR07": "Winner",
    "PR08": "Subsidy Dud",
}


def _query(sql: str):
    from google.cloud import bigquery

    s = get_settings()
    return bigquery.Client(project=s.project).query(sql.format(dataset=s.dataset_ref)).to_dataframe()


@pytest.fixture(scope="module")
def perf():
    return _query("SELECT * FROM `{dataset}.v_promo_performance`").set_index("promo_id")


@pytest.fixture(scope="module")
def candidates():
    return _query("SELECT * FROM `{dataset}.v_next_promo_candidates`")


@pytest.mark.parametrize("promo_id,verdict", EXPECTED_VERDICTS.items())
def test_planted_verdicts(perf, promo_id, verdict):
    assert perf.loc[promo_id, "verdict"] == verdict


def test_margin_trap_is_the_demo_hook(perf):
    row = perf.loc["PR01"]
    revenue_change = row.incremental_revenue / (row.expected_units * row.list_price)
    assert 0.20 <= revenue_change <= 0.40
    assert row.net_incremental_profit < 0


def test_every_promo_has_a_baseline(perf):
    assert len(perf) == 10
    assert (perf.baseline_daily_units > 0).all()


def test_candidates_exclude_recent_promos(candidates):
    ids = set(candidates.product_id)
    assert {"B03", "S05", "C03", "H05"}.isdisjoint(ids)
    assert "B01" in ids
    with_discount = candidates.dropna(subset=["suggested_discount_pct"])
    assert (with_discount.suggested_discount_pct < with_discount.margin_pct).all()
    assert (with_discount.projected_incremental_profit > 0).all()


def test_cannibalized_units_are_not_counted_as_lift(perf):
    row = perf.loc["PR06"]
    assert row.net_lift_pct <= row.lift_pct - 0.30


def test_cannibalizing_category_is_not_promoted_next(candidates):
    top5 = set(candidates.sort_values("score", ascending=False).head(5).product_id)
    assert {"C01", "C02"}.isdisjoint(top5)


def test_promo_daily_window(perf):
    daily = _query("SELECT * FROM `{dataset}.v_promo_daily` WHERE promo_id = 'PR01'")
    assert len(daily) == 42
    assert daily.is_promo_day.sum() == 14
