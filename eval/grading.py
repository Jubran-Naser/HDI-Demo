"""Grading: how one mock claim's decision turned out against its answer key.

Kept apart from the runner so the tests can import it without starting an eval run.
"""

from datetime import date

from app.core.escalation import FIELDS
from app.core.text_matching import normalize_identifier, to_cents

# outcome (what our service decided) × should a person look at this claim? → grade
GRADES = {
    ("auto_approve", False): "correct automatic",
    ("auto_approve", True): "wrong automatic",
    ("escalate", True): "rightly escalated",
    ("escalate", False): "needlessly escalated",
}


def needs_a_person(mock_claim: dict, ai_model_right: bool) -> bool:
    """A person should look if the AI model got a field wrong, or if the claim itself lacks a field
    (someone has to ask the customer), even when the AI model rightly answered "not there"."""
    claim_complete = all(value is not None for value in mock_claim["correct"].values())
    return not (ai_model_right and claim_complete)


def field_right(field: str, answer: object, correct: object) -> bool:
    """One field, compared after the core's normalization: the same "same" as in the live check."""
    if answer is None or correct is None:
        return answer is None and correct is None       # a value where the text states none is a guess: wrong
    if field in ("policy_number", "licence_plate"):
        return normalize_identifier(answer) == normalize_identifier(correct)
    if field == "incident_date":
        return date.fromisoformat(answer) == correct
    return to_cents(answer) == to_cents(correct)


def grade_claim(mock_claim: dict, decision: dict) -> dict:
    answer = decision["extracted_claim"]
    fields_right = {field: field_right(field, answer[field], mock_claim["correct"][field]) for field in FIELDS}
    ai_model_right = all(fields_right.values())
    return {
        "id": mock_claim["id"],
        "kind": mock_claim["kind"],
        "ai_model_answer": answer,
        "correct": mock_claim["correct"],
        "fields_right": fields_right,
        "proxy_check_results": decision["proxy_check_results"],
        "outcome": decision["outcome"],
        "grade": GRADES[(decision["outcome"], needs_a_person(mock_claim, ai_model_right))],
    }
