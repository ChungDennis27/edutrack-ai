"""SM-2 spaced repetition algorithm tests."""
from app.services.flashcard_service import sm2_algorithm


def test_first_correct_response():
    ef, interval, reps = sm2_algorithm(quality=5, ease_factor=2.5, interval=1, repetitions=0)
    assert interval == 1
    assert reps == 1
    assert ef >= 1.3


def test_second_correct_response_uses_six_days():
    ef, interval, reps = sm2_algorithm(quality=4, ease_factor=2.5, interval=1, repetitions=1)
    assert interval == 6
    assert reps == 2


def test_third_correct_multiplies_by_ease_factor():
    ef, interval, reps = sm2_algorithm(quality=5, ease_factor=2.5, interval=6, repetitions=2)
    assert interval == round(6 * 2.5)
    assert reps == 3


def test_incorrect_resets_repetitions():
    ef, interval, reps = sm2_algorithm(quality=2, ease_factor=2.5, interval=6, repetitions=3)
    assert interval == 1
    assert reps == 0


def test_ease_factor_never_below_floor():
    ef, _, _ = sm2_algorithm(quality=0, ease_factor=1.3, interval=1, repetitions=0)
    assert ef >= 1.3
