"""Typed contracts for the service.

v1 extraction target: flat, and every field optional (`| None`) so the AI model can
honestly abstain (return None) on a missing field instead of being pressured to
invent one — which is exactly the hallucination the escalate-if-doubtful check has to catch.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ValidationError, field_validator

from app.core.text_matching import read_date_as_written


class InsuranceClaim(BaseModel):
    policy_number: str | None = None     # Polizzennummer, e.g. "VK-998273-A"
    incident_date: date | None = None    # the AI model copies it as written ("28.04.2026"); read_date_as_written reads it
    amount_claimed: float | None = None  # Schadenshöhe, e.g. 1450.50
    licence_plate: str | None = None     # Kennzeichen, e.g. "W-12345A"

    @field_validator("incident_date", mode="before")
    @classmethod
    def read_copied_date(cls, value: object) -> object:
        if isinstance(value, str):
            return read_date_as_written(value) or value   # unreadable → left as is → the type check sets it aside
        return value


class ProxyCheckResult(BaseModel):
    """The result of one proxy check: one question about one field → passed or flagged."""

    field: str
    kind: Literal["type_check", "completeness", "verification"]
    passed: bool
    detail: str


class ClaimDecision(BaseModel):
    """Our endpoint's response: what the AI model extracted, every proxy check result, and the outcome."""

    extracted_claim: InsuranceClaim
    proxy_check_results: list[ProxyCheckResult]
    outcome: Literal["auto_approve", "escalate"]


def validate_fields(reply: dict) -> tuple[InsuranceClaim, dict[str, object]]:
    """Type-check the AI model's reply field by field.

    Returns the extracted claim (fields that failed their type left empty) and the
    type check failures: field → the AI model's value that didn't fit.
    """
    try:
        return InsuranceClaim.model_validate(reply), {}
    except ValidationError as error:
        failed_fields = {problem["loc"][0] for problem in error.errors() if problem["loc"]}
        type_check_failures = {field: reply.get(field) for field in failed_fields}
        fitting_fields = {field: value for field, value in reply.items() if field not in failed_fields}
        return InsuranceClaim.model_validate(fitting_fields), type_check_failures
