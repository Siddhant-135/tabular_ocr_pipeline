"""Main pass: one VLM call per row crop -> output/output-<n>.csv (one file per page).

Per row:
  1st pass valid                -> recheck=False, checks_failed=""
  1st pass invalid, 2nd valid   -> recheck=True,  checks_failed=""
  both invalid                  -> recheck=True,  checks_failed="phone;..." and those fields NaN
A field that was valid in either pass is kept (2nd pass preferred).

Phone second read: the enlarged phone-column crop is read on its own. If it disagrees with the
row pass, the crop reading wins (it was right in every verified disagreement on the samples),
and the row is marked recheck=true with both readings in `notes`.
"""

import csv
import json
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from transcribe.checks import FIELDS, NAN, PHONE_RE, failed_fields, normalize_phone, normalize_row
from transcribe.dictionary import LocationDictionary, load_dictionary
from transcribe.layout import N_ROWS
from transcribe.paths import COL3, OUTPUT_DIR, ROWS, output_csv, resolve_crop
from transcribe.prompts import phone_crop_prompt, retry_prompt, row_prompt
from transcribe.vlm import VLMBackend, get_backend

COLUMNS = ["row", "name", "location", "dictionary_key", "phone", "recheck", "checks_failed", "notes", "raw"]


@dataclass
class RowResult:
    row: int
    name: str
    location: str
    dictionary_key: str
    phone: str
    recheck: bool
    checks_failed: list[str]
    notes: str
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

    phone, phone_disputed, notes = verify_phone(backend, page_id, i, final["phone"])
    failed = [f for f in failed if f != "phone"] + (["phone"] if phone == NAN else [])

    key = dictionary.lookup(final["location"]) if final["location"] != NAN else None
    return RowResult(
        row=i + 1,
        name=final["name"],
        location=key or final["location"],
        dictionary_key=key or "",
        phone=phone,
        recheck=bool(failed1) or phone_disputed,
        checks_failed=failed,
        notes=notes,
        raw=" || ".join(r.replace("\n", " ") for r in raws),
    )


def _phone_read(backend: VLMBackend, image, prompt: str) -> str:
    p = normalize_phone(backend.generate(image, prompt, max_tokens=16))
    return p if PHONE_RE.match(p) else ""


def verify_phone(backend: VLMBackend, page_id: str, i: int, row_phone: str) -> tuple[str, bool, str]:
    """Return (phone, disputed, notes). Phone is NaN if no reading is a valid 10-digit number."""
    row_phone = row_phone if PHONE_RE.match(row_phone) else ""
    crop_phone = _phone_read(backend, resolve_crop(page_id, COL3, i), phone_crop_prompt())
    if row_phone and row_phone == crop_phone:
        return row_phone, False, ""
    notes = f"phone row={row_phone or 'invalid'} crop={crop_phone or 'invalid'}"
    return crop_phone or row_phone or NAN, True, notes


def extract_page_with_backend(
    page_id: str,
    backend: VLMBackend,
    dictionary: LocationDictionary | None = None,
    *,
    progress: bool = False,
) -> dict:
    dictionary = dictionary or load_dictionary()
    results = []
    for i in range(N_ROWS):
        results.append(read_row(backend, page_id, i, dictionary))
        if progress and (i + 1) % 5 == 0:
            print(f"  {page_id}: row {i + 1}/{N_ROWS}", flush=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = output_csv(page_id)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in results:
            w.writerow([r.row, r.name, r.location, r.dictionary_key, r.phone,
                        str(r.recheck).lower(), ";".join(r.checks_failed), r.notes, r.raw])

    summary = {
        "page": page_id,
        "file": path.name,
        "rows": len(results),
        "ok_first_pass": sum(not r.recheck for r in results),
        "recheck": sum(r.recheck for r in results),
        "phone_disputed": sum(r.notes.startswith("phone") for r in results),
        "checks_failed": sum(bool(r.checks_failed) for r in results),
        "failed_by_field": dict(Counter(f for r in results for f in r.checks_failed)),
        "in_dictionary": sum(bool(r.dictionary_key) for r in results),
        "locations": dict(Counter(r.location for r in results).most_common()),
    }
    path.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def extract_page(page_id: str, backend_name: str, model: str | None = None) -> dict:
    return extract_page_with_backend(page_id, get_backend(backend_name, model))


def extract_pages(page_ids: list[str], backend_name: str, model: str | None, workers: int) -> list[dict]:
    """Parallel across files only. Each worker loads its own model copy, so keep workers
    small for local models (the 9B model at 8-bit is ~11 GB of unified memory)."""
    if workers <= 1:
        backend = get_backend(backend_name, model)
        return [extract_page_with_backend(p, backend, progress=True) for p in page_ids]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(extract_page, page_ids, [backend_name] * len(page_ids), [model] * len(page_ids)))
