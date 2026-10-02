"""Text matching: finding values in the claim text and reading them the Austrian way."""

from datetime import date
from decimal import Decimal

import pytest

from app.core.text_matching import (amounts_in_text, dates_in_text, identifier_in_text, read_date_as_written,
                                    read_german_number)


@pytest.mark.parametrize("written, number", [
    ("1.450,50", Decimal("1450.50")),   # thousands dot, decimal comma
    ("1450,50", Decimal("1450.50")),    # no thousands dot
    ("1.450,-", Decimal("1450")),       # ",-" = no cents
    ("1450.50", Decimal("1450.50")),    # English style
    ("12.500", Decimal("12500")),       # a dot before exactly 3 digits separates thousands
])
def test_read_german_number(written, number):
    assert read_german_number(written) == number


def test_amounts_need_a_currency():
    assert amounts_in_text("Schaden € 1.450,50, Polizze VK-998273-A") == [Decimal("1450.50")]


def test_dates_are_read_day_first_and_impossible_dates_dropped():
    assert dates_in_text("Unfall am 3.4.2026, gemeldet am 5.4.26") == [date(2026, 4, 3), date(2026, 4, 5)]
    assert dates_in_text("am 30.02.2026") == []


@pytest.mark.parametrize("identifier, text, found", [
    ("VK998273A", "Polizze VK. 998 273 A", True),      # spaces and dots between the characters
    ("W-12345A", "Kennzeichen W-12345AB", False),      # never inside a longer identifier
])
def test_identifier_in_text(identifier, text, found):
    assert identifier_in_text(identifier, text) == found


@pytest.mark.parametrize("written, read", [
    ("28.04.2026", date(2026, 4, 28)),
    ("9.6.26", date(2026, 6, 9)),
    ("2026-04-28", date(2026, 4, 28)),
    ("3. März 2026", None),     # written-out months are not read (stated limit)
    ("gestern", None),
])
def test_read_date_as_written(written, read):
    assert read_date_as_written(written) == read
