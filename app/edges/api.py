"""FastAPI service — local, privacy-first claim extraction with an escalate-if-doubtful check.

POST /claims extracts the claim with a local AI model, checks it against the claim text, saves
an audit record, and returns the outcome: auto_approve, or escalate to a person.
GET /stats returns the straight-through-processing rate over all audit records.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel

from app.core.escalation import escalate_if_doubtful
from app.core.models import ClaimDecision
from app.edges.audit import create_tables, save_audit_record, straight_through_rate
from app.edges.config import settings
from app.edges.extractor import extract_claim, provenance, self_test_thinking_off


@asynccontextmanager
async def lifespan(app: FastAPI):
    self_test_thinking_off()               # a configuration mistake stops the service here, before the first claim
    create_tables()
    app.state.provenance = provenance()    # fixed for as long as the service runs
    yield


app = FastAPI(title="local-claim-intake", version="0.1.0", lifespan=lifespan)


class ClaimRequest(BaseModel):
    claim_text: str


class ClaimResponse(ClaimDecision):
    audit_record_id: int                   # the caller can refer to this decision later


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ai_model": settings.ai_model}


@app.post("/claims", response_model=ClaimResponse)
def receive_claim(request: ClaimRequest) -> ClaimResponse:
    received_at = datetime.now(timezone.utc)
    extracted_claim, type_check_failures = extract_claim(request.claim_text)
    decision = escalate_if_doubtful(extracted_claim, type_check_failures, request.claim_text)
    record_id = save_audit_record(request.claim_text, decision, app.state.provenance, received_at)
    return ClaimResponse(**decision.model_dump(), audit_record_id=record_id)


@app.get("/stats")
def stats() -> dict:
    return straight_through_rate()
