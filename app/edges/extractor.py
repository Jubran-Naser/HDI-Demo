"""Our extractor: send the claim text to the model server, get the AI model's reply back.

Uses structured output — the InsuranceClaim schema is sent with the request, and the
model server constrains the reply to JSON that fits it. The type check
(core/models.py → validate_fields) then sets aside any value that doesn't fit its type,
instead of failing — a doubtful answer is a case for a person, not an error.
"""

import hashlib
import json

import httpx
import openai
from openai import OpenAI

from app.core.models import InsuranceClaim, validate_fields
from app.edges.config import settings

client = OpenAI(
    base_url=settings.model_server_url,
    api_key=settings.model_server_api_key,
    timeout=settings.model_server_timeout_seconds,
    max_retries=0,   # no silent retries: a failed attempt sends the claim to a person instead of waiting longer
)


class NoUsableAnswer(Exception):
    """The AI model gave no usable answer; `reason` says why, in plain words."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason

# Second prompt: what each field means and what it looks like, plus general reading rules. Written after
# seeing the baseline run's misses, but naming no specific trap from the mock claims (disclosed in the README).
SYSTEM_PROMPT = (
    "You extract four fields from a German-language car insurance claim (Schadenmeldung) sent to an "
    "Austrian insurer. The claim may be a letter, an email, a chat, a note of a phone call or a transcript.\n"
    "\n"
    "Fields:\n"
    "- policy_number: the claimant's own insurance policy number (Polizzennummer). Policy numbers have "
    "the form VK-998273-A: 'VK', six digits, one letter.\n"
    "- incident_date: the day the damage happened.\n"
    "- amount_claimed: the damage sum the claimant asks to be paid, as a number. Amounts are written in "
    "German number format: 1.450,50 € means 1450.50.\n"
    "- licence_plate: the plate of the claimant's own insured vehicle. Austrian plates start with a "
    "district code of one or two letters, followed by digits and letters, e.g. W-12345A or PL-987K.\n"
    "\n"
    "Rules:\n"
    "- Use only what the text states. If a field is not stated, return null. Never guess or calculate.\n"
    "- Copy policy numbers, licence plates and dates completely and exactly as written."
)


def _response_format() -> dict:
    """The InsuranceClaim schema in the strict form structured output expects."""
    schema = InsuranceClaim.model_json_schema()
    # The date as written ("28.04.2026"); our code reads it (models.py). A "format": "date" rule here makes the
    # model server force year-first digits, which scrambled 15 of 50 dates in the baseline run ("2804-04-20").
    schema["properties"]["incident_date"] = {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Incident Date"}
    schema["required"] = list(schema["properties"])  # every field present; null = "not stated"
    schema["additionalProperties"] = False
    for prop in schema["properties"].values():
        prop.pop("default", None)
    return {
        "type": "json_schema",
        "json_schema": {"name": "InsuranceClaim", "schema": schema, "strict": True},
    }


def extract_claim(claim_text: str) -> tuple[InsuranceClaim, dict[str, object]]:
    try:
        response = client.chat.completions.create(
            model=settings.ai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": claim_text},
            ],
            response_format=_response_format(),
            temperature=0,  # same input → same output; needed for repeatable results
            extra_body=settings.model_server_extra_body,  # thinking off
        )
    except openai.APITimeoutError as error:     # listed first: it's a kind of connection error
        raise NoUsableAnswer(
            f"the AI model did not answer within {settings.model_server_timeout_seconds:g} seconds") from error
    except openai.APIConnectionError as error:
        raise NoUsableAnswer("the model server could not be reached") from error
    except openai.APIStatusError as error:
        raise NoUsableAnswer(f"the model server returned an error (HTTP {error.status_code})") from error
    return validate_fields(fields_from_reply(response.choices[0].message))


def fields_from_reply(message) -> dict:
    """The AI model's reply as a set of fields, or NoUsableAnswer if there's nothing usable in it."""
    if getattr(message, "refusal", None):
        raise NoUsableAnswer("the AI model refused to answer")
    try:
        reply = json.loads(message.content or "")
    except json.JSONDecodeError as error:
        raise NoUsableAnswer("the AI model's reply was not valid JSON") from error
    if not isinstance(reply, dict):
        raise NoUsableAnswer("the AI model's reply was not a set of fields")
    return reply


def self_test_thinking_off() -> None:
    """Thinking-off self-test — runs once at service startup, not per claim.

    Sends a tiny request with the same extra options every claim request uses. If the
    model server still returns thinking text (Ollama puts it in a `reasoning` field),
    model_server_extra_body doesn't fit this model server: stop before any claim is read.
    """
    response = client.chat.completions.create(
        model=settings.ai_model,
        messages=[{"role": "user", "content": "Reply with: ok"}],
        max_tokens=5,  # keeps the self-test short even if thinking is wrongly on
        temperature=0,
        extra_body=settings.model_server_extra_body,
    )
    if getattr(response.choices[0].message, "reasoning", None):
        raise RuntimeError(
            "Thinking-off self-test failed: the AI model returned thinking text. "
            "Set MODEL_SERVER_EXTRA_BODY to this model server's way of switching thinking off."
        )


def provenance() -> dict:
    """Which exact system decides: the AI model, its version, and the instructions it gets."""
    instructions = SYSTEM_PROMPT + json.dumps(_response_format(), sort_keys=True)
    return {
        "ai_model": settings.ai_model,
        "ai_model_fingerprint": ai_model_fingerprint(),
        "instructions_fingerprint": hashlib.sha256(instructions.encode()).hexdigest()[:12],
    }


def ai_model_fingerprint() -> str:
    """Ollama's fingerprint (digest) of the AI model's files: it changes when the model is updated.
    'unknown' on model servers that don't report one."""
    ollama_root = settings.model_server_url.removesuffix("/v1")
    try:
        models = httpx.get(f"{ollama_root}/api/tags", timeout=5).json()["models"]
    except (httpx.HTTPError, KeyError, ValueError):
        return "unknown"
    return next((model["digest"][:12] for model in models if model["name"] == settings.ai_model), "unknown")
