import datetime as dt

import pandas as pd
import pytest

import generate_data as g


@pytest.fixture(scope="module")
def frames(tmp_path_factory):
    return g.generate(tmp_path_factory.mktemp("data"))


def test_generation_is_deterministic(tmp_path, frames):
    again = g.generate(tmp_path)
    for name in ("products", "promotions", "sales"):
        pd.testing.assert_frame_equal(frames[name], again[name])
    assert (tmp_path / "sales.csv").exists()


def test_promotions_start_after_baseline_period():
    first_allowed = g.START + dt.timedelta(days=35)
    assert (g.build_promotions()["start_date"] >= first_allowed).all()


def test_baseline_windows_have_no_category_promotions():
    promos = g.build_promotions().merge(
        g.build_products()[["product_id", "category"]], on="product_id"
    )
    for p in promos.itertuples():
        window_start = p.start_date - dt.timedelta(days=28)
        others = promos[(promos.category == p.category) & (promos.promo_id != p.promo_id)]
        overlapping = others[(others.end_date >= window_start) & (others.start_date <= p.end_date)]
        assert overlapping.empty, f"{p.promo_id} overlaps {list(overlapping.promo_id)}"


def test_discounts_only_on_promo_lines(frames):
    sales = frames["sales"]
    assert (sales.loc[sales.promo_id.isna(), "discount_amount"] == 0).all()
    assert (sales.loc[sales.promo_id.notna(), "discount_amount"] > 0).all()


def test_margin_trap_lift_is_planted(frames):
    sales, promos = frames["sales"], frames["promotions"].set_index("promo_id")
    promo = promos.loc["PR01"]
    daily = sales[sales.product_id == "B01"].groupby("order_date")["quantity"].sum()
    dates = pd.Series(daily.index, index=daily.index)
    pre = daily[(dates >= promo.start_date - dt.timedelta(days=28)) & (dates < promo.start_date)]
    during = daily[(dates >= promo.start_date) & (dates <= promo.end_date)]
    assert during.mean() / pre.mean() == pytest.approx(1.85, abs=0.1)
