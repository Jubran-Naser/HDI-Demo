"""Offline measuring: run the 50 mock claims through the real endpoint and grade each one.

Every claim goes through POST /claims in-process (FastAPI's TestClient: the same code path as
a live request, no server needed). One line per mock claim is saved, so every number in the
results report can be traced back to its claims.

Run from the repo root:  python -m eval.run_eval <label>     (e.g. baseline)
"""

import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///eval/results/eval-audit.db"   # mock claims never reach the service's own logbook

import yaml
from fastapi.testclient import TestClient

from app.edges.api import app
from app.edges.config import settings
from eval.grading import grade_claim

EVAL_DIR = Path(__file__).parent


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
