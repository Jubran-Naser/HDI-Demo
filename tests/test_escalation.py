"""The escalate-if-doubtful check on 24 hand-written AI model answers (no AI model runs).

Each case changes one thing in an otherwise correct answer. The ideal: escalate exactly when the AI model's
answer is wrong. 8 cases are known limits of checking values against the claim text: marked as expected failures.
"""

import pytest

from app.core.escalation import escalate_if_doubtful
from app.core.models import validate_fields

CLAIM_TEXT = "Polizzennummer VK 998273 A, Kennzeichen W-12345A, Unfall am 3.4.2026. Schaden 1.450,50 Euro."
CORRECT_ANSWER = {"policy_number": "VK-998273-A", "incident_date": "3.4.2026",
                  "amount_claimed": 1450.5, "licence_plate": "w12345a"}

# (what it tests, claim text, changes to the AI model's answer, is the AI model's answer right?)
CASES = [
    ("all fields correct", CLAIM_TEXT, {}, True),
    ("policy no. digits swapped", CLAIM_TEXT, {"policy_number": "VK-998237-A"}, False),
    ("impossible date", CLAIM_TEXT, {"incident_date": "30.2.2026"}, False),
    ("policy no. missing", CLAIM_TEXT, {"policy_number": None}, False),
    ("report date picked instead of incident date",
     CLAIM_TEXT.replace("3.4.2026.", "3.4.2026, gemeldet am 5.4.2026."), {"incident_date": "5.4.2026"}, False),
    ("shorter plate", CLAIM_TEXT, {"licence_plate": "W-1234"}, False),
    ("separator not in the list: _", CLAIM_TEXT.replace("W-12345A", "W_12345A"), {"licence_plate": "W12345A"}, True),
    ("separator not in the list: en dash", CLAIM_TEXT.replace("W-12345A", "W–12345A"), {"licence_plate": "W-12345A"},
     True),
    ("spaces and dots in the policy no.", CLAIM_TEXT.replace("VK 998273 A", "VK. 998 273 A"),
     {"policy_number": "VK998273A"}, True),
    ("plate truncated by the AI model", CLAIM_TEXT.replace("W-12345A", "W-12345AB"), {"licence_plate": "W-12345A"},
     False),
    ("the other driver's plate picked",
     CLAIM_TEXT.replace("Kennzeichen W-12345A", "mein Auto W-12345A, Unfallgegner W-99999B"),
     {"licence_plate": "W-99999B"}, False),
    ("two-digit year", CLAIM_TEXT.replace("3.4.2026", "3.4.26"), {}, True),
    ("written-out date", CLAIM_TEXT.replace("3.4.2026", "3. April 2026"), {}, True),
    ("'gestern', AI model guesses a date", CLAIM_TEXT.replace("am 3.4.2026", "gestern"),
     {"incident_date": "29.9.2026"}, False),
    ("date in US order (meant April 3)", CLAIM_TEXT.replace("3.4.2026", "04/03/2026"), {}, True),
    ("amount without a thousands dot", CLAIM_TEXT.replace("1.450,50 Euro", "1450,50 €"), {}, True),
    ("currency before the amount", CLAIM_TEXT.replace("1.450,50 Euro", "€ 1.450,50"), {}, True),
    ("amount in English style", CLAIM_TEXT.replace("1.450,50 Euro", "EUR 1450.50"), {}, True),
    ("'no cents' written as ,-", CLAIM_TEXT.replace("1.450,50 Euro", "1.450,- Euro"), {"amount_claimed": 1450}, True),
    ("approximate amount", CLAIM_TEXT.replace("1.450,50 Euro", "ca. 800 Euro"), {"amount_claimed": 800}, True),
    ("amount digits swapped", CLAIM_TEXT, {"amount_claimed": 1405.5}, False),
    ("policy-number digits taken as the amount", CLAIM_TEXT, {"amount_claimed": 998273}, False),
    ("amount with no currency written", CLAIM_TEXT.replace("1.450,50 Euro", "1.450,50"), {}, True),
    ("towing amount picked instead of repair",
     CLAIM_TEXT.replace("Schaden 1.450,50 Euro", "Reparatur 1.450,50 Euro, Abschleppung 120 €"),
     {"amount_claimed": 120}, False),
]
KNOWN_LIMITS = {
    "report date picked instead of incident date": "a wrong value that is also in the text passes",
    "the other driver's plate picked": "a wrong value that is also in the text passes",
    "towing amount picked instead of repair": "a wrong value that is also in the text passes",
    "separator not in the list: _": "only space, hyphen, dot and slash are allowed between characters",
    "separator not in the list: en dash": "only space, hyphen, dot and slash are allowed between characters",
    "written-out date": "only dates written in numbers are found in the text",
    "date in US order (meant April 3)": "dates are read day-first (a stated assumption)",
    "amount with no currency written": "amounts are only found next to € / EUR / Euro",
}


def case(what, claim_text, changes, answer_right):
    marks = [pytest.mark.xfail(strict=True, reason=f"known limit: {KNOWN_LIMITS[what]}")] if what in KNOWN_LIMITS else []
    return pytest.param(claim_text, changes, answer_right, id=what, marks=marks)


@pytest.mark.parametrize("claim_text, changes, answer_right", [case(*c) for c in CASES])
def test_escalates_exactly_when_the_answer_is_wrong(claim_text, changes, answer_right):
    extracted_claim, type_check_failures = validate_fields({**CORRECT_ANSWER, **changes})
    decision = escalate_if_doubtful(extracted_claim, type_check_failures, claim_text)
    assert decision.outcome == ("auto_approve" if answer_right else "escalate")
