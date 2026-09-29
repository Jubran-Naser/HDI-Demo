"""FastAPI service — local, privacy-first claim extraction with an escalate-if-doubtful check.

It.1: POST /claims extracts the claim with a local AI model, checks it against the claim
text, and returns the outcome: auto_approve, or escalate to a person.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from app.core.escalation import escalate_if_doubtful
from app.core.models import ClaimDecision
from app.edges.config import settings
from app.edges.extractor import extract_claim, self_test_thinking_off


@asynccontextmanager
async def lifespan(app: FastAPI):
    self_test_thinking_off()  # a configuration mistake stops the service here, before the first claim
    yield


app = FastAPI(title="local-claim-intake", version="0.1.0", lifespan=lifespan)


class ClaimRequest(BaseModel):
    claim_text: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ai_model": settings.ai_model}


@app.post("/claims", response_model=ClaimDecision)
def receive_claim(request: ClaimRequest) -> ClaimDecision:
    extracted_claim, type_check_failures = extract_claim(request.claim_text)
    return escalate_if_doubtful(extracted_claim, type_check_failures, request.claim_text)
