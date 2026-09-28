"""FastAPI service — local, privacy-first claim extraction with a human-review gate.

It.1: POST /claims returns the typed extraction. The gate verdict is added next.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import settings
from app.engine import extract_claim
from app.models import InsuranceClaim

app = FastAPI(title="local-claim-intake", version="0.1.0")


class ClaimRequest(BaseModel):
    text: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "engine_model": settings.engine_model}


@app.post("/claims", response_model=InsuranceClaim)
def create_claim(request: ClaimRequest) -> InsuranceClaim:
    return extract_claim(request.text)
