"""Shared test setup. Tests never call a real AI model, so they run anywhere in seconds (also on GitHub)."""

import os
import tempfile

# Before the service's code is loaded: the endpoint tests save their audit records in a throwaway database
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test-audit.db"

import pytest  # noqa: E402  (imported after the setting above on purpose)
from fastapi.testclient import TestClient  # noqa: E402

import app.edges.api as api  # noqa: E402
from app.core.models import validate_fields  # noqa: E402

STAND_IN_ANSWER = {"policy_number": "VK-998273-A", "incident_date": "3.4.2026", "amount_claimed": 1450.5,
                   "licence_plate": "W-12345A"}


@pytest.fixture
def client(monkeypatch):
    """The endpoint, with stand-ins for the three places the service talks to the AI model."""
    monkeypatch.setattr(api, "self_test_thinking_off", lambda: None)
    monkeypatch.setattr(api, "provenance", lambda: {"ai_model": "stand-in", "ai_model_fingerprint": "none",
                                                    "instructions_fingerprint": "none"})
    monkeypatch.setattr(api, "extract_claim", lambda claim_text: validate_fields(STAND_IN_ANSWER))
    with TestClient(api.app) as client:
        yield client
