"""Typed contracts for the service.

v1 extraction target: flat, and every field optional (`| None`) so the model can
honestly abstain (return None) on a missing field instead of being pressured to
invent one — which is exactly the hallucination the gate later has to catch.
"""

from pydantic import BaseModel


class InsuranceClaim(BaseModel):
    policy_number: str | None = None     # Polizzennummer, e.g. "VK-998273-A"
    incident_date: str | None = None     # kept as text in v1; normalized to a real date later
    amount_claimed: float | None = None  # Schadenshöhe, e.g. 1450.50
    licence_plate: str | None = None     # Kennzeichen, e.g. "B-XY 1234"
