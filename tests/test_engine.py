
"""Tests for rule evaluation, action generation, and suppression."""

import pytest

from src.engine import RulesEngine, load_rules
from src.expressions import MissingFieldError, evaluate_condition


RULES = load_rules("rules/rules.json")


def make_patient(**overrides):
    """Create a baseline patient with optional field overrides."""
    patient = {
        "id": "P001",
        "age": 72,
        "conditions": ["diabetes", "hypertension"],
        "smoker": True,
        "riskLevel": "medium",
        "lastVisitDaysAgo": 45,
        "bloodPressure": {"systolic": 155, "diastolic": 92},
        "completedTasks": ["blood_test"],
    }
    patient.update(overrides)
    return patient


def test_follow_up_after_30_days():
    """A follow-up should be recommended after 30 days."""
    engine = RulesEngine(RULES)

    actions, suppressed, missing = engine.evaluate_patient(
        make_patient(lastVisitDaysAgo=45)
    )

    assert "follow_up_visit" in {
        action["type"] for action in actions
    }
    assert missing == []


def test_no_follow_up_within_30_days():
    """A recent visit should not trigger a follow-up."""
    engine = RulesEngine(RULES)

    actions, _, _ = engine.evaluate_patient(
        make_patient(lastVisitDaysAgo=10)
    )

    assert "follow_up_visit" not in {
        action["type"] for action in actions
    }


def test_follow_up_at_exactly_30_days():
    """The follow-up threshold is strictly greater than 30 days."""
    engine = RulesEngine(RULES)

    actions, _, _ = engine.evaluate_patient(
        make_patient(lastVisitDaysAgo=30)
    )

    assert "follow_up_visit" not in {
        action["type"] for action in actions
    }


def test_completed_action_is_suppressed():
    """Completed tasks should suppress matching recommendations."""
    engine = RulesEngine(RULES)

    actions, suppressed, missing = engine.evaluate_patient(
        make_patient()
    )

    assert "blood_test" not in {
        action["type"] for action in actions
    }

    suppressed_blood_test = next(
        action
        for action in suppressed
        if action["type"] == "blood_test"
    )

    assert suppressed_blood_test["suppressedBy"] == "R005"
    assert missing == []


def test_missing_field_is_reported():
    """Missing patient attributes should be reported by the engine."""
    engine = RulesEngine(RULES)

    patient = make_patient()
    patient.pop("lastVisitDaysAgo")

    _, _, missing = engine.evaluate_patient(patient)

    assert any(
        item["rule"] == "R004"
        and item["field"] == "lastVisitDaysAgo"
        for item in missing
    )


def test_missing_nested_field():
    """Unavailable nested attributes should raise MissingFieldError."""
    condition = {
        "field": "bloodPressure.systolic",
        "operator": ">",
        "value": 140,
    }

    with pytest.raises(MissingFieldError) as error:
        evaluate_condition(
            {"bloodPressure": None},
            condition,
        )

    assert error.value.fields == ["bloodPressure.systolic"]


def test_duplicate_actions_merge_with_highest_priority():
    """Duplicate actions should merge and retain the highest priority."""
    rules = [
        {
            "id": "A",
            "name": "Follow-up based on age",
            "ruleType": "generation",
            "condition": {
                "field": "age",
                "operator": ">=",
                "value": 65,
            },
            "action": {
                "type": "follow_up_visit",
                "priority": "LOW",
            },
            "reason": "Reason A",
        },
        {
            "id": "B",
            "name": "Follow-up based on smoking",
            "ruleType": "generation",
            "condition": {
                "field": "smoker",
                "operator": "==",
                "value": True,
            },
            "action": {
                "type": "follow_up_visit",
                "priority": "HIGH",
            },
            "reason": "Reason B",
        },
    ]

    engine = RulesEngine(rules)

    actions, suppressed, missing = engine.evaluate_patient(
        make_patient()
    )

    assert len(actions) == 1
    assert actions[0]["type"] == "follow_up_visit"
    assert actions[0]["priority"] == "HIGH"
    assert actions[0]["rules"] == ["A", "B"]
    assert actions[0]["reasons"] == ["Reason A", "Reason B"]
    assert suppressed == []
    assert missing == []


def test_no_applicable_rules():
    """No recommendations should be generated when no rules match."""
    engine = RulesEngine(RULES)

    actions, suppressed, missing = engine.evaluate_patient(
        make_patient(
            age=30,
            conditions=[],
            smoker=False,
            lastVisitDaysAgo=5,
            bloodPressure={"systolic": 120, "diastolic": 80},
            completedTasks=[],
        )
    )

    assert actions == []
    assert suppressed == []
    assert missing == []


def test_logical_and():
    """AND should match when all child conditions are true."""
    condition = {
        "operator": "and",
        "conditions": [
            {"field": "age", "operator": ">=", "value": 65},
            {"field": "smoker", "operator": "==", "value": True},
        ],
    }

    assert evaluate_condition(make_patient(), condition) is True


def test_logical_or():
    """OR should match when at least one child condition is true."""
    condition = {
        "operator": "or",
        "conditions": [
            {"field": "age", "operator": "<", "value": 65},
            {"field": "smoker", "operator": "==", "value": True},
        ],
    }

    assert evaluate_condition(make_patient(), condition) is True


def test_logical_not():
    """NOT should invert the result of its child condition."""
    condition = {
        "operator": "not",
        "conditions": [
            {"field": "smoker", "operator": "==", "value": False}
        ],
    }

    assert evaluate_condition(make_patient(), condition) is True


def test_unknown_operator():
    """Evaluation should reject unsupported operators."""
    condition = {
        "field": "age",
        "operator": "approximately",
        "value": 65,
    }

    with pytest.raises(ValueError, match="Unknown operator"):
        evaluate_condition(make_patient(), condition)


def test_suppression_is_generic():
    """Suppression should work for any completed action type."""
    engine = RulesEngine(RULES)

    actions, suppressed, _ = engine.evaluate_patient(
        make_patient(
            completedTasks=[
                "blood_test",
                "geriatric_assessment",
                "follow_up_visit",
            ]
        )
    )

    recommended_types = {action["type"] for action in actions}
    suppressed_types = {action["type"] for action in suppressed}

    assert "blood_test" not in recommended_types
    assert "geriatric_assessment" not in recommended_types
    assert "follow_up_visit" not in recommended_types

    assert {
        "blood_test",
        "geriatric_assessment",
        "follow_up_visit",
    }.issubset(suppressed_types)
