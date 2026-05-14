from __future__ import annotations

from datetime import date, timedelta

from app.domain.entities import Goal, GoalStatus


def _goal(**overrides) -> Goal:
    defaults = dict(
        id=1, name="Test", target_amount=1000, current_amount=0,
        target_date=None, status="active", account_id=1,
    )
    defaults.update(overrides)
    return Goal(**defaults)


# --- progress_percent ---

def test_progress_percent_zero():
    assert _goal(current_amount=0, target_amount=1000).progress_percent == 0.0


def test_progress_percent_partial():
    assert _goal(current_amount=250, target_amount=1000).progress_percent == 25.0


def test_progress_percent_full():
    assert _goal(current_amount=1000, target_amount=1000).progress_percent == 100.0


def test_progress_percent_over():
    assert _goal(current_amount=1200, target_amount=1000).progress_percent == 120.0


def test_progress_percent_target_zero():
    assert _goal(current_amount=0, target_amount=0).progress_percent == 100.0


def test_progress_percent_rounds_to_two_decimals():
    assert _goal(current_amount=1, target_amount=3).progress_percent == 33.33


# --- effective_status: completed ---

def test_effective_status_completed_when_current_equals_target():
    goal = _goal(current_amount=1000, target_amount=1000)
    assert goal.effective_status == GoalStatus.COMPLETED


def test_effective_status_completed_when_current_exceeds_target():
    goal = _goal(current_amount=1500, target_amount=1000)
    assert goal.effective_status == GoalStatus.COMPLETED


def test_effective_status_completed_overrides_expired_date():
    goal = _goal(
        current_amount=1000, target_amount=1000,
        target_date=date.today() - timedelta(days=30),
    )
    assert goal.effective_status == GoalStatus.COMPLETED


# --- effective_status: expired ---

def test_effective_status_expired_when_past_date_and_not_completed():
    goal = _goal(
        current_amount=500, target_amount=1000,
        target_date=date.today() - timedelta(days=1),
    )
    assert goal.effective_status == GoalStatus.EXPIRED


def test_effective_status_not_expired_when_date_is_today():
    goal = _goal(
        current_amount=500, target_amount=1000,
        target_date=date.today(),
    )
    assert goal.effective_status == GoalStatus.ACTIVE


def test_effective_status_not_expired_when_date_is_future():
    goal = _goal(
        current_amount=500, target_amount=1000,
        target_date=date.today() + timedelta(days=1),
    )
    assert goal.effective_status == GoalStatus.ACTIVE


# --- effective_status: paused ---

def test_effective_status_paused_preserved():
    goal = _goal(status="paused")
    assert goal.effective_status == GoalStatus.PAUSED


def test_effective_status_paused_even_when_date_expired():
    goal = _goal(
        status="paused",
        target_date=date.today() - timedelta(days=10),
    )
    assert goal.effective_status == GoalStatus.PAUSED


def test_effective_status_completed_overrides_paused():
    goal = _goal(
        status="paused",
        current_amount=1000, target_amount=1000,
    )
    assert goal.effective_status == GoalStatus.COMPLETED


# --- effective_status: active ---

def test_effective_status_active_default():
    goal = _goal()
    assert goal.effective_status == GoalStatus.ACTIVE


def test_effective_status_active_with_no_date():
    goal = _goal(target_date=None, current_amount=500, target_amount=1000)
    assert goal.effective_status == GoalStatus.ACTIVE


def test_effective_status_active_with_none_status():
    goal = _goal(status=None)
    assert goal.effective_status == GoalStatus.ACTIVE


# --- effective_status: target_amount zero edge case ---

def test_effective_status_active_when_target_zero_and_current_zero():
    goal = _goal(target_amount=0, current_amount=0)
    assert goal.effective_status == GoalStatus.ACTIVE
