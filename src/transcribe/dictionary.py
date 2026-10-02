"""Location dictionary (column 2).

Pass 1 (`build`): read every col2 crop with the VLM, normalise (SecXY -> Sec-XY, PhXY -> Ph-XY)
and count. Writes
    dictionary/col2_reads.csv   one line per crop
    dictionary/candidates.csv   unique values with counts and where they occur
and seeds dictionary/locations.json if it does not exist yet.

You then hand-edit locations.json once:
    {"locations": ["Ph-11", "Sec-49", "Vill", ...],
     "aliases":   {"Bhawani Mnl": "BhawanMnl", ...}}   # misreading -> canonical entry
The main extraction pass uses it to guide the VLM and to fill `dictionary_key`.
"""

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from transcribe.checks import location_kind, normalize_location
from transcribe.layout import N_ROWS
from transcribe.paths import (
    CANDIDATES_FILE,
    COL2,
    DICTIONARY_DIR,
    LOCATIONS_FILE,
    page_number,
    resolve_crop,
)
from transcribe.prompts import col2_prompt
from transcribe.vlm import VLMBackend


@dataclass
class LocationDictionary:
    locations: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self._index = {loc.lower(): loc for loc in self.locations}
        for alias, target in self.aliases.items():
            self._index[normalize_location(alias).lower()] = target

    def lookup(self, location: str) -> str | None:
        """Canonical dictionary key for a normalised location, or None (not in dictionary)."""
        return self._index.get(location.lower()) if location else None


def load_dictionary() -> LocationDictionary:
    if not LOCATIONS_FILE.exists():
        return LocationDictionary()
    raw = json.loads(LOCATIONS_FILE.read_text())
    return LocationDictionary(raw.get("locations", []), raw.get("aliases", {}))


def build(backend: VLMBackend, page_ids: list[str]) -> Counter:
    DICTIONARY_DIR.mkdir(parents=True, exist_ok=True)
    prompt = col2_prompt()
    reads = []
    for page_id in page_ids:
        for i in range(N_ROWS):
            raw = backend.generate(resolve_crop(page_id, COL2, i), prompt, max_tokens=16).strip()
            norm = "" if raw.upper() in {"", "NONE", "NULL"} else normalize_location(raw)
            reads.append((page_id, i + 1, raw, norm))

    with (DICTIONARY_DIR / "col2_reads.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["page", "row", "raw", "normalized"])
        w.writerows(reads)

    counts = Counter(norm for *_, norm in reads if norm)
    where = defaultdict(list)
    variants = defaultdict(set)
    for page_id, row, raw, norm in reads:
        if norm:
            where[norm].append(f"{page_number(page_id)}:{row}")
            variants[norm].add(raw)

    with CANDIDATES_FILE.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["value", "kind", "count", "page:row", "raw_variants"])
        for value, n in counts.most_common():
            w.writerow([value, location_kind(value), n, " ".join(where[value]), " | ".join(sorted(variants[value]))])

    if not LOCATIONS_FILE.exists():
        seed = sorted(v for v in counts if location_kind(v) != "invalid")
        LOCATIONS_FILE.write_text(json.dumps({"locations": seed, "aliases": {}}, indent=2) + "\n")

    empty = sum(1 for *_, norm in reads if not norm)
    print(f"col2 reads: {len(reads)}  empty: {empty}  unique values: {len(counts)}")
    for value, n in counts.most_common():
        print(f"  {n:4d}  {value}")
    known = load_dictionary()
    unknown = [v for v in counts if known.lookup(v) is None]
    if unknown:
        print(f"not yet in {LOCATIONS_FILE.name}: {unknown}")
    return counts
