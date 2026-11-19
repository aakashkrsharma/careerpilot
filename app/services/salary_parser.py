"""Normalize salary values without converting between currencies."""
import re
from dataclasses import dataclass
from typing import Optional


_NUMBER = re.compile(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?\s*[kKmM]?")


@dataclass(frozen=True)
class Compensation:
    minimum: Optional[int]
    maximum: Optional[int]
    currency: Optional[str]
    period: Optional[str]
    raw_text: Optional[str]


def parse_compensation(
    value: object,
    *,
    currency_hint: Optional[str] = None,
    period_hint: Optional[str] = None,
) -> Compensation:
    if value is None:
        return Compensation(None, None, _normalize_currency(currency_hint), period_hint, None)

    raw = str(value).strip()
    if not raw:
        return Compensation(None, None, _normalize_currency(currency_hint), period_hint, None)

    normalized = raw.lower()
    currency = _normalize_currency(currency_hint)
    if "₹" in raw or "inr" in normalized or re.search(r"\brs\.?\b", normalized):
        currency = "INR"
    elif "$" in raw or "usd" in normalized:
        currency = "USD"
    elif "€" in raw or "eur" in normalized:
        currency = "EUR"
    elif "£" in raw or "gbp" in normalized:
        currency = "GBP"
    elif "cad" in normalized:
        currency = "CAD"
    elif "aud" in normalized:
        currency = "AUD"

    period = _normalize_period(period_hint)
    if re.search(r"\b(lpa|lakhs?\s*(per\s*annum|a\s*year|/year)?)\b", normalized):
        currency = currency or "INR"
        period = "annual"
        multiplier = 100_000
    elif re.search(r"\b(per\s*month|monthly|/month|per\s*mo)\b", normalized):
        period = period or "monthly"
        multiplier = 1
    elif re.search(r"\b(per\s*hour|hourly|/hour)\b", normalized):
        period = period or "hourly"
        multiplier = 1
    elif re.search(
        r"\b(per\s*year|yearly|annually|annual|/year|p\.?a\.?)\b",
        normalized,
    ):
        period = period or "annual"
        multiplier = 1
    else:
        multiplier = 1

    numbers = [_parse_number(match.group(0)) for match in _NUMBER.finditer(raw)]
    numbers = [number for number in numbers if number is not None]
    if not numbers:
        return Compensation(None, None, currency, period, raw)

    suffix_multiplier = 1
    if re.search(r"\d\s*k\b", normalized):
        suffix_multiplier = 1_000
    elif re.search(r"\d\s*m\b", normalized):
        suffix_multiplier = 1_000_000

    amounts = [int(round(number * suffix_multiplier * multiplier)) for number in numbers[:2]]
    minimum = amounts[0]
    maximum = amounts[1] if len(amounts) > 1 else amounts[0]
    if minimum > maximum:
        minimum, maximum = maximum, minimum
    return Compensation(minimum, maximum, currency, period, raw)


def _parse_number(value: str) -> Optional[float]:
    cleaned = re.sub(r"[,\s]", "", value)
    cleaned = re.sub(r"[kKmM]$", "", cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_currency(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().upper()
    aliases = {
        "₹": "INR",
        "RS": "INR",
        "RS.": "INR",
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
    }
    return aliases.get(normalized, normalized if len(normalized) == 3 else None)


def _normalize_period(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {
        "year",
        "yearly",
        "annual",
        "annually",
        "per_year",
        "pa",
        "p.a.",
    }:
        return "annual"
    if normalized in {"month", "monthly", "per_month", "pm"}:
        return "monthly"
    if normalized in {"hour", "hourly", "per_hour", "ph"}:
        return "hourly"
    if normalized in {"week", "weekly", "per_week", "pw"}:
        return "weekly"
    return normalized[:20]
