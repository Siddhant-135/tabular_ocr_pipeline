"""One-shot pipeline: every image in input/ -> calibrate, slice, dictionary, extract, crosscheck."""

import json
import time

from PIL import Image

from transcribe.calibrate import calibrate_page
from transcribe.crosscheck import crosscheck
from transcribe.dictionary import build, load_dictionary
from transcribe.extract import extract_page_with_backend
from transcribe.layout import DEFAULT_MARGIN_FACTOR, is_locked, load_layout, save_layout
from transcribe.paths import LAYOUT_FILE, list_pages
from transcribe.slicing import slice_page
from transcribe.vlm import get_backend


def run_all(
    *,
    pages: list[str] | None = None,
    backend: str = "mlx",
    model: str | None = None,
    margin_factor: float = DEFAULT_MARGIN_FACTOR,
    force_calibrate: bool = False,
    skip_dictionary: bool = False,
    combine: bool = False,
) -> list[dict]:
    paths = list_pages(pages)
    if not paths:
        raise SystemExit(f"no images in input/ (looked for {pages or 'all pages'})")
    page_ids = [p.stem for p in paths]
    t0 = time.time()

    for path in paths:
        if is_locked(path.stem) and not force_calibrate:
            print(f"calibrate {path.stem}: locked, skipped")
            continue
        layout, report = calibrate_page(path, margin_factor)
        save_layout(path.stem, layout)
        print(f"calibrate {path.stem}: {report}")

    for path in paths:
        with Image.open(path) as im:
            w, h = im.size
        print(f"slice {path.stem}: {slice_page(path, load_layout(path.stem, w, h))}")
    print(f"geometry -> {LAYOUT_FILE}, crops -> verification/")

    t = time.time()
    vlm = get_backend(backend, model)
    print(f"model loaded ({backend}) in {time.time() - t:.1f}s")

    if not skip_dictionary:
        build(vlm, page_ids)

    dictionary = load_dictionary()
    summaries = []
    for n, page_id in enumerate(page_ids, 1):
        t = time.time()
        summaries.append(extract_page_with_backend(page_id, vlm, dictionary, progress=True))
        print(f"extract {page_id} ({n}/{len(page_ids)}) in {time.time() - t:.1f}s")

    crosscheck()

    if combine:
        from transcribe.combine import combine as combine_outputs

        combine_outputs()

    print(f"done: {len(page_ids)} page(s) in {time.time() - t0:.1f}s")
    for s in summaries:
        print(json.dumps({k: v for k, v in s.items() if k != "locations"}))
    return summaries
