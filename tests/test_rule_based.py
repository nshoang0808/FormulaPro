import pandas as pd

from promo_intel.rule_based import rule_insight, rule_next_recs, safe_discount

MARGIN_TRAP = dict(
    promo_id="PR01", promo_name="Cola Summer Blast 30% Off", product_name="Fizz Cola 330ml",
    category="Beverages", list_price=2.0, discount_pct=0.30, promo_days=14, margin_pct=0.35,
    expected_units=840.0, lift_pct=0.85, breakeven_lift_pct=6.0, incremental_revenue=504.0,
    incremental_profit=-432.6, cannibalization_profit=0.0, net_incremental_profit=-432.6,
    subsidy_cost=504.0, verdict="Margin Trap",
)


def test_safe_discount_picks_deepest_step_that_clears_breakeven():
    assert safe_discount(0.35, 0.85) == 0.10
    assert safe_discount(0.50, 0.50) == 0.10


def test_safe_discount_none_when_lift_too_small():
    assert safe_discount(0.40, 0.03) is None


def test_margin_trap_insight():
    insight = rule_insight(MARGIN_TRAP)
    assert insight.headline == "Sales up 30%, profit down $433"
    assert insight.actions[0].type == "reduce_discount"
    assert insight.suggested_discount_pct == 0.10
    assert insight.source == "fallback"


def test_subsidy_dud_recommends_stop():
    row = {**MARGIN_TRAP, "verdict": "Subsidy Dud", "lift_pct": 0.03, "incremental_revenue": -300.0}
    insight = rule_insight(row)
    assert insight.actions[0].type == "stop"
    assert insight.suggested_discount_pct is None
    assert insight.headline.startswith("Sales down")


def test_impossible_breakeven_is_explained():
    row = {**MARGIN_TRAP, "breakeven_lift_pct": float("nan")}
    assert "impossible" in rule_insight(row).explanation


def test_rule_next_recs_handles_no_discount():
    df = pd.DataFrame([dict(
        product_id="H02", product_name="Paper Towels 6pk", category="Household",
        margin_pct=0.25, category_avg_lift=0.2, suggested_discount_pct=float("nan"),
        projected_incremental_profit=0.0,
    )])
    recs = rule_next_recs(df)
    assert recs[0].suggested_discount_pct is None
    assert "full price" in recs[0].expected_impact
    assert recs[0].source == "fallback"
