"""The escalate-if-doubtful check: can this claim go through automatically?

Pure functions — no network, no AI model, no settings: the same extracted claim and
claim text always give the same outcome.

Proxy checks each ask one question about one field and return passed or flagged —
they never decide. The rule collects them: any flag → escalate (to a person).

A live claim has no answer key, so every comparison is against the claim text. That is
what makes these *proxy* checks: "the AI model's value appears in the claim text"
suggests, but does not prove, that it is the right value (e.g. the report date instead
of the incident date would still pass). Whether the check is good enough is measured offline.

v1 scope: completeness for every field; verification against the claim text for all
four: policy number, licence plate, incident date (read day-first) and amount (read in
German number format: "1.450,50 €" → 1450.50).
"""

from datetime import date

from app.core.models import ClaimDecision, InsuranceClaim, ProxyCheckResult
from app.core.text_matching import amounts_in_text, dates_in_text, identifier_in_text, to_cents

FIELDS = ("policy_number", "incident_date", "amount_claimed", "licence_plate")
IDENTIFIER_FIELDS = ("policy_number", "licence_plate")


# --- proxy checks: one question about one field → one result -------------------------------

def type_check_failed(field: str, failed_value: object) -> ProxyCheckResult:
    return ProxyCheckResult(
        field=field,
        kind="type_check",
        passed=False,
        detail=f"the AI model's value {failed_value!r} doesn't fit this field's type",
    )


def completeness(field: str, present: bool) -> ProxyCheckResult:
    return ProxyCheckResult(
        field=field,
        kind="completeness",
        passed=present,
        detail="present" if present else "missing",
    )


def verify_identifier_against_text(field: str, value: str, claim_text: str) -> ProxyCheckResult:
    found = identifier_in_text(value, claim_text)
    return ProxyCheckResult(
        field=field,
        kind="verification",
        passed=found,
        detail=f"{value!r} {'found' if found else 'not found'} in the claim text",
    )


def verify_date_against_text(value: date, claim_text: str) -> ProxyCheckResult:
    found = value in dates_in_text(claim_text)
    return ProxyCheckResult(
        field="incident_date",
        kind="verification",
        passed=found,
        detail=f"{value.isoformat()} {'found' if found else 'not found'} among the dates in the claim text",
    )



def verify_amount_against_text(value: float, claim_text: str) -> ProxyCheckResult:
    amount = to_cents(value)                                        # 1450.5 → 1450.50
    found = amount in amounts_in_text(claim_text)
    return ProxyCheckResult(
        field="amount_claimed",
        kind="verification",
        passed=found,
        detail=f"{amount} {'found' if found else 'not found'} among the amounts in the claim text",
    )

# --- running the proxy checks --------------------------------------------------------------

def proxy_checks_for_field(
    field: str,
    extracted_claim: InsuranceClaim,
    type_check_failures: dict[str, object],
    claim_text: str,
) -> list[ProxyCheckResult]:
    """Ask one field's questions in order; stop when the next question is pointless."""
    if field in type_check_failures:
        return [type_check_failed(field, type_check_failures[field])]

    value = getattr(extracted_claim, field)
    if value is None:
        return [completeness(field, present=False)]

    results = [completeness(field, present=True)]
    if field in IDENTIFIER_FIELDS:
        results.append(verify_identifier_against_text(field, value, claim_text))
    elif field == "incident_date":
        results.append(verify_date_against_text(value, claim_text))
    elif field == "amount_claimed":
        results.append(verify_amount_against_text(value, claim_text))
    return results


def run_proxy_checks(
    extracted_claim: InsuranceClaim,
    type_check_failures: dict[str, object],
    claim_text: str,
) -> list[ProxyCheckResult]:
    results = []
    for field in FIELDS:
        results += proxy_checks_for_field(field, extracted_claim, type_check_failures, claim_text)
    return results


# --- the rule ------------------------------------------------------------------------------

def escalate_if_doubtful(
    extracted_claim: InsuranceClaim,
    type_check_failures: dict[str, object],
    claim_text: str,
) -> ClaimDecision:
    """The escalate-if-doubtful check: all proxy checks, then the rule — any flag → escalate."""
    results = run_proxy_checks(extracted_claim, type_check_failures, claim_text)
    all_passed = all(result.passed for result in results)
    return ClaimDecision(
        extracted_claim=extracted_claim,
        proxy_check_results=results,
        outcome="auto_approve" if all_passed else "escalate",
    )
