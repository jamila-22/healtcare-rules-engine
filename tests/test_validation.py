
"""Tests for rule structure validation and invalid configurations."""

import copy

import pytest

from src.engine import RulesEngine, load_rules
from src.validation import (
    RuleValidationError,
    validate_condition,
    validate_rules,
)


def test_existing_rules_are_valid():
    """The configured rule set should pass validation."""
    rules = load_rules("rules/rules.json")

    validate_rules(rules)


def test_duplicate_rule_ids():
    """Rule identifiers must be unique."""
    rules = load_rules("rules/rules.json")

    # Any rule type can have a duplicate ID.
    duplicate = copy.deepcopy(rules[0])
    rules.append(duplicate)

    with pytest.raises(
        RuleValidationError,
        match="Duplicate rule ID",
    ):
        validate_rules(rules)


def test_unknown_operator():
    """Unsupported comparison operators should be rejected."""
    condition = {
        "field": "age",
        "operator": "greaterThan",
        "value": 65,
    }

    with pytest.raises(
        RuleValidationError,
        match="Unknown operator",
    ):
        validate_condition(condition)


def test_invalid_priority():
    """Generation actions must use a supported priority."""
    rules = load_rules("rules/rules.json")

    generation = next(
        rule for rule in rules
        if rule["ruleType"] == "generation"
    )
    generation["action"]["priority"] = "URGENT"

    with pytest.raises(
        RuleValidationError,
        match="invalid priority",
    ):
        validate_rules(rules)


def test_missing_action():
    """Generation rules must define an action."""
    rules = load_rules("rules/rules.json")

    generation = next(
        rule for rule in rules
        if rule["ruleType"] == "generation"
    )
    generation.pop("action")

    with pytest.raises(
        RuleValidationError,
        match="require an action",
    ):
        validate_rules(rules)


def test_comparison_requires_value():
    """Comparison conditions must specify a value source."""
    condition = {
        "field": "age",
        "operator": ">=",
    }

    with pytest.raises(
        RuleValidationError,
        match="exactly one",
    ):
        validate_condition(condition)


def test_comparison_cannot_have_both_values():
    """A comparison cannot define both value and valueFrom."""
    condition = {
        "field": "age",
        "operator": ">=",
        "value": 65,
        "valueFrom": "action.type",
    }

    with pytest.raises(
        RuleValidationError,
        match="exactly one",
    ):
        validate_condition(condition)


def test_and_requires_conditions():
    """AND conditions must contain at least one child condition."""
    condition = {
        "operator": "and",
        "conditions": [],
    }

    with pytest.raises(
        RuleValidationError,
        match="non-empty",
    ):
        validate_condition(condition)


def test_not_requires_exactly_one_condition():
    """NOT must operate on exactly one condition."""
    condition = {
        "operator": "not",
        "conditions": [
            {"field": "smoker", "operator": "==", "value": True},
            {"field": "age", "operator": ">=", "value": 65},
        ],
    }

    with pytest.raises(
        RuleValidationError,
        match="exactly one",
    ):
        validate_condition(condition)


def test_invalid_nested_condition():
    """Validation must also inspect nested conditions."""
    condition = {
        "operator": "and",
        "conditions": [
            {"field": "age", "operator": ">=", "value": 65},
            {"field": "smoker", "operator": "invalid", "value": True},
        ],
    }

    with pytest.raises(
        RuleValidationError,
        match="Unknown operator",
    ):
        validate_condition(condition)


def test_suppression_cannot_define_action():
    """Suppression rules must not define a generation action."""
    rules = load_rules("rules/rules.json")

    suppression = next(
        rule for rule in rules
        if rule["ruleType"] == "suppression"
    )

    suppression["action"] = {
        "type": "blood_test",
        "priority": "LOW",
    }

    with pytest.raises(
        RuleValidationError,
        match="must not define an action",
    ):
        validate_rules(rules)


def test_engine_rejects_invalid_rules():
    """The engine must validate rules during initialization."""
    rules = load_rules("rules/rules.json")

    generation = next(
        rule for rule in rules
        if rule["ruleType"] == "generation"
    )
    generation["action"]["priority"] = "URGENT"

    with pytest.raises(RuleValidationError):
        RulesEngine(rules)
