"""The endpoint end to end, with a stand-in for the AI model: decision, audit record, /stats."""

import pytest
from fastapi.testclient import TestClient

import app.edges.api as api
from app.core.models import validate_fields

CLAIM_TEXT = "Polizzennummer VK 998273 A, Kennzeichen W-12345A, Unfall am 3.4.2026. Schaden 1.450,50 Euro."
ANSWER = {"policy_number": "VK-998273-A", "incident_date": "3.4.2026", "amount_claimed": 1450.5,
          "licence_plate": "W-12345A"}


@pytest.fixture
def client(monkeypatch):
    # Stand-ins for the three places the service talks to the AI model
    monkeypatch.setattr(api, "self_test_thinking_off", lambda: None)
    monkeypatch.setattr(api, "provenance", lambda: {"ai_model": "stand-in", "ai_model_fingerprint": "none",
                                                    "instructions_fingerprint": "none"})
    monkeypatch.setattr(api, "extract_claim", lambda claim_text: validate_fields(ANSWER))
    with TestClient(api.app) as client:
        yield client


def test_a_claim_is_decided_and_recorded(client):
    response = client.post("/claims", json={"claim_text": CLAIM_TEXT}).json()
    assert response["outcome"] == "auto_approve"
    assert response["audit_record_id"] >= 1


def test_stats_counts_every_decision(client):
    before = client.get("/stats").json()["decisions"]
    client.post("/claims", json={"claim_text": CLAIM_TEXT})
    assert client.get("/stats").json()["decisions"] == before + 1
