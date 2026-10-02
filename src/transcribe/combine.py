"""Final step (run only after manual review): merge output-*.csv into output/combined.csv
with the page number on every line."""

import csv

from transcribe.crosscheck import read_table
from transcribe.paths import OUTPUT_DIR, page_number


def combine() -> int:
    files = sorted(OUTPUT_DIR.glob("output-*.csv"), key=lambda p: page_number(p.stem))
    out = OUTPUT_DIR / "combined.csv"
    n = 0
    with out.open("w", newline="") as fo:
        writer = None
        for path in files:
            fieldnames, rows = read_table(path)
            if writer is None:
                writer = csv.DictWriter(fo, fieldnames=["page", *fieldnames], extrasaction="ignore")
                writer.writeheader()
            for rec in rows:
                writer.writerow({"page": page_number(path.stem), **rec})
                n += 1
    print(f"combined {len(files)} pages, {n} rows -> {out}")
    return n
