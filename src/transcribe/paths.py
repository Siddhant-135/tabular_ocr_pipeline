import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = ROOT / "input"
CONFIG_DIR = ROOT / "config"
VERIFICATION_DIR = ROOT / "verification"
MANUAL_DIR = ROOT / "manual"
DICTIONARY_DIR = ROOT / "dictionary"
OUTPUT_DIR = ROOT / "output"

LAYOUT_FILE = CONFIG_DIR / "layout.json"
LOCATIONS_FILE = DICTIONARY_DIR / "locations.json"
CANDIDATES_FILE = DICTIONARY_DIR / "candidates.csv"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}

# Crop kinds: full 3-column row strips, and column-2 (location) strips.
ROWS = "rows"
COL2 = "col2"


def list_pages(only: list[str] | None = None) -> list[Path]:
    pages = sorted(
        (p for p in INPUT_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTS),
        key=lambda p: (page_number(p.stem), p.stem),
    )
    if only:
        pages = [p for p in pages if p.stem in only or str(page_number(p.stem)) in only]
    return pages


def page_number(stem: str) -> int:
    m = re.search(r"(\d+)$", stem)
    return int(m.group(1)) if m else -1


def crop_name(i: int) -> str:
    return f"row_{i + 1:02d}.png"


def crop_dir(page_id: str, kind: str) -> Path:
    return VERIFICATION_DIR / page_id / kind


def resolve_crop(page_id: str, kind: str, i: int) -> Path:
    """A hand-made crop in manual/<page>/<kind>/row_XX.png wins over the generated one."""
    manual = MANUAL_DIR / page_id / kind / crop_name(i)
    return manual if manual.exists() else crop_dir(page_id, kind) / crop_name(i)


def output_csv(page_id: str) -> Path:
    n = page_number(page_id)
    return OUTPUT_DIR / f"output-{n if n >= 0 else page_id}.csv"
