# Healthcare Rules Engine

A configurable, JSON-based rules engine with a Streamlit interface for evaluating synthetic patient data.

The engine evaluates patient information against configurable rules to generate recommended actions with assigned priorities and explanations. It merges duplicate recommendations, applies suppression rules to exclude actions that should not be performed, and reports missing data when a rule cannot be evaluated conclusively.

A Streamlit interface allows users to evaluate patients, inspect results, and add new patients and/or rules.

## 1. How to Run the Project

Requires Python 3.10 or newer.

From the project root, install the dependencies:

```bash
pip install -r requirements.txt
```

Launch the Streamlit application:

```bash
streamlit run app.py
```

Run the automated tests:

```bash
python -m pytest -q
```

### Using the application

The Streamlit interface is organized into three tabs:

- **Evaluation:** Select a patient to evaluate and view the results, including recommended actions, suppressed actions, and missing data. The evaluation can also be downloaded as a JSON file.

- **Patients:** Browse existing patient records or add a new patient by entering their information in JSON format.

- **Rules:** Browse existing rules or add a new rule using the provided JSON examples.

## 2. Architecture

The implementation separates the rules engine from the Streamlit interface:

| Component | Responsibility |
| --- | --- |
| `app.py` | Streamlit UI, loading/saving JSON data, and displaying/exporting evaluations |
| `src/engine.py` | Rule evaluation, action generation, merging, suppression, and result summaries |
| `src/expressions.py` | Comparison and logical expression evaluation, nested field lookup, and missing-field reporting |
| `src/validation.py` | Structural validation of rule definitions |
| `rules/rules.json` | Configured rules |
| `patients/` | Individual patient JSON records |
| `tests/` | Automated tests for rule validation and evaluation behavior |

### Evaluation flow

1. Load and validate the configured rules.
2. Evaluate **generation rules** against the selected patient. Matching rules produce actions with priorities and reasons.
3. Merge actions with the same `type`, retaining the highest generated priority and all contributing rule IDs and reasons.
4. Evaluate **suppression rules** against each generated action. Suppressed actions are listed separately with the suppressing rule and reason.
5. Sort the remaining recommendations by priority: **HIGH**, **MEDIUM**, then **LOW**.
6. Return recommended actions, suppressed actions, and missing-data records.

## 3. Design Decisions

### JSON-based configuration

JSON was chosen to follow the format illustrated in the assignment and keep the implementation simple and easy to inspect. 
Patients are stored in individual JSON files under `patients/`, while rules are maintained together in `rules/rules.json` for straightforward loading and validation. Both can also be managed directly through these files.

### Rule types and evaluation order

Two rule types were introduced to handle the different behaviors required by the assignment:

- **Generation rules** evaluate patient conditions and produce actions with a type, priority, and explanation. They cover requirements such as recommending a geriatric assessment based on age.
- **Suppression rules** evaluate generated actions and exclude those that should not be recommended.

Generation rules are evaluated first, followed by suppression rules. This allows suppression rules to be defined independently of the rules that generate actions.

When multiple suppression rules match an action, the first matching rule determines its suppression and provides the recorded explanation.

### Conditions and operators

The comparison operators `==`, `!=`, `>`, `>=`, `<`, `<=`, and `contains` support the numeric, boolean, and list-based conditions needed for the provided scenarios.

The logical operators `and`, `or`, and `not` allow more complex conditions to be expressed without modifying the engine. Nested field paths, such as `bloodPressure.systolic`, support structured patient data.

Conditions can use either a fixed `value` or a dynamic `valueFrom` reference. Dynamic references enable comparisons between fields, including checking whether a generated action appears in `completedTasks`.

### Duplicate actions and priorities

When multiple rules generate the same action type, their results are merged into a single recommendation to avoid duplicates. All contributing rule IDs and explanations are preserved.

If the rules assign different priorities to the same action, **the highest priority is retained** (`HIGH` > `MEDIUM` > `LOW`). This prevents a lower-priority rule from reducing the urgency assigned by another applicable rule.

The final recommendations are sorted by decreasing priority so that more urgent actions appear first.

### Missing data

Missing fields and explicit `null` values are treated as unavailable rather than as false conditions. When a rule cannot be evaluated conclusively, the missing information is reported while the remaining rules continue to be evaluated.

For logical expressions, a definitive `False` determines the result of `and`, while a definitive `True` determines the result of `or`, even when other fields are missing. Otherwise, the missing fields are reported.

This avoids making recommendations based on unknown values without discarding results that can still be determined.

### Explainability

Each generated action retains the IDs and explanations of the rules that produced it. Suppressed actions also identify the rule responsible for their suppression and its explanation.

This makes evaluation results traceable and allows users to understand why an action was recommended or excluded.

## 4. Assumptions

**Patient data**
- Patient records may have different attributes; no fixed patient schema is enforced.
- Patient attributes are expected to have types compatible with the comparisons defined in the rules. Missing and `null` values are handled explicitly, but comprehensive patient data validation is not performed.

**Rule definitions**
- Rule definitions are structurally validated, but their logical consistency is not checked. For example, a condition requiring both `age < 10` and `age > 30` is accepted but cannot match a patient with a valid numeric age.

**Identifiers**
- Patient and rule IDs must be unique and follow the formats `P###` and `R###`, respectively.
- IDs are entered manually. The interface suggests the next sequential number based on existing records but does not assign or reserve it. 

## 5. Trade-offs

### JSON-based insertion vs. structured forms

Structured forms could make adding patients and rules more accessible, especially for users unfamiliar with JSON. However, patient records can contain different attributes, and rule conditions can include nested logical expressions. Supporting this flexibility through forms would require a more complex interface and additional logic to construct valid configurations.

JSON-based insertion was chosen as a simpler alternative that preserves the flexibility of the underlying data and rule formats. The trade-off is that users need some familiarity with JSON, although the interface provides examples to guide insertion.

### Generic vs. visit-specific follow-ups

The assignment uses `lastVisitDaysAgo` to recommend a generic `follow_up_visit`, without specifying what kind of visit it refers to.

Storing completion dates for individual tasks was also considered, so that follow-ups could be recommended based on previous activities. However, this raised questions about which assessments require follow-ups, how often they should occur, and whether different types of visits should be tracked separately.

The simpler model from the assignment was kept for this prototype. It is sufficient to demonstrate the rules engine, but does not capture the relationship between specific assessments and their follow-ups.

## 6. Limitations and Future Work

The implementation focuses on the core rule evaluation requirements. Some features were left outside the scope of this prototype:

- **Priority adjustments:** The engine merges duplicate actions using the highest generated priority, but does not support separate rules that change an action's priority after generation. This would require an additional evaluation phase and a clear policy for conflicting adjustments.
- **Rule conflicts:** Rules are checked for valid structure, but not for contradictory conditions or conflicting behavior. Detecting these issues would help identify configuration problems before evaluation.
- **Patient data validation:** A more defined patient schema and stronger type checking would help prevent errors caused by incompatible data.
- **Record management:** Existing patients and rules cannot be edited or deleted through the interface.

For a production application, the next priorities would be stronger automated testing, rule versioning, and audit logging, so that evaluations can be reproduced and traced to the rules and data used. Database storage, authentication, and integration with clinical systems would also need to be considered.