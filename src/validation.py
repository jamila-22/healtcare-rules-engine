
"""Validate the structure and configuration of JSON rules."""

from src.expressions import COMPARISON_OPERATORS


VALID_RULE_TYPES = {"generation", "suppression"}
VALID_PRIORITIES = {"LOW", "MEDIUM", "HIGH"}
LOGICAL_OPERATORS = {"and", "or", "not"}


class RuleValidationError(ValueError):
    """Raised when a rule configuration is invalid."""


def validate_condition(condition):
    """Recursively validate logical and comparison conditions."""

    if not isinstance(condition, dict):
        raise RuleValidationError(
            "Condition must be an object."
        )

    operator = condition.get("operator")

    # Logical operators require nested conditions.
    if operator in LOGICAL_OPERATORS:
        children = condition.get("conditions")

        if not isinstance(children, list) or not children:
            raise RuleValidationError(
                f"'{operator}' requires a non-empty conditions list."
            )

        if operator == "not" and len(children) != 1:
            raise RuleValidationError(
                "'not' requires exactly one condition."
            )

        for child in children:
            validate_condition(child)

        return

    # Comparison operators must be supported by the evaluator.
    if operator not in COMPARISON_OPERATORS:
        raise RuleValidationError(
            f"Unknown operator: {operator}"
        )

    field = condition.get("field")

    if not isinstance(field, str) or not field.strip():
        raise RuleValidationError(
            "Comparison condition requires a valid field."
        )

    # A comparison uses either a literal value or a dynamic reference.
    has_value = "value" in condition
    has_value_from = "valueFrom" in condition

    if has_value == has_value_from:
        raise RuleValidationError(
            "Comparison condition must specify exactly "
            "one of 'value' or 'valueFrom'."
        )

    if has_value_from:
        value_from = condition["valueFrom"]

        if (
            not isinstance(value_from, str)
            or not value_from.strip()
        ):
            raise RuleValidationError(
                "'valueFrom' must be a non-empty string."
            )


def validate_rules(rules):
    """Validate rule definitions, identifiers, and required properties."""

    if not isinstance(rules, list):
        raise RuleValidationError(
            "Rules configuration must be a list."
        )

    seen_ids = set()

    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise RuleValidationError(
                f"Rule at index {index} must be an object."
            )

        rule_id = rule.get("id")

        if not isinstance(rule_id, str) or not rule_id.strip():
            raise RuleValidationError(
                f"Rule at index {index} requires a valid ID."
            )

        # Rule identifiers must be unique across the configuration.
        if rule_id in seen_ids:
            raise RuleValidationError(
                f"Duplicate rule ID: {rule_id}"
            )

        seen_ids.add(rule_id)

        rule_type = rule.get("ruleType")

        if rule_type not in VALID_RULE_TYPES:
            raise RuleValidationError(
                f"Rule {rule_id}: invalid rule type: {rule_type}"
            )

        name = rule.get("name")

        if not isinstance(name, str) or not name.strip():
            raise RuleValidationError(
                f"Rule {rule_id}: name is required."
            )

        reason = rule.get("reason")

        if not isinstance(reason, str) or not reason.strip():
            raise RuleValidationError(
                f"Rule {rule_id}: reason is required."
            )

        if "condition" not in rule:
            raise RuleValidationError(
                f"Rule {rule_id}: condition is required."
            )

        # Include the rule ID when reporting nested condition errors.
        try:
            validate_condition(rule["condition"])
        except RuleValidationError as error:
            raise RuleValidationError(
                f"Rule {rule_id}: {error}"
            ) from error

        if rule_type == "generation":
            # Generation rules must define an action and its priority.
            action = rule.get("action")

            if not isinstance(action, dict):
                raise RuleValidationError(
                    f"Rule {rule_id}: generation rules "
                    "require an action."
                )

            action_type = action.get("type")

            if (
                not isinstance(action_type, str)
                or not action_type.strip()
            ):
                raise RuleValidationError(
                    f"Rule {rule_id}: action type is required."
                )

            priority = action.get("priority")

            if priority not in VALID_PRIORITIES:
                raise RuleValidationError(
                    f"Rule {rule_id}: invalid priority: {priority}"
                )

        elif "action" in rule:
            # Suppression rules operate on existing actions.
            raise RuleValidationError(
                f"Rule {rule_id}: suppression rules "
                "must not define an action."
            )
