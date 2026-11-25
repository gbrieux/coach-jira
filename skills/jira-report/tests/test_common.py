"""Helpers partagés (indicators/common.py, indicators/defaults.py)."""
from indicators.common import month_range
from indicators.defaults import MIN_TRANSITION_SECONDS, min_transition_seconds


def test_month_range_wraps_year():
    assert month_range((2025, 11), (2026, 2)) == [
        (2025, 11), (2025, 12), (2026, 1), (2026, 2)
    ]


def test_min_transition_seconds_default_and_override():
    assert min_transition_seconds({}) == MIN_TRANSITION_SECONDS
    assert min_transition_seconds({"dispersion_etapes": None}) == MIN_TRANSITION_SECONDS
    assert min_transition_seconds({"dispersion_etapes": {"min_transition_seconds": 1}}) == 1
