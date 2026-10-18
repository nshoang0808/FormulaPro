import json
from pathlib import Path

import pandas as pd
import pytest

from promo_intel import ai
from promo_intel.schemas import Action, NextPromoRecBody, NextRecsBody, PromoInsightBody

FIXTURES = Path(ai.__file__).parent / "fixtures"
ROW = next(r for r in json.loads((FIXTURES / "leaderboard.json").read_text()) if r["promo_id"] == "PR01")
CANDIDATES = pd.DataFrame(json.loads((FIXTURES / "candidates.json").read_text()))


@pytest.fixture(autouse=True)
def live_mode(monkeypatch):
    monkeypatch.setenv("USE_FIXTURES", "0")
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    monkeypatch.setattr(ai, "_promo_row", lambda promo_id: ROW)
    monkeypatch.setattr(ai, "get_next_candidates", lambda: CANDIDATES)
    ai._insight_cache.clear()
    ai._recs_cache.clear()


def _body() -> PromoInsightBody:
    return PromoInsightBody(
        promo_id="PR01", headline="Sales up 30%, profit down $433", explanation="x",
        root_causes=["y"], suggested_discount_pct=0.10,
        actions=[Action(action="Cut to 10%", type="reduce_discount", expected_impact="+$200", confidence="high")],
    )


def test_gemini_result_is_returned_and_cached(monkeypatch):
    prompts = []

    def fake_generate(prompt, schema):
        prompts.append(prompt)
        return _body()

    monkeypatch.setattr(ai, "_generate", fake_generate)
    first = ai.analyze_promo("PR01")
    second = ai.analyze_promo("PR01")
    assert first.source == "gemini"
    assert first is second
    assert len(prompts) == 1
    assert "Margin Trap" in prompts[0]


def test_prompt_formats_percentages_and_grounds_the_discount():
    prompt = ai._promo_prompt(ROW)
    assert '"breakeven_lift_pct": "600%"' in prompt
    assert '"discount_pct": "30%"' in prompt
    assert '"safe_discount_pct": "10%"' in prompt
    assert '"revenue_change_pct": "+' in prompt


def test_exception_falls_back(monkeypatch):
    def boom(prompt, schema):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(ai, "_generate", boom)
    assert ai.analyze_promo("PR01").source == "fallback"


def test_invalid_json_falls_back(monkeypatch):
    class FakeModels:
        def generate_content(self, **kwargs):
            return type("Response", (), {"text": "not json"})()

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr(ai, "_genai_client", lambda: FakeClient())
    assert ai.analyze_promo("PR01").source == "fallback"


def test_recommend_next_keeps_only_known_products(monkeypatch):
    known = CANDIDATES.iloc[0]
    body = NextRecsBody(recs=[
        NextPromoRecBody(product_id=known.product_id, product_name=known.product_name,
                         suggested_discount_pct=None, rationale="r", expected_impact="e", confidence="low"),
        NextPromoRecBody(product_id="ZZZ", product_name="Ghost", suggested_discount_pct=None,
                         rationale="r", expected_impact="e", confidence="low"),
    ])
    monkeypatch.setattr(ai, "_generate", lambda prompt, schema: body)
    recs = ai.recommend_next()
    assert [r.product_id for r in recs] == [known.product_id]
    assert recs[0].source == "gemini"


def test_recommend_next_falls_back_on_error(monkeypatch):
    def boom(prompt, schema):
        raise TimeoutError()

    monkeypatch.setattr(ai, "_generate", boom)
    recs = ai.recommend_next()
    assert recs and all(r.source == "fallback" for r in recs)
