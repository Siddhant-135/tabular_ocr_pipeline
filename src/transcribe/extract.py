"""Main pass: one VLM call per row crop -> output/output-<n>.csv (one file per page).

Per row:
  1st pass valid                -> recheck=False, checks_failed=""
  1st pass invalid, 2nd valid   -> recheck=True,  checks_failed=""
  both invalid                  -> recheck=True,  checks_failed="phone;..." and those fields NaN
A field that was valid in either pass is kept (2nd pass preferred).
"""

import csv
import json
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from transcribe.checks import FIELDS, NAN, failed_fields, normalize_row
from transcribe.dictionary import LocationDictionary, load_dictionary
from transcribe.layout import N_ROWS
from transcribe.paths import OUTPUT_DIR, ROWS, output_csv, resolve_crop
from transcribe.prompts import retry_prompt, row_prompt
from transcribe.vlm import VLMBackend, get_backend

COLUMNS = ["row", "name", "location", "dictionary_key", "phone", "recheck", "checks_failed", "raw"]


@dataclass
class RowResult:
    row: int
    name: str
    location: str
    dictionary_key: str
    phone: str
    recheck: bool
    checks_failed: list[str]
    raw: str


def parse_answer(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def read_row(backend: VLMBackend, page_id: str, i: int, dictionary: LocationDictionary) -> RowResult:
    image = resolve_crop(page_id, ROWS, i)

    raw1 = backend.generate(image, row_prompt(dictionary.locations))
    first = normalize_row(parse_answer(raw1))
    failed1 = failed_fields(first)
    final, failed, raws = first, failed1, [raw1]

    if failed1:
        raw2 = backend.generate(image, retry_prompt(dictionary.locations, raw1, failed1))
        second = normalize_row(parse_answer(raw2))
        failed2 = failed_fields(second)
        raws.append(raw2)
        final, failed = {}, []
        for f in FIELDS:
            if f not in failed2:
                final[f] = second[f]
            elif f not in failed1:
                final[f] = first[f]
            else:
                final[f] = NAN
                failed.append(f)

    key = dictionary.lookup(final["location"]) if final["location"] != NAN else None
    return RowResult(
        row=i + 1,
        name=final["name"],
        location=key or final["location"],
        dictionary_key=key or "",
        phone=final["phone"],
        recheck=bool(failed1),
        checks_failed=failed,
        raw=" || ".join(r.replace("\n", " ") for r in raws),
    )


def extract_page(page_id: str, backend_name: str, model: str | None = None) -> dict:
    backend = get_backend(backend_name, model)
    dictionary = load_dictionary()
    results = [read_row(backend, page_id, i, dictionary) for i in range(N_ROWS)]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = output_csv(page_id)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in results:
            w.writerow([r.row, r.name, r.location, r.dictionary_key, r.phone,
                        str(r.recheck).lower(), ";".join(r.checks_failed), r.raw])

    summary = {
        "page": page_id,
        "file": path.name,
        "rows": len(results),
        "ok_first_pass": sum(not r.recheck for r in results),
        "recheck": sum(r.recheck for r in results),
        "checks_failed": sum(bool(r.checks_failed) for r in results),
        "failed_by_field": dict(Counter(f for r in results for f in r.checks_failed)),
        "in_dictionary": sum(bool(r.dictionary_key) for r in results),
        "locations": dict(Counter(r.location for r in results).most_common()),
    }
    path.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def extract_pages(page_ids: list[str], backend_name: str, model: str | None, workers: int) -> list[dict]:
    """Parallel across files only. Each worker loads its own model copy, so keep workers
    small for local models (an 8B model at 8-bit is ~9 GB of unified memory)."""
    if workers <= 1:
        return [extract_page(p, backend_name, model) for p in page_ids]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(extract_page, page_ids, [backend_name] * len(page_ids), [model] * len(page_ids)))
