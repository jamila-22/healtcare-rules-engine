
"""Evaluate logical and comparison conditions defined in JSON rules."""

import operator


class MissingFieldError(Exception):
    """Raised when one or more required fields are unavailable."""

    def __init__(self, fields):
        if isinstance(fields, str):
            fields = [fields]

        self.fields = list(dict.fromkeys(fields))

        super().__init__(
            f"Missing fields: {', '.join(self.fields)}"
        )


COMPARISON_OPERATORS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
    "contains": operator.contains,
}


def evaluate_logical(operator_name, children, context):
    """Evaluate AND, OR, or NOT while tracking unavailable fields."""
    results = []
    missing_fields = []

    # Evaluate every child to collect all relevant missing fields.
    for child in children:
        try:
            results.append(
                evaluate_expression(child, context)
            )
        except MissingFieldError as error:
            results.append(None)
            missing_fields.extend(error.fields)

    # A false condition determines AND, even if other fields are missing.
    if operator_name == "and":
        if False in results:
            return False

        if missing_fields:
            raise MissingFieldError(missing_fields)

        return True

    # A true condition determines OR, even if other fields are missing.
    if operator_name == "or":
        if True in results:
            return True

        if missing_fields:
            raise MissingFieldError(missing_fields)

        return False

    # NOT has exactly one child, so unavailable data remains unresolved.
    if missing_fields:
        raise MissingFieldError(missing_fields)

    return not results[0]


def get_field_value(data, field):
    """Retrieve a nested value using dot notation."""
    value = data

    for key in field.split("."):
        if not isinstance(value, dict) or key not in value:
            raise MissingFieldError(field)

        value = value[key]

        # Explicit null values are treated as unavailable data.
        if value is None:
            raise MissingFieldError(field)

    return value


def evaluate_condition(
    patient,
    condition,
    action=None,
):
    """Evaluate a rule condition against patient and optional action data."""
    context = {
        "patient": patient,
        "action": action,
    }

    return evaluate_expression(condition, context)


def evaluate_expression(expression, context):
    """Recursively evaluate a logical or comparison expression."""
    operator_name = expression["operator"]

    # Logical expressions may contain nested conditions.
    if operator_name in ("and", "or", "not"):
        children = expression["conditions"]

        if not children:
            raise ValueError(
                f"'{operator_name}' requires conditions"
            )

        if operator_name == "not" and len(children) != 1:
            raise ValueError(
                "'not' requires exactly one condition"
            )

        return evaluate_logical(
            operator_name, children, context
        )

    if operator_name not in COMPARISON_OPERATORS:
        raise ValueError(
            f"Unknown operator: {operator_name}"
        )

    actual = get_field_value(
        context["patient"],
        expression["field"],
    )

    # valueFrom allows comparisons against dynamically resolved values,
    # such as the type of an action being evaluated for suppression.
    if "valueFrom" in expression:
        expected = get_field_value(
            context,
            expression["valueFrom"],
        )
    else:
        expected = expression["value"]

    comparison = COMPARISON_OPERATORS[operator_name]

    return comparison(actual, expected)
