"""When the AI model gives no usable answer, the claim still gets a decision: escalate, with the reason recorded."""

from types import SimpleNamespace

import pytest
from openai import OpenAI

import app.edges.api as api
import app.edges.extractor as extractor
from app.edges.extractor import NoUsableAnswer, fields_from_reply


def test_an_unreachable_model_server_is_named_as_the_reason(monkeypatch):
    # Nothing listens on port 9: a real connection attempt that fails at once
    monkeypatch.setattr(extractor, "client", OpenAI(base_url="http://127.0.0.1:9/v1", api_key="none", max_retries=0))
    with pytest.raises(NoUsableAnswer, match="could not be reached"):
        extractor.extract_claim("Unfall am 3.4.2026")


@pytest.mark.parametrize("content, refusal, reason", [
    ("not json at all", None, "not valid JSON"),
    (None, "I can't help with that", "refused"),
    ('["a", "list"]', None, "not a set of fields"),
])
def test_an_unusable_reply_is_named_as_the_reason(content, refusal, reason):
    with pytest.raises(NoUsableAnswer, match=reason):
        fields_from_reply(SimpleNamespace(content=content, refusal=refusal))


def test_no_usable_answer_still_gets_a_recorded_decision(client, monkeypatch):
    def model_server_down(claim_text):
        raise NoUsableAnswer("the model server could not be reached")
    monkeypatch.setattr(api, "extract_claim", model_server_down)
    response = client.post("/claims", json={"claim_text": "Unfall am 3.4.2026"}).json()
    assert response["outcome"] == "escalate"
    assert response["proxy_check_results"][0]["detail"] == "the model server could not be reached"
    assert response["audit_record_id"] >= 1
