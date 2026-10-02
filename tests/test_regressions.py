"""Bugs found while measuring (eval/), each kept as a test so it can't come back."""

import json
from datetime import date

from app.edges.extractor import _response_format
from eval.grading import needs_a_person


def test_the_ai_model_is_not_given_a_date_format():
    # Found 2026-10-01: a "format": "date" rule in the answer schema made the model server force year-first digits;
    # 15 of 50 dates came back garbled ("28.04.2026" became "2804-04-20"). The AI model now copies the date as written.
    incident_date = _response_format()["json_schema"]["schema"]["properties"]["incident_date"]
    assert "format" not in json.dumps(incident_date)


def test_a_claim_with_a_missing_field_rightly_goes_to_a_person():
    # Found 2026-10-01: the first grading called this "needlessly escalated" because the AI model was right
    # ("not there"). But someone still has to ask the customer for the missing policy number.
    mock_claim = {"correct": {"policy_number": None, "incident_date": date(2026, 2, 10),
                              "amount_claimed": 1230.0, "licence_plate": "W-73561X"}}
    assert needs_a_person(mock_claim, ai_model_right=True)
