"""Offline measuring: run the 50 mock claims through the real endpoint and grade each one.

Every claim goes through POST /claims in-process (FastAPI's TestClient: the same code path as
a live request, no server needed). One line per mock claim is saved, so every number in the
results report can be traced back to its claims.

Run from the repo root:  python -m eval.run_eval <label>     (e.g. baseline)
"""

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.core.escalation import FIELDS
from app.core.text_matching import normalize_identifier, to_cents
from app.edges.api import app
from app.edges.config import settings

EVAL_DIR = Path(__file__).parent

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


def main() -> None:
    mock_claims = yaml.safe_load((EVAL_DIR / "mock_claims.yaml").read_text())
    graded = []
    with TestClient(app) as client:                     # runs the startup self-test first
        for mock_claim in mock_claims:
            decision = client.post("/claims", json={"claim_text": mock_claim["claim_text"]}).json()
            graded.append(grade_claim(mock_claim, decision))
            print(f"{mock_claim['id']:10} {graded[-1]['grade']}")

    label = sys.argv[1] if len(sys.argv) > 1 else "run"   # names the run, e.g. "baseline" / "date-as-written"
    run = {"run_date": date.today().isoformat(), "label": label, "ai_model": settings.ai_model,
           "mock_claims": len(mock_claims)}
    results_file = EVAL_DIR / "results" / f"{run['run_date']}_{label}.jsonl"
    results_file.parent.mkdir(exist_ok=True)
    lines = [json.dumps(line, ensure_ascii=False, default=str) for line in [run, *graded]]
    results_file.write_text("\n".join(lines) + "\n")

    print(Counter(line["grade"] for line in graded))
    print(f"saved: {results_file}")


if __name__ == "__main__":
    main()
