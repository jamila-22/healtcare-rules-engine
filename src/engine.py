
"""Evaluate patient data against generation and suppression rules."""

import json

from src.validation import validate_rules
from src.expressions import (
    MissingFieldError,
    evaluate_condition,
)


PRIORITIES = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


class RulesEngine:
    """Generate, merge, and suppress actions based on configured rules."""

    def __init__(self, rules):
        """Validate rules and separate them by evaluation phase."""
        validate_rules(rules)

        self.generation_rules = []
        self.suppression_rules = []

        for rule in rules:
            rule_type = rule["ruleType"]

            if rule_type == "generation":
                self.generation_rules.append(rule)

            elif rule_type == "suppression":
                self.suppression_rules.append(rule)

    def evaluate_patient(self, patient):
        """Return recommended actions, suppressed actions, and missing data."""
        actions_by_type = {}
        missing_data = []

        # Phase 1: Evaluate generation rules and merge actions by type.
        for rule in self.generation_rules:
            try:
                matches = evaluate_condition(
                    patient,
                    rule["condition"],
                )

            except MissingFieldError as error:
                # Report every field preventing this rule from being evaluated.
                for field in error.fields:
                    missing_data.append({
                        "rule": rule["id"],
                        "field": field,
                        "priority": rule["action"]["priority"],
                    })
                continue

            if not matches:
                continue

            action_definition = rule["action"]
            action_type = action_definition["type"]
            priority = action_definition["priority"]

            if action_type not in actions_by_type:
                actions_by_type[action_type] = {
                    "type": action_type,
                    "priority": priority,
                    "rules": [rule["id"]],
                    "reasons": [rule["reason"]],
                }
                continue

            # Merge recommendations for the same action, preserving
            # all triggering rules and their explanations.
            existing = actions_by_type[action_type]

            existing["rules"].append(rule["id"])
            existing["reasons"].append(rule["reason"])

            # Use the highest priority among the generating rules.
            if (
                PRIORITIES[priority]
                > PRIORITIES[existing["priority"]]
            ):
                existing["priority"] = priority

        # Phase 2: Apply suppression rules to generated actions.
        recommended_actions = []
        suppressed_actions = []

        for action in actions_by_type.values():
            suppression = self._find_suppression(
                patient,
                action,
                missing_data,
            )

            if suppression is None:
                recommended_actions.append(action)

            else:
                suppressed_actions.append({
                    **action,
                    "suppressedBy": suppression["id"],
                    "suppressionReason": suppression["reason"],
                })

        # Phase 3: Sort actions from highest to lowest priority.
        def priority_key(action):
            return PRIORITIES[action["priority"]]

        recommended_actions.sort(
            key=priority_key,
            reverse=True,
        )

        suppressed_actions.sort(
            key=priority_key,
            reverse=True,
        )

        return (
            recommended_actions,
            suppressed_actions,
            missing_data,
        )

    def _find_suppression(
        self,
        patient,
        action,
        missing_data,
    ):
        """Return the first matching suppression rule for an action."""
        for rule in self.suppression_rules:
            try:
                matches = evaluate_condition(
                    patient,
                    rule["condition"],
                    action=action,
                )

            except MissingFieldError as error:
                # Keep missing-data reports associated with the action.
                for field in error.fields:
                    missing_data.append({
                        "rule": rule["id"],
                        "field": field,
                        "action": action["type"],
                    })
                continue

            if matches:
                return rule

        return None


def explain_results(actions, missing_data):
    """Summarize the evaluation outcome for display in the UI."""
    if missing_data:
        return {
            "status": "incomplete",
            "message": (
                "Some rules could not be evaluated "
                "due to missing data."
            ),
        }

    if actions:
        return {
            "status": "actions_required",
            "message": "One or more actions are recommended.",
        }

    return {
        "status": "no_actions",
        "message": (
            "No actions recommended based "
            "on the configured rules."
        ),
    }


def load_rules(file_path):
    """Load rule definitions from a JSON file."""
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)
