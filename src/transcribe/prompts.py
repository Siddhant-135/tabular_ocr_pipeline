"""Prompts. Crops overlap their neighbours by design, so every prompt insists on the
single, vertically centred line of handwriting."""

import json

CENTER_BIAS = (
    "The image is a horizontal strip cut from a scanned handwritten diary page. "
    "It is centred on ONE handwritten row. Parts of the rows directly above and below "
    "may be partially visible at the top and bottom edges: ignore them completely and "
    "read only the line of handwriting that runs through the vertical middle of the image. "
    "Ignore printed text (small hour numbers like 8, 9, 10 in the left margin, the printed "
    "year 2025, calendar text) and ignore words that are struck through."
)

LOCATION_HINT = (
    "Locations are usually a code 'Ph-N' (phase) or 'Sec-N' (sector) where N has 1 to 3 "
    "digits — count the digits carefully, 'Ph-1' and 'Ph-11' are different. Otherwise it is a "
    "village/town name or abbreviation such as 'Vill' or 'MHL'."
)


def col2_prompt() -> str:
    return (
        f"{CENTER_BIAS}\n\n"
        "This strip shows only the middle (location) column. "
        f"{LOCATION_HINT}\n\n"
        "Reply with the location text exactly as written, nothing else. "
        "If there is no readable text in the middle row, reply NONE."
    )


def row_prompt(locations: list[str]) -> str:
    known = json.dumps(locations) if locations else "[] (no dictionary yet)"
    return (
        f"{CENTER_BIAS}\n\n"
        "The row has exactly three columns, left to right:\n"
        "1. name — a person's name, letters only (initials like 'A.C' allowed)\n"
        f"2. location — {LOCATION_HINT} Known locations: {known}. Prefer an exact entry "
        "from this list when the handwriting matches it; otherwise write what you read.\n"
        "3. phone — exactly 10 digits when written; use null if the phone column is blank.\n\n"
        'Reply with a single JSON object and nothing else: {"name": "...", "location": "...", '
        '"phone": "..."}. Use null for a field you cannot read or that is not written on the page.'
    )


def phone_crop_prompt() -> str:
    # Kept short on purpose: the longer CENTER_BIAS preamble measurably hurt digit accuracy.
    return (
        "The image is a horizontal strip cut from a scanned handwritten diary page, centred on ONE "
        "handwritten row; ignore partial rows at the top/bottom edges and any printed text like "
        "'2025'. It shows a handwritten 10-digit Indian mobile phone number. Read it digit by "
        "digit, carefully distinguishing 1/7, 4/9, 3/8, 5/6, 0/6. If no number is written, reply NONE. "
        "Otherwise reply with only the 10 digits, nothing else."
    )


def retry_prompt(locations: list[str], previous: str, failed: list[str]) -> str:
    return (
        f"{row_prompt(locations)}\n\n"
        f"A previous reading of this same image was: {previous!r}\n"
        f"It failed validation for: {', '.join(failed)} "
        "(name: letters only; phone: exactly 10 digits; location: Ph-N / Sec-N / place name). "
        "Look again carefully at the middle row and answer with corrected JSON."
    )
