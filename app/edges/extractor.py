"""Our extractor: send the claim text to the model server, get the AI model's reply back.

Uses structured output — the InsuranceClaim schema is sent with the request, and the
model server constrains the reply to JSON that fits it. The type check
(core/models.py → validate_fields) then sets aside any value that doesn't fit its type,
instead of failing — a doubtful answer is a case for a person, not an error.
"""

import json

from openai import OpenAI

from app.core.models import InsuranceClaim, validate_fields
from app.edges.config import settings

client = OpenAI(base_url=settings.model_server_url, api_key=settings.model_server_api_key)

# First-draft prompt. Wording is a design decision; revisited in the robustness step.
SYSTEM_PROMPT = (
    "You extract data from German insurance claim texts (Schadenmeldungen). "
    "Fill each field only with information stated in the text. "
    "If a field is not stated, leave it null — never guess."
)


def _response_format() -> dict:
    """The InsuranceClaim schema in the strict form structured output expects."""
    schema = InsuranceClaim.model_json_schema()
    schema["required"] = list(schema["properties"])  # every field present; null = "not stated"
    schema["additionalProperties"] = False
    for prop in schema["properties"].values():
        prop.pop("default", None)
    return {
        "type": "json_schema",
        "json_schema": {"name": "InsuranceClaim", "schema": schema, "strict": True},
    }


def extract_claim(claim_text: str) -> tuple[InsuranceClaim, dict[str, object]]:
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
    return validate_fields(json.loads(response.choices[0].message.content))


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
