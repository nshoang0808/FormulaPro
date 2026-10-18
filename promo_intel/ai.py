"""AI insights for promotions: Gemini on Vertex AI, with a deterministic fallback."""
import json
import logging
import math
from functools import lru_cache
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from .config import get_settings
from .data import get_leaderboard, get_next_candidates
from .rule_based import rule_insight, rule_next_recs, safe_discount
from .schemas import NextPromoRec, NextRecsBody, PromoInsight, PromoInsightBody

log = logging.getLogger(__name__)
FIXTURES = Path(__file__).parent / "fixtures"
TIMEOUT_MS = 15_000

SYSTEM_INSTRUCTION = (
    "You are a retail pricing analyst explaining promotion results to a category manager. "
    "Use only the numbers provided; never invent figures. Format money like $1,234 and "
    "percentages like 30%. Be specific and actionable."
)
PROMO_FIELDS = [
    "promo_name", "product_name", "category", "discount_pct", "promo_days", "margin_pct",
    "baseline_daily_units", "expected_units", "actual_units", "lift_pct", "net_lift_pct", "breakeven_lift_pct",
    "actual_revenue", "incremental_revenue", "incremental_profit", "cannibalization_profit",
    "net_incremental_profit", "subsidy_cost", "discount_spend", "promo_roi", "verdict",
]
CANDIDATE_FIELDS = [
    "product_id", "product_name", "category", "list_price", "margin_pct", "category_avg_lift",
    "baseline_daily_units", "suggested_discount_pct", "projected_incremental_profit",
]

_insight_cache: dict[str, PromoInsight] = {}
_recs_cache: dict[str, list[NextPromoRec]] = {}


@lru_cache(maxsize=1)
def _genai_client():
    from google import genai
    from google.genai import types

    s = get_settings()
    return genai.Client(vertexai=True, project=s.project, location=s.location,
                        http_options=types.HttpOptions(timeout=TIMEOUT_MS))


def _generate(prompt: str, schema: type[BaseModel]) -> BaseModel:
    from google.genai import types

    response = _genai_client().models.generate_content(
        model=get_settings().gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
            thinking_config=types.ThinkingConfig(thinking_budget=0),  # latency matters more than depth here
        ),
    )
    return schema.model_validate_json(response.text)


SIGNED_PCT = {"lift_pct", "net_lift_pct", "revenue_change_pct"}


def _clean(key: str, value):
    """JSON-safe value; ratios become percent strings so the model can't misread fractions."""
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    if key.endswith("_pct") or key in ("promo_roi", "category_avg_lift"):
        return f"{value:+.0%}" if key in SIGNED_PCT else f"{value:.0%}"
    return round(value, 2) if isinstance(value, float) else value


def _facts(row: dict, fields: list[str]) -> dict:
    return {k: _clean(k, row[k]) for k in fields}


def _promo_prompt(row: dict) -> str:
    facts = _facts(row, PROMO_FIELDS)
    facts["revenue_change_pct"] = _clean(
        "revenue_change_pct", row["incremental_revenue"] / (row["expected_units"] * row["list_price"]))
    safe = safe_discount(row["margin_pct"], max(row["lift_pct"], 0.0))
    facts["safe_discount_pct"] = _clean("safe_discount_pct", safe) if safe is not None else None
    return (
        "Analyze this retail promotion.\n"
        f"Metrics (JSON): {json.dumps(facts)}\n"
        "Definitions: lift_pct = unit change vs. expected_units (the 28 days before the promotion). "
        "net_lift_pct = lift_pct minus units lost by same-category products (stolen sales are not real lift). "
        "breakeven_lift_pct = unit lift needed just to break even at this discount; null means the "
        "discount exceeds the margin, so no lift can break even. revenue_change_pct = revenue vs. baseline. "
        "net_incremental_profit = incremental_profit + cannibalization_profit (profit change of other "
        "products in the same category). safe_discount_pct = deepest discount whose breakeven, with a "
        "1.5x safety margin, is covered by the observed lift; null means stop discounting. "
        "Money values are US dollars.\n"
        f"Set promo_id to {row['promo_id']}. Headline format, at most 15 words: revenue change as a "
        "percentage and profit change in dollars, e.g. 'Sales up 32%, but profit down $417'. "
        f"Explain why the verdict is '{row['verdict']}'. Give 1-3 root causes and 1-3 concrete actions. "
        "suggested_discount_pct must equal safe_discount_pct as a fraction (10% -> 0.10), or null."
    )


def _next_prompt(candidates: pd.DataFrame) -> str:
    rows = [_facts(r, CANDIDATE_FIELDS) for r in candidates.to_dict("records")]
    return (
        "Recommend which of these products should get the next 14-day promotion. "
        "Return one rec per product, best first.\n"
        f"Candidates (JSON): {json.dumps(rows)}\n"
        "category_avg_lift is the category's average net lift (excluding sales stolen from sibling products). "
        "suggested_discount_pct was computed so the category's typical net lift clears breakeven with a "
        "1.5x safety margin; null means no discount is safe. Return it as a fraction (15% -> 0.15); "
        "keep it or lower it, never raise it. Base expected_impact on projected_incremental_profit (US dollars)."
    )


def _promo_row(promo_id: str) -> dict:
    df = get_leaderboard()
    match = df[df["promo_id"] == promo_id]
    if match.empty:
        raise ValueError(f"Unknown promo_id: {promo_id}")
    return match.iloc[0].to_dict()


def _fixture(name: str):
    path = FIXTURES / name
    return json.loads(path.read_text()) if path.exists() else None


def _fallback_insight(promo_id: str, row: dict) -> PromoInsight:
    stored = (_fixture("insights.json") or {}).get(promo_id)
    if stored:
        return PromoInsight(**{**stored, "source": "fallback"})
    return rule_insight(row)


def _fallback_recs() -> list[NextPromoRec]:
    stored = _fixture("next_recs.json")
    if stored:
        return [NextPromoRec(**{**rec, "source": "fallback"}) for rec in stored]
    return rule_next_recs(get_next_candidates())


def analyze_promo(promo_id: str) -> PromoInsight:
    row = _promo_row(promo_id)
    if get_settings().use_fixtures:
        return _fallback_insight(promo_id, row)
    if promo_id in _insight_cache:
        return _insight_cache[promo_id]
    try:
        body = _generate(_promo_prompt(row), PromoInsightBody)
        insight = PromoInsight(**{**body.model_dump(), "promo_id": promo_id, "source": "gemini"})
    except Exception:
        log.warning("Gemini analysis failed for %s; using fallback", promo_id, exc_info=True)
        return _fallback_insight(promo_id, row)
    _insight_cache[promo_id] = insight
    return insight


def recommend_next() -> list[NextPromoRec]:
    if get_settings().use_fixtures:
        return _fallback_recs()
    if "recs" in _recs_cache:
        return _recs_cache["recs"]
    candidates = get_next_candidates().head(5)
    try:
        body = _generate(_next_prompt(candidates), NextRecsBody)
        known = set(candidates["product_id"])
        recs = [NextPromoRec(**r.model_dump(), source="gemini") for r in body.recs if r.product_id in known]
        if not recs:
            raise ValueError("Gemini returned no known products")
    except Exception:
        log.warning("Gemini next-promo recommendation failed; using fallback", exc_info=True)
        return _fallback_recs()
    _recs_cache["recs"] = recs
    return recs
