
"""Streamlit interface for evaluating patients and managing JSON data."""

import json
from pathlib import Path

import streamlit as st

from src.engine import RulesEngine, explain_results, load_rules
from src.validation import RuleValidationError, validate_rules


# ------------------------------------------------------------
# Configuration and examples
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
PATIENTS_DIR = BASE_DIR / "patients"
RULES_PATH = BASE_DIR / "rules" / "rules.json"

PRIORITY_COLORS = {
    "HIGH": "red",
    "MEDIUM": "orange",
    "LOW": "blue",
}

PATIENT_EXAMPLE = {
    "id": "P###",
    "age": 52,
    "conditions": ["anemia", "diabetes"],
    "bloodPressure": {
        "systolic": 185,
        "diastolic": 105,
    },
    "bodyTemperature": None,
    "smoker": False,
    "lastVisitDaysAgo": 10,
    "completedTasks": [],
}


GENERATION_EXAMPLE = {
    "id": "R###",
    "name": "Lifestyle support recommendation",
    "ruleType": "generation",
    "condition": {
        "operator": "or",
        "conditions": [
            {
                "field": "sleepHours",
                "operator": "<",
                "value": 6,
            },
            {
                "field": "exerciseDaysPerWeek",
                "operator": "<",
                "value": 2,
            },
        ],
    },
    "action": {
        "type": "lifestyle_consultation",
        "priority": "LOW",
    },
    "reason": "Insufficient sleep or low physical activity",
}


SUPPRESSION_EXAMPLE = {
    "id": "R###",
    "name": "Completed task suppression",
    "ruleType": "suppression",
    "condition": {
        "field": "completedTasks",
        "operator": "contains",
        "valueFrom": "action.type",
    },
    "reason": "The activity has already been completed",
}


# ------------------------------------------------------------
# Data helpers
# ------------------------------------------------------------

def next_id(existing_ids, prefix):
    """Suggest an unused sequential ID without assigning it."""
    numbers = [
        int(value[len(prefix):])
        for value in existing_ids
        if (
            isinstance(value, str)
            and value.startswith(prefix)
            and value[len(prefix):].isdigit()
        )
    ]

    return f"{prefix}{max(numbers, default=0) + 1:03d}"


def load_patients():
    """Load patient JSON files without enforcing a fixed schema."""
    if not PATIENTS_DIR.exists():
        return {}

    patients = {}

    for path in sorted(PATIENTS_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            patient = json.load(file)

        if not isinstance(patient, dict):
            raise ValueError(
                f"{path.name} must contain a JSON object."
            )

        patients[path.stem] = patient

    return patients


def save_patient(patient):
    """Save a patient using the ID provided in its JSON."""
    if not isinstance(patient, dict):
        raise ValueError("Patient JSON must be an object.")

    patient_id = patient.get("id")
    if (
        not isinstance(patient_id, str)
        or not patient_id.startswith("P")
        or not patient_id[1:].isdigit()
        or len(patient_id) != 4
    ):
        raise ValueError("Patient ID must follow the format P###.")

    PATIENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = PATIENTS_DIR / f"{patient_id}.json"

    # Exclusive creation rejects duplicate IDs without overwriting records.
    try:
        with path.open("x", encoding="utf-8") as file:
            json.dump(patient, file, indent=2)
    except FileExistsError as error:
        raise ValueError(f"Patient ID {patient_id} already exists.") from error

    return patient_id


def save_rule(rule):
    """Validate and save a rule using the ID provided in its JSON."""
    if not isinstance(rule, dict):
        raise ValueError("Rule JSON must be an object.")

    rule_id = rule.get("id")
    if (
        not isinstance(rule_id, str)
        or not rule_id.startswith("R")
        or not rule_id[1:].isdigit()
        or len(rule_id) != 4
    ):
        raise ValueError("Rule ID must follow the format R###.")

    rules = load_rules(RULES_PATH)
    updated_rules = rules + [rule]

    # Validation also rejects duplicate rule IDs.
    validate_rules(updated_rules)

    with RULES_PATH.open("w", encoding="utf-8") as file:
        json.dump(updated_rules, file, indent=2)

    return rule_id


def patient_label(patient_id, patients):
    """Include scenario descriptions in patient selection menus."""
    scenario = patients[patient_id].get("scenario")

    if scenario:
        return f"{patient_id} — {scenario}"

    return patient_id


def patient_data_for_display(patient):
    """Hide demonstration metadata from displayed patient records."""
    return {
        key: value
        for key, value in patient.items()
        if key != "scenario"
    }


# ------------------------------------------------------------
# Presentation helpers
# ------------------------------------------------------------

def format_action_name(action_type):
    """Convert an action identifier into a readable title."""
    return action_type.replace("_", " ").title()


def display_rule_reasons(action):
    """Show the explanation associated with each triggering rule."""
    rules = action.get("rules", [])
    reasons = action.get("reasons", [])

    for rule_id, reason in zip(rules, reasons):
        st.markdown(f"**{rule_id}** — {reason}")


def display_action(action):
    """Display a recommended action and its priority."""
    with st.container(border=True):
        name_column, priority_column = st.columns([4, 1])

        name_column.markdown(
            f"**{format_action_name(action['type'])}**"
        )

        priority_column.badge(
            action["priority"],
            color=PRIORITY_COLORS.get(
                action["priority"], "gray"
            ),
        )

        display_rule_reasons(action)


def display_behavior_guide():
    """Explain how to interpret the evaluation results."""
    with st.expander("❓How to interpret these results"):
        st.markdown(
            """
**Recommended:** Recommended actions for the applied
rules (if applicable), sorted by decreasing priority.
When multiple rules recommend the same action, the engine returns
it only once, keeping the highest generated priority and preserving 
triggering rules and explanations.

**Suppressed:** Suppressed actions for the applied rules.

**Missing data:** Fields that prevent one or more rules from 
being evaluated conclusively.
"""
        )

def display_rules_guide():
    """Explain rule types and supported conditions."""
    with st.expander("❓ About rules"):
        st.markdown(
            """
Rules are defined in JSON and can be of two types:

**Generation rules:** Evaluate patient data and recommend an
action with a priority (HIGH, MEDIUM, or LOW).

**Suppression rules:** Evaluate generated actions and remove
them from recommendations when a suppression condition matches.

**Conditions and operators:**
- Comparison: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`
- Logical: `and`, `or`, `not`
- Nested fields: Access attributes such as `bloodPressure.systolic`
- Nested conditions: Combine logical expressions to create
  more complex conditions.

**Values:** Conditions can compare against a fixed `value`
or use `valueFrom` to reference another field dynamically,
including `action.type` in suppression rules.
"""
        )

def display_missing_data(missing):
    """Group unavailable fields by rule for easier inspection."""
    if not missing:
        st.write("No missing data detected.")
        return

    # Generation and suppression records may contain different metadata.
    groups = {}

    for item in missing:
        key = (
            item["rule"],
            item.get("action"),
        )

        if key not in groups:
            groups[key] = []

        if item["field"] not in groups[key]:
            groups[key].append(item["field"])

    for (rule_id, action_type), fields in groups.items():
        field_names = ", ".join(f"`{field}`" for field in fields)

        message = (
            f"Rule **{rule_id}** could not be fully evaluated. "
            f"Missing fields: {field_names}."
        )

        if action_type is not None:
            message += f" Affected action: `{action_type}`."

        st.warning(message)


# ------------------------------------------------------------
# Application setup
# ------------------------------------------------------------

st.set_page_config(
    page_title="Healthcare Rules Engine",
    layout="wide",
)

st.title("Healthcare Rules Engine")
st.caption(
    "Evaluate patients and manage configurable JSON-based rules."
)

# Apply a newly saved patient selection before creating its widget.
if "pending_patient" in st.session_state:
    st.session_state["selected_patient"] = (
        st.session_state.pop("pending_patient")
    )

if "patient_saved" in st.session_state:
    st.success(
        f"Patient {st.session_state.pop('patient_saved')} saved."
    )

if "rule_saved" in st.session_state:
    st.success(
        f"Rule {st.session_state.pop('rule_saved')} saved."
    )

evaluation_tab, patients_tab, rules_tab = st.tabs(
    ["Evaluation", "Patients", "Rules"]
)


# ------------------------------------------------------------
# Evaluation tab
# ------------------------------------------------------------

with evaluation_tab:
    try:
        patients = load_patients()

    except (OSError, ValueError) as error:
        st.error(f"Could not load patients: {error}")
        patients = {}

    if not patients:
        st.info(
            "No patients available. "
            "Insert a patient in the Patients tab."
        )

    else:
        if st.session_state.get("selected_patient") not in patients:
            st.session_state["selected_patient"] = next(iter(patients))

        selected_id = st.selectbox(
            "Select a patient",
            options=list(patients),
            format_func=lambda pid: patient_label(pid, patients),
            key="selected_patient",
        )

        patient = patients[selected_id]

        st.subheader(f"Patient {selected_id}")
        st.json(
            patient_data_for_display(patient),
            expanded=False,
        )

        try:
            engine = RulesEngine(load_rules(RULES_PATH))

            actions, suppressed, missing = (
                engine.evaluate_patient(patient)
            )

            summary = explain_results(actions, missing)

        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            RuleValidationError,
        ) as error:
            st.error(f"Evaluation failed: {error}")

        else:
            st.divider()
            st.subheader("Evaluation results")

            display_behavior_guide()

            col1, col2, col3 = st.columns(3)

            col1.metric("Recommended", len(actions))
            col2.metric("Suppressed", len(suppressed))
            col3.metric("Missing data", len(missing))

            if summary["status"] == "incomplete":
                st.warning(summary["message"])

            elif summary["status"] == "no_actions":
                st.success(summary["message"])

            else:
                st.info(summary["message"])

            st.subheader("Recommended actions")

            if not actions:
                st.write(
                    "No recommended actions for this patient."
                )

            for action in actions:
                display_action(action)

            with st.expander(
                f"Suppressed actions ({len(suppressed)})"
            ):
                if not suppressed:
                    st.write("No actions were suppressed.")

                for action in suppressed:
                    st.markdown(
                        f"**{format_action_name(action['type'])}**"
                    )

                    display_rule_reasons(action)

                    st.write(
                        f"**Suppressed by {action['suppressedBy']}:** "
                        f"{action['suppressionReason']}"
                    )

                    st.divider()

            with st.expander(
                f"Missing data ({len(missing)})"
            ):
                display_missing_data(missing)

            # Export the structured result independently of the UI.
            report = {
                "patientId": selected_id,
                "recommendedActions": actions,
                "suppressedActions": suppressed,
                "missingData": missing,
            }

            st.download_button(
                label="Download evaluation JSON",
                data=json.dumps(report, indent=2),
                file_name=f"evaluation_{selected_id}.json",
                mime="application/json",
            )


# ------------------------------------------------------------
# Patients tab
# ------------------------------------------------------------

with patients_tab:
    patient_count = len(list(PATIENTS_DIR.glob("*.json")))
    patient_mode = st.radio(
        "Patients",
        ["consult", "insert"],
        format_func=lambda mode: (
            f"Consult patients ({patient_count} available)"
            if mode == "consult" else "Insert new patient"
        ),
        horizontal=True,
        key="patient_mode",
    )

    if patient_mode == "consult":
        try:
            patients_for_view = load_patients()

        except (OSError, ValueError) as error:
            st.error(f"Could not load patients: {error}")
            patients_for_view = {}

        if not patients_for_view:
            st.info("No patients available.")

        else:
            view_id = st.selectbox(
                "Select a patient",
                options=list(patients_for_view),
                format_func=lambda pid: patient_label(
                    pid, patients_for_view
                ),
                key="consult_patient",
            )

            st.json(
                patient_data_for_display(
                    patients_for_view[view_id]
                ),
                expanded=True,
            )

    else:
        st.subheader("Insert new patient")

        next_patient_id = next_id(
            (path.stem for path in PATIENTS_DIR.glob("*.json")),
            "P",
        )

        st.caption(
            f"Suggested patient ID: {next_patient_id} "
            "(enter an ID in the JSON; suggestions are not reserved)"
        )

        st.info(
            "Enter a JSON object describing the patient's attributes. "
            "There is no fixed patient schema; any field can be added. "
            " Missing attributes and null values are treated as "
            "unavailable when evaluated. Empty lists are valid values."
        )

        patient_text = st.text_area(
            "Patient JSON",
            value=json.dumps(PATIENT_EXAMPLE, indent=2),
            height=290,
            key="new_patient_json",
        )

        if st.button("Save patient", type="primary"):
            try:
                patient_data = json.loads(patient_text)
                saved_id = save_patient(patient_data)

            except (OSError, ValueError, TypeError) as error:
                st.error(f"Could not save patient: {error}")

            else:
                st.session_state["pending_patient"] = saved_id
                st.session_state["patient_saved"] = saved_id
                st.rerun()


# ------------------------------------------------------------
# Rules tab
# ------------------------------------------------------------

with rules_tab:
    display_rules_guide()

    try:
        rule_count = len(load_rules(RULES_PATH))
    except (OSError, ValueError, TypeError, KeyError, RuleValidationError):
        rule_count = 0

    rule_mode = st.radio(
        "Rules",
        ["consult", "insert"],
        format_func=lambda mode: (
            f"Consult rules ({rule_count} available)"
            if mode == "consult" else "Insert new rule"
        ),
        horizontal=True,
        key="rule_mode",
    )

    rules_load_error = None

    try:
        rules = load_rules(RULES_PATH)
        validate_rules(rules)

    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RuleValidationError,
    ) as error:
        rules_load_error = error
        rules = []
        st.error(f"Could not load rules: {error}")

    if rules_load_error is None:

        if rule_mode == "consult":

            if not rules:
                st.info("No rules configured.")

            else:
                rule_by_id = {
                    rule["id"]: rule
                    for rule in rules
                }

                selected_rule_id = st.selectbox(
                    "Select a rule",
                    options=list(rule_by_id),
                    format_func=lambda rid: (
                        f"{rid} — {rule_by_id[rid]['name']}"
                    ),
                    key="consult_rule",
                )

                st.json(
                    rule_by_id[selected_rule_id],
                    expanded=True,
                )

        else:
            st.subheader("Insert new rule")

            next_rule_id = next_id(
                (rule["id"] for rule in rules),
                "R",
            )

            st.caption(
                f"Suggested rule ID: {next_rule_id} "
                "(enter an ID in the JSON; suggestions are not reserved)"
            )

            rule_type = st.radio(
                "Rule type",
                ["generation", "suppression"],
                horizontal=True,
            )

            example = (
                GENERATION_EXAMPLE
                if rule_type == "generation"
                else SUPPRESSION_EXAMPLE
            )

            st.caption(
                "Edit the JSON example below, including its ID. "
                "IDs must be unique."
            )

            rule_text = st.text_area(
                "Rule JSON",
                value=json.dumps(example, indent=2),
                height=370,
                key=f"rule_json_{rule_type}",
            )

            if st.button("Save rule", type="primary"):
                try:
                    rule_data = json.loads(rule_text)
                    saved_id = save_rule(rule_data)

                except (
                    OSError,
                    ValueError,
                    TypeError,
                    KeyError,
                    RuleValidationError,
                ) as error:
                    st.error(f"Could not save rule: {error}")

                else:
                    st.session_state["rule_saved"] = saved_id
                    st.rerun()


# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------

st.divider()
