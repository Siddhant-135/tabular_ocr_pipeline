"""Normalisation + regex validation for the three columns."""

import re

FIELDS = ("name", "location", "phone")

# Letters only, but initials like "A.C Khare", "A-C Rhare", "S.P singh" occur in the data.
NAME_RE = re.compile(r"^[A-Za-z]+(?:[ .'-]+[A-Za-z]+)*\.?$")
PHONE_RE = re.compile(r"^\d{10}$")
# Ph-11, Ph11, ph 4, Sec-49, Sec27, SEC - 66 ... (1-3 digits; Ph-1 must stay distinct from Ph-11)
LOC_CODE_RE = re.compile(r"^(ph|sec)\s*[-.]?\s*(\d{1,3})$", re.IGNORECASE)
# Everything else: village/city names or abbreviations (Vill, MHL, Dharamgarh, ...)
LOC_FREE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 .'-]*$")

NAN = "NaN"


def _clean(s) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


def normalize_name(s) -> str:
    return _clean(s)


def normalize_phone(s) -> str:
    s = _clean(s)
    if s.lower() in ("none", "null", "nan", "n/a", "-", "—"):
        return NAN
    return re.sub(r"[\s\-()]", "", s)


def phone_missing(phone: str) -> bool:
    return phone in ("", NAN)


def normalize_location(s) -> str:
    s = _clean(s)
    m = LOC_CODE_RE.match(s)
    if m:
        prefix = "Ph" if m.group(1).lower() == "ph" else "Sec"
        return f"{prefix}-{int(m.group(2))}"
    return s


def location_kind(loc: str) -> str:
    if LOC_CODE_RE.match(loc):
        return "code"
    if LOC_FREE_RE.match(loc):
        return "place"
    return "invalid"


def normalize_row(row: dict) -> dict:
    raw_phone = row.get("phone")
    if raw_phone is None:
        phone = NAN
    else:
        phone = normalize_phone(raw_phone)
    return {
        "name": normalize_name(row.get("name")),
        "location": normalize_location(row.get("location")),
        "phone": phone,
    }


def failed_fields(row: dict) -> list[str]:
    """Fields of an already-normalised row that fail their regex (empty = missing = fail)."""
    failed = []
    if not NAME_RE.match(row["name"]):
        failed.append("name")
    if location_kind(row["location"]) == "invalid":
        failed.append("location")
    if phone_missing(row["phone"]):
        pass  # genuine blank on the page; name/location still extracted
    elif not PHONE_RE.match(row["phone"]):
        failed.append("phone")
    return failed
