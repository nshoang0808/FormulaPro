"""Deterministic insights built from metrics alone. Used when Gemini is unavailable."""
import math

import pandas as pd

from .schemas import Action, NextPromoRec, PromoInsight

DISCOUNT_STEPS = (0.05, 0.10, 0.15, 0.20, 0.25)
SAFETY = 1.5


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _money(value: float) -> str:
    return f"${abs(value):,.0f}"


def safe_discount(margin_pct: float, expected_lift: float) -> float | None:
    """Deepest discount step whose breakeven lift, times SAFETY, is covered by expected_lift."""
    ok = [d for d in DISCOUNT_STEPS
          if d < margin_pct and SAFETY * d / (margin_pct - d) <= expected_lift]
    return max(ok) if ok else None


def rule_insight(row: dict) -> PromoInsight:
    verdict = row["verdict"]
    lift = row["lift_pct"]
    net = row["net_incremental_profit"]
    revenue_change = row["incremental_revenue"] / (row["expected_units"] * row["list_price"])
    breakeven = row["breakeven_lift_pct"]
    breakeven_text = ("impossible (discount exceeds margin)" if _missing(breakeven)
                      else f"{breakeven:.0%}")
    new_discount = safe_discount(row["margin_pct"], max(lift, 0.0))

    if new_discount is not None:
        trap_action = Action(action=f"Cut the discount from {row['discount_pct']:.0%} to {new_discount:.0%}",
                             type="reduce_discount",
                             expected_impact="Keeps most of the lift while restoring margin",
                             confidence="medium")
    else:
        trap_action = Action(action="Stop discounting this product", type="stop",
                             expected_impact=f"Avoids losing {_money(net)} per run", confidence="high")

    by_verdict = {
        "Winner": (f"Lift of {lift:.0%} cleared the breakeven of {breakeven_text}",
                   Action(action="Run it again at the same depth", type="scale_up",
                          expected_impact=f"About +{_money(net)} per {row['promo_days']}-day run",
                          confidence="medium")),
        "Margin Trap": (f"Lift of {lift:.0%} fell short of the breakeven of {breakeven_text}", trap_action),
        "Cannibalizer": (f"Other {row['category']} products lost {_money(row['cannibalization_profit'])} "
                         "of profit during the promotion",
                         Action(action="Bundle with sibling products instead of discounting one item",
                                type="bundle",
                                expected_impact=f"Recovers part of the {_money(row['cannibalization_profit'])} "
                                                "lost from sibling products",
                                confidence="medium")),
        "Subsidy Dud": (f"Only {lift:.0%} lift, so most of the discount went to customers "
                        "who would have bought anyway",
                        Action(action="Stop this promotion", type="stop",
                               expected_impact=f"Saves about {_money(row['subsidy_cost'])} in discounts "
                                               "on units that sell anyway",
                               confidence="high")),
        "Underperformer": ("Both revenue and profit fell below baseline",
                           Action(action="Stop this promotion and test a different product",
                                  type="change_product", expected_impact=f"Avoids a {_money(net)} loss",
                                  confidence="medium")),
    }
    cause, action = by_verdict[verdict]
    headline = (f"Sales {'up' if revenue_change >= 0 else 'down'} {abs(revenue_change):.0%}, "
                f"profit {'up' if net >= 0 else 'down'} {_money(net)}")
    explanation = (f"{row['promo_name']} ran {row['discount_pct']:.0%} off {row['product_name']} "
                   f"for {row['promo_days']} days. Units moved {lift:+.0%} against baseline; "
                   f"breakeven lift was {breakeven_text}. Net incremental profit after category "
                   f"effects: {'+' if net >= 0 else '-'}{_money(net)}.")
    return PromoInsight(
        promo_id=row["promo_id"],
        headline=headline,
        explanation=explanation,
        root_causes=[cause],
        actions=[action],
        suggested_discount_pct={"Winner": row["discount_pct"], "Margin Trap": new_discount}.get(verdict),
        source="fallback",
    )


def rule_next_recs(candidates: pd.DataFrame, top: int = 5) -> list[NextPromoRec]:
    recs = []
    for row in candidates.head(top).to_dict("records"):
        discount = row["suggested_discount_pct"]
        has_discount = not _missing(discount)
        recs.append(NextPromoRec(
            product_id=row["product_id"],
            product_name=row["product_name"],
            suggested_discount_pct=discount if has_discount else None,
            rationale=(f"{row['margin_pct']:.0%} margin, and {row['category']} promotions "
                       f"average {row['category_avg_lift']:.0%} lift"),
            expected_impact=(f"About +{_money(row['projected_incremental_profit'])} over a 14-day promotion"
                             if has_discount else "Keep at full price; no discount clears breakeven"),
            confidence="medium",
            source="fallback",
        ))
    return recs
