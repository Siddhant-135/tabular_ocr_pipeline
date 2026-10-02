"""Keep only name, place, phone from reviewed CSVs.

    python final_output/clipper.py                 # every *.csv in final_output/
    python final_output/clipper.py output-1.csv    # only these files (relative to final_output/)

Writes final_output/clipped/<same name>.csv. Rows still marked recheck=true or containing
NaN are clipped anyway but counted in the warning line.
"""

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "clipped"
KEEP = {"name": "name", "place": "location", "phone": "phone"}  # output column -> source column


def read_rows(path: Path) -> list[dict]:
    # skipinitialspace + strip: tolerate editor "align columns" padding.
    with path.open(newline="") as f:
        return [
            {k.strip(): (v or "").strip() for k, v in r.items() if k is not None}
            for r in csv.DictReader(f, skipinitialspace=True)
        ]


def clip(path: Path) -> None:
    rows = read_rows(path)
    if rows and "location" not in rows[0] and "place" in rows[0]:
        source = {**KEEP, "place": "place"}
    else:
        source = KEEP
    missing = [c for c in source.values() if rows and c not in rows[0]]
    if missing:
        print(f"{path.name}: skipped, missing columns {missing}")
        return

    out_rows = [{out: r[src] for out, src in source.items()} for r in rows]
    out_rows = [r for r in out_rows if any(r.values())]
    OUT.mkdir(exist_ok=True)
    with (OUT / path.name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(source))
        w.writeheader()
        w.writerows(out_rows)

    unreviewed = sum(r.get("recheck", "").lower() == "true" for r in rows)
    nan = sum("NaN" in r.values() for r in out_rows)
    warn = f"  (warning: {unreviewed} still recheck=true, {nan} with NaN)" if unreviewed or nan else ""
    print(f"{path.name}: {len(out_rows)} rows -> clipped/{path.name}{warn}")


def main() -> None:
    files = [HERE / a for a in sys.argv[1:]] or sorted(HERE.glob("*.csv"))
    if not files:
        print(f"no CSV files in {HERE}")
        return
    for path in files:
        clip(path)


if __name__ == "__main__":
    main()
