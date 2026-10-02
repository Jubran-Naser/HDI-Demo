"""The endpoint end to end, with a stand-in for the AI model (see conftest.py): decision, audit record, /stats."""

CLAIM_TEXT = "Polizzennummer VK 998273 A, Kennzeichen W-12345A, Unfall am 3.4.2026. Schaden 1.450,50 Euro."


def test_a_claim_is_decided_and_recorded(client):
    response = client.post("/claims", json={"claim_text": CLAIM_TEXT}).json()
    assert response["outcome"] == "auto_approve"
    assert response["audit_record_id"] >= 1


def test_stats_counts_every_decision(client):
    before = client.get("/stats").json()["decisions"]
    client.post("/claims", json={"claim_text": CLAIM_TEXT})
    assert client.get("/stats").json()["decisions"] == before + 1
