
"""Tests for missing data handling and logical condition evaluation."""

import pytest

from src.engine import RulesEngine, load_rules
from src.expressions import (
    MissingFieldError,
    evaluate_condition,
)


AGE = {
    "field": "age",
    "operator": ">=",
    "value": 65,
}

SMOKER = {
    "field": "smoker",
    "operator": "==",
    "value": True,
}


@pytest.mark.parametrize(
    "conditions",
    [
        [AGE, SMOKER],
        [SMOKER, AGE],
    ],
)
def test_and_false_overrides_missing(conditions):
    """AND returns False if a condition is false, despite missing data."""
    expression = {
        "operator": "and",
        "conditions": conditions,
    }

    assert evaluate_condition(
        {"smoker": False}, expression
    ) is False


@pytest.mark.parametrize(
    "conditions",
    [
        [AGE, SMOKER],
        [SMOKER, AGE],
    ],
)
def test_or_true_overrides_missing(conditions):
    """OR returns True if a condition is true, despite missing data."""
    expression = {
        "operator": "or",
        "conditions": conditions,
    }

    assert evaluate_condition(
        {"smoker": True}, expression
    ) is True


def test_and_with_unresolved_missing_data():
    """AND raises an error if missing data prevents a definite result."""
    expression = {
        "operator": "and",
        "conditions": [AGE, SMOKER],
    }

    with pytest.raises(MissingFieldError):
        evaluate_condition(
            {"smoker": True}, expression
        )


def test_or_with_unresolved_missing_data():
    """OR raises an error if missing data prevents a definite result."""
    expression = {
        "operator": "or",
        "conditions": [AGE, SMOKER],
    }

    with pytest.raises(MissingFieldError):
        evaluate_condition(
            {"smoker": False}, expression
        )


def test_not_with_missing_data():
    """NOT propagates missing data from its child condition."""
    expression = {
        "operator": "not",
        "conditions": [AGE],
    }

    with pytest.raises(MissingFieldError):
        evaluate_condition({}, expression)


def test_null_value_is_missing():
    """Explicit null values are treated as unavailable data."""
    with pytest.raises(MissingFieldError):
        evaluate_condition(
            {"age": None}, AGE
        )


def test_follow_up_threshold():
    """A follow-up is not triggered at exactly 30 days."""
    rules = load_rules("rules/rules.json")
    engine = RulesEngine(rules)

    patient = {
        "age": 40,
        "conditions": [],
        "smoker": False,
        "lastVisitDaysAgo": 30,
        "completedTasks": [],
    }

    actions, _, _ = engine.evaluate_patient(patient)

    assert not any(
        action["type"] == "follow_up_visit"
        for action in actions
    )


def test_missing_completed_tasks_is_reported():
    """Missing suppression data is reported without removing the action."""
    rules = [
        {
            "id": "R1",
            "name": "Age assessment",
            "ruleType": "generation",
            "condition": AGE,
            "action": {
                "type": "geriatric_assessment",
                "priority": "MEDIUM",
            },
            "reason": "Patient is at least 65",
        },
        {
            "id": "R2",
            "name": "Suppress completed tasks",
            "ruleType": "suppression",
            "condition": {
                "field": "completedTasks",
                "operator": "contains",
                "valueFrom": "action.type",
            },
            "reason": "Task already completed",
        },
    ]

    engine = RulesEngine(rules)

    actions, suppressed, missing = (
        engine.evaluate_patient({"age": 72})
    )

    assert len(actions) == 1
    assert suppressed == []
    assert missing == [
        {
            "rule": "R2",
            "field": "completedTasks",
            "action": "geriatric_assessment",
        }
    ]
