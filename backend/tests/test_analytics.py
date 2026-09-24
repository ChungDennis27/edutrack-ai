"""Weak-topic analytics maths tests (no DB required)."""
from app.services.analytics import AnalyticsService


def test_mastery_percent_basic():
    assert AnalyticsService.compute_mastery_percent(8, 10) == 80.0


def test_mastery_percent_zero_total():
    assert AnalyticsService.compute_mastery_percent(0, 0) == 0.0


def test_mastery_percent_slow_penalty():
    # 100% base, 2 of 10 slow-but-correct -> -15 * 2/10 = -3
    assert AnalyticsService.compute_mastery_percent(10, 10, slow_correct=2) == 97.0


def test_mastery_percent_never_negative():
    assert AnalyticsService.compute_mastery_percent(1, 10, slow_correct=10) >= 0.0


def test_flag_slow_answers():
    assert AnalyticsService.flag_slow_answers(130, True) is True
    assert AnalyticsService.flag_slow_answers(130, False) is False
    assert AnalyticsService.flag_slow_answers(60, True) is False
