from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app.py"
pytestmark = pytest.mark.skipif(not APP.exists(), reason="app.py is built by Gemini Flash")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("USE_FIXTURES", "1")
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(APP), default_timeout=30).run()


def test_app_renders_kpis_and_leaderboard(app):
    assert not app.exception
    assert len(app.metric) >= 5
    assert len(app.dataframe) >= 1


def test_default_promo_is_margin_trap(app):
    assert app.selectbox(key="promo_select").value == "PR01"


def test_analyze_and_recommend_buttons(app):
    app.button(key="analyze_btn").click().run()
    assert not app.exception
    app.button(key="recommend_btn").click().run()
    assert not app.exception
