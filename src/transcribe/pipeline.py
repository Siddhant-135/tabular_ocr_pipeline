"""One-shot pipeline: every image in input/ -> calibrate, slice, dictionary, extract, crosscheck."""

import json
import time
from pathlib import Path

from PIL import Image

from transcribe.layout import DEFAULT_MARGIN_FACTOR, is_locked, load_layout, save_layout
from transcribe.paths import LAYOUT_FILE, list_pages
from transcribe.progress import log, stage


def calibrate_pages(paths: list[Path], margin_factor: float, force: bool = False) -> None:
    from transcribe.calibrate import calibrate_page

    for n, path in enumerate(paths, 1):
        if is_locked(path.stem) and not force:
            log(f"calibrate {path.stem} ({n}/{len(paths)}): locked, skipped")
            continue
        t = time.time()
        layout, report = calibrate_page(path, margin_factor)
        save_layout(path.stem, layout)
        log(f"calibrate {path.stem} ({n}/{len(paths)}) done in {time.time() - t:.1f}s: "
            f"start_h={layout.start_h} row_h={layout.row_h} "
            f"col2=[{layout.col2_x0},{layout.col2_x1}] row_confidence={report['row_confidence']} "
            f"columns_detected={report['columns_detected']}")
    log(f"geometry written to {LAYOUT_FILE}")


def slice_pages(paths: list[Path]) -> None:
    from transcribe.slicing import slice_page

    for n, path in enumerate(paths, 1):
        t = time.time()
        with Image.open(path) as im:
            w, h = im.size
        counts = slice_page(path, load_layout(path.stem, w, h))
        log(f"slice {path.stem} ({n}/{len(paths)}) done in {time.time() - t:.1f}s: {counts} "
            f"-> verification/{path.stem}/")


def run_all(
    *,
    pages: list[str] | None = None,
    backend: str = "mlx",
    model: str | None = None,
    margin_factor: float = DEFAULT_MARGIN_FACTOR,
    force_calibrate: bool = False,
    skip_dictionary: bool = False,
) -> list[dict]:
    from transcribe.crosscheck import crosscheck
    from transcribe.dictionary import build, load_dictionary
    from transcribe.extract import extract_page_with_backend
    from transcribe.vlm import get_backend

    paths = list_pages(pages)
    if not paths:
        raise SystemExit(f"no images in input/ (looked for {pages or 'all pages'})")
    page_ids = [p.stem for p in paths]
    n_stages = 5
    t0 = time.time()
    log(f"run: {len(paths)} page(s): {', '.join(page_ids)}")

    stage(1, n_stages, "calibrate", f"{len(paths)} pages")
    calibrate_pages(paths, margin_factor, force_calibrate)

    stage(2, n_stages, "slice + verification images", f"{len(paths)} pages")
    slice_pages(paths)

    vlm = get_backend(backend, model)

    if skip_dictionary:
        stage(3, n_stages, "dictionary", "skipped, reusing dictionary/locations.json")
    else:
        stage(3, n_stages, "dictionary", f"{len(paths)} pages x 31 location crops")
        build(vlm, page_ids)

    stage(4, n_stages, "extract", f"{len(paths)} pages x 31 rows")
    dictionary = load_dictionary()
    summaries = []
    for n, page_id in enumerate(page_ids, 1):
        log(f"extract {page_id} ({n}/{len(page_ids)}) started")
        summaries.append(extract_page_with_backend(page_id, vlm, dictionary))

    stage(5, n_stages, "crosscheck", "near-duplicate phones across pages")
    crosscheck()

    log(f"done: {len(page_ids)} page(s) in {time.time() - t0:.0f}s")
    for s in summaries:
        print(json.dumps({k: v for k, v in s.items() if k != "locations"}), flush=True)
    return summaries
