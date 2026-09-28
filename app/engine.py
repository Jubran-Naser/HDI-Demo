"""The engine: send claim text to the local model, get a typed InsuranceClaim back.

Uses structured output — the InsuranceClaim schema is sent with the request, and the
model server constrains the reply to JSON that fits it; pydantic then validates it.
"""

from openai import OpenAI

from app.config import settings
from app.models import InsuranceClaim

client = OpenAI(base_url=settings.engine_base_url, api_key=settings.engine_api_key)

# First-draft prompt. Wording is a design decision; revisited in the robustness step.
SYSTEM_PROMPT = (
    "You extract data from German insurance claim texts (Schadenmeldungen). "
    "Fill each field only with information stated in the text. "
    "If a field is not stated, leave it null — never guess."
)


def extract_claim(text: str) -> InsuranceClaim:
    response = client.chat.completions.parse(
        model=settings.engine_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format=InsuranceClaim,
        temperature=0,  # same input → same output; needed for repeatable results
    )
    return response.choices[0].message.parsed
