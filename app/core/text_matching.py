"""Text matching: find values in the claim text and bring them into one comparable form.

Pure functions — no network, no AI model, no settings. Used by the proxy checks in
escalation.py to answer "is the AI model's value written in the claim text?".
"""

import re
from datetime import date
from decimal import Decimal

# Dates in the claim text. Day first (Austrian order) is a stated assumption: 3.4.2026 = 3 April.
DAY_FIRST_DATE = re.compile(r"\b(?P<day>\d{1,2})[./-](?P<month>\d{1,2})[./-](?P<year>\d{4}|\d{2})\b")
ISO_DATE = re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")

# Amounts in the claim text: a number directly before or after a currency word or sign.
#   before: "1.450,50 Euro" · "1450,50 €" · "1.450,- €"      after: "€ 800" · "EUR 1450.50"
AMOUNT_BEFORE_CURRENCY = re.compile(r"(?<![\w.,])(?P<number>\d[\d.,]*(?:,-)?)\s*(?:€|EUR\b|Euro\b)", re.IGNORECASE)
AMOUNT_AFTER_CURRENCY = re.compile(r"(?:€|\bEUR|\bEuro)\s*(?P<number>\d[\d.,]*(?:,-)?)", re.IGNORECASE)
CENT = Decimal("0.01")

# Characters allowed between the characters of an identifier: space, hyphen, dot, slash — any number, or none.
IDENTIFIER_SEPARATORS = r"[\s\-./]*"


# --- identifiers (policy number, licence plate) -------------------------------------------

def normalize_identifier(value: str) -> str:
    """Capitals, no separators: 'vk-998273 a' → 'VK998273A'."""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def identifier_in_text(identifier: str, claim_text: str) -> bool:
    """Is this identifier written in the claim text — with or without separators?

    Normalizes the claim text only at the spot being compared: 'VK998273A' matches
    'VK 998273 A' and 'vk-998273-a', but never inside a longer identifier ('XVK998273A1').
    """
    characters = normalize_identifier(identifier)
    pattern = IDENTIFIER_SEPARATORS.join(re.escape(character) for character in characters)
    not_inside_a_longer_identifier = rf"(?<![A-Z0-9]){pattern}(?![A-Z0-9])"
    return re.search(not_inside_a_longer_identifier, claim_text, re.IGNORECASE) is not None


# --- dates ---------------------------------------------------------------------------------

def dates_in_text(claim_text: str) -> list[date]:
    """Every real date written in the claim text, day-first (Austrian order) or ISO."""
    matches = [*DAY_FIRST_DATE.finditer(claim_text), *ISO_DATE.finditer(claim_text)]
    possible_dates = [to_date(match) for match in matches]
    return [real_date for real_date in possible_dates if real_date is not None]


def read_date_as_written(written: str) -> date | None:
    """One date as the AI model copied it from the claim text → a real date.

    Reads the same forms as dates_in_text: '28.04.2026' · '9.6.26' · '2026-04-28'.
    None if it isn't one date in those forms (e.g. '3. März 2026', 'gestern').
    """
    for pattern in (DAY_FIRST_DATE, ISO_DATE):
        match = pattern.fullmatch(written.strip())
        if match:
            return to_date(match)
    return None


def to_date(match: re.Match) -> date | None:
    """A matched date → a real date, or None if it can't exist (e.g. 30.2.)."""
    try:
        return date(full_year(int(match["year"])), int(match["month"]), int(match["day"]))
    except ValueError:
        return None


def full_year(year: int) -> int:
    """Two-digit years are read as 20xx: 23 → 2023."""
    return 2000 + year if year < 100 else year


# --- amounts -------------------------------------------------------------------------------

def amounts_in_text(claim_text: str) -> list[Decimal]:
    """Every amount written next to a currency word or sign in the claim text, to the cent."""
    matches = [*AMOUNT_BEFORE_CURRENCY.finditer(claim_text), *AMOUNT_AFTER_CURRENCY.finditer(claim_text)]
    return [to_cents(read_german_number(match["number"])) for match in matches]


def read_german_number(written: str) -> Decimal:
    """German number format → a number: '1.450,50' → 1450.50.

    Stated assumption: a '.' followed by exactly 3 digits (and no ',') separates thousands
    ('1.450' → 1450); otherwise the last mark is the decimal mark ('1450.50' → 1450.50).
    """
    # "1.450,-" means no cents; a trailing "." is the sentence's full stop.
    written = written.removesuffix(",-").rstrip(".,")              # "1.450,50." → "1.450,50"

    last_mark = max(written.rfind(","), written.rfind("."))
    if last_mark == -1:
        return Decimal(written)                                     # "800" → 800

    digits_after_mark = len(written) - last_mark - 1
    if written[last_mark] == "." and digits_after_mark == 3 and "," not in written:
        return Decimal(written.replace(".", ""))                    # "1.450" → "1450" → 1450

    whole_part = written[:last_mark].replace(".", "").replace(",", "")    # "1.450,50" → "1450"
    decimal_part = written[last_mark + 1:]                                # "1.450,50" → "50"
    return Decimal(f"{whole_part}.{decimal_part}")                        # "1450.50" → 1450.50


def to_cents(number: Decimal | float) -> Decimal:
    """Round to the cent, so 1450.5 and 1450.50 compare as equal."""
    return Decimal(str(number)).quantize(CENT)                      # 1450.5 → "1450.5" → 1450.50
