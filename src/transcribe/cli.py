"""Pipeline entry point.

    uv run transcribe run                  # everything below in one go, for all of input/
    uv run transcribe calibrate            # suggest row/column geometry -> config/layout.json
    uv run transcribe slice                # crops + overlays -> verification/<page>/
    uv run transcribe dictionary           # col-2 pass -> dictionary/ (then edit locations.json)
    uv run transcribe extract              # row pass + phone second read -> output/output-<n>.csv
    uv run transcribe crosscheck           # optional: flag likely OCR digit swaps across pages

Common flags: --pages 1 2 (page numbers or file stems), --backend mlx|mock, --model <id>.
"""

import argparse
import json

from transcribe.layout import DEFAULT_MARGIN_FACTOR
from transcribe.paths import list_pages


def cmd_calibrate(args):
    from transcribe.pipeline import calibrate_pages

    calibrate_pages(list_pages(args.pages), args.margin_factor, args.force)


def cmd_slice(args):
    from transcribe.pipeline import slice_pages

    slice_pages(list_pages(args.pages))


def cmd_dictionary(args):
    from transcribe.dictionary import build
    from transcribe.vlm import get_backend

    build(get_backend(args.backend, args.model), [p.stem for p in list_pages(args.pages)])


def cmd_extract(args):
    from transcribe.extract import extract_pages

    pages = [p.stem for p in list_pages(args.pages)]
    for s in extract_pages(pages, args.backend, args.model, args.workers):
        print(json.dumps({k: v for k, v in s.items() if k != "locations"}))


def cmd_crosscheck(args):
    from transcribe.crosscheck import crosscheck

    crosscheck()


def cmd_run(args):
    from transcribe.pipeline import run_all

    run_all(
        pages=args.pages,
        backend=args.backend,
        model=args.model,
        margin_factor=args.margin_factor,
        force_calibrate=args.force,
        skip_dictionary=args.skip_dictionary,
    )


def main(argv=None):
    p = argparse.ArgumentParser(prog="transcribe", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, vlm=False):
        sp = sub.add_parser(name)
        sp.add_argument("--pages", nargs="*", help="page numbers or input file stems (default: all)")
        if vlm:
            sp.add_argument("--backend", default="mlx", choices=["mlx", "mock"])
            sp.add_argument("--model", default=None)
        sp.set_defaults(fn=fn)
        return sp

    r = add("run", cmd_run, vlm=True)
    r.add_argument("--margin-factor", type=float, default=DEFAULT_MARGIN_FACTOR)
    r.add_argument("--force", action="store_true", help="re-calibrate locked pages")
    r.add_argument("--skip-dictionary", action="store_true", help="reuse dictionary/ from a prior run")
    c = add("calibrate", cmd_calibrate)
    c.add_argument("--margin-factor", type=float, default=DEFAULT_MARGIN_FACTOR)
    c.add_argument("--force", action="store_true", help="also overwrite locked pages")
    add("slice", cmd_slice)
    add("dictionary", cmd_dictionary, vlm=True)
    e = add("extract", cmd_extract, vlm=True)
    e.add_argument("--workers", type=int, default=1, help="parallel pages (each loads the model)")
    add("crosscheck", cmd_crosscheck)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
