import pytest

import promo_intel as pi
from promo_intel.data import CANDIDATE_COLUMNS, KPI_KEYS, LEADERBOARD_COLUMNS, TIMESERIES_COLUMNS

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def live_mode(monkeypatch):
    monkeypatch.setenv("USE_FIXTURES", "0")


def test_live_functions_match_contract():
    assert list(pi.get_leaderboard().columns) == LEADERBOARD_COLUMNS
    assert list(pi.get_promo_timeseries("PR01").columns) == TIMESERIES_COLUMNS
    assert list(pi.get_next_candidates().columns) == CANDIDATE_COLUMNS
    assert list(pi.get_kpis()) == KPI_KEYS
