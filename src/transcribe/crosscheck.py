"""Near-duplicate phone check across all output/output-*.csv.

Optional heuristic (not a fix): handwriting OCR often misreads one digit (4/9, 1/7) while
name/location match. The same person can appear on multiple pages with two phones that differ
in exactly one digit. Those rows get recheck=true and a note — a human decides which is right.
"""

import csv
from collections import Counter, defaultdict
from itertools import combinations

from transcribe.checks import PHONE_RE
from transcribe.paths import OUTPUT_DIR, page_number
from transcribe.progress import log


def read_table(path) -> tuple[list[str], list[dict]]:
    """Read a CSV, tolerating editor 'align columns' padding around keys and values."""
    with path.open(newline="") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        fieldnames = [k.strip() for k in reader.fieldnames]
        rows = [
            {k.strip(): (v or "").strip() for k, v in r.items() if k is not None}
            for r in reader
        ]
    return fieldnames, rows


def _one_digit_apart(a: str, b: str) -> bool:
    return sum(x != y for x, y in zip(a, b)) == 1


def crosscheck() -> int:
    files = sorted(OUTPUT_DIR.glob("output-*.csv"), key=lambda p: page_number(p.stem))
    tables = {path: read_table(path) for path in files}

    where = defaultdict(list)
    for path, (_, rows) in tables.items():
        for r in rows:
            if PHONE_RE.match(r["phone"]):
                where[r["phone"]].append((path, r))
    counts = Counter({p: len(v) for p, v in where.items()})

    flagged = 0
    for a, b in combinations(sorted(where), 2):
        if not _one_digit_apart(a, b):
            continue
        suspects = [a, b] if counts[a] == counts[b] else [min(a, b, key=counts.__getitem__)]
        for s in suspects:
            other = b if s == a else a
            seen = " ".join(f"{page_number(p.stem)}:{r['row']}" for p, r in where[other])
            for _, r in where[s]:
                note = f"near-dup of {other} ({seen})"
                if note not in r.get("notes", ""):
                    r["notes"] = "; ".join(x for x in (r.get("notes", ""), note) if x)
                    r["recheck"] = "true"
                    flagged += 1
                    log(f"  {page_number(path.stem)}:{r['row']} {s} is {note}")

    for path, (fieldnames, rows) in tables.items():
        if "notes" not in fieldnames:
            fieldnames.insert(fieldnames.index("raw") if "raw" in fieldnames else len(fieldnames), "notes")
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
    log(f"crosscheck: {len(files)} files, {len(where)} distinct phones, "
        f"{flagged} rows flagged as near-duplicates")
    return flagged
