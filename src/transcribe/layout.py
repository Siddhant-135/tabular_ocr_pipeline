"""Per-page geometry: where the 31 rows and the location column sit.

Stored in config/layout.json. Per-page values are in pixels of that page's image;
`defaults` are fractions of width/height, used for pages that were never calibrated.
Set "locked": true on a page after hand-tuning so `calibrate` won't overwrite it.
"""

import json
from dataclasses import asdict, dataclass, fields

from transcribe.paths import LAYOUT_FILE

N_ROWS = 31

DEFAULT_FRACTIONS = {
    "start_h": 0.13,
    "row_h": 0.027,
    "x_left": 0.02,
    "x_right": 0.97,
    "col2_x0": 0.40,
    "col2_x1": 0.72,
}
DEFAULT_MARGIN_FACTOR = 4.0


@dataclass
class PageLayout:
    width: int
    height: int
    start_h: float
    row_h: float
    x_left: int
    x_right: int
    col2_x0: int
    col2_x1: int
    n_rows: int = N_ROWS
    # Each crop extends row_h / margin_factor above and below its nominal band.
    margin_factor: float = DEFAULT_MARGIN_FACTOR
    locked: bool = False

    def row_band(self, i: int) -> tuple[int, int]:
        top = self.start_h + i * self.row_h
        return round(top), round(top + self.row_h)

    def _vertical_extent(self, i: int) -> tuple[int, int]:
        m = self.row_h / self.margin_factor
        top = self.start_h + i * self.row_h - m
        bottom = self.start_h + (i + 1) * self.row_h + m
        return max(0, round(top)), min(self.height, round(bottom))

    def row_box(self, i: int) -> tuple[int, int, int, int]:
        y0, y1 = self._vertical_extent(i)
        return self.x_left, y0, self.x_right, y1

    def col2_box(self, i: int) -> tuple[int, int, int, int]:
        y0, y1 = self._vertical_extent(i)
        return self.col2_x0, y0, self.col2_x1, y1

    @classmethod
    def from_defaults(cls, width: int, height: int, fractions: dict | None = None) -> "PageLayout":
        f = {**DEFAULT_FRACTIONS, **(fractions or {})}
        return cls(
            width=width,
            height=height,
            start_h=f["start_h"] * height,
            row_h=f["row_h"] * height,
            x_left=round(f["x_left"] * width),
            x_right=round(f["x_right"] * width),
            col2_x0=round(f["col2_x0"] * width),
            col2_x1=round(f["col2_x1"] * width),
            margin_factor=f.get("margin_factor", DEFAULT_MARGIN_FACTOR),
        )


def _load_raw() -> dict:
    if LAYOUT_FILE.exists():
        return json.loads(LAYOUT_FILE.read_text())
    return {"defaults": {**DEFAULT_FRACTIONS, "margin_factor": DEFAULT_MARGIN_FACTOR}, "pages": {}}


def load_layout(page_id: str, width: int, height: int) -> PageLayout:
    raw = _load_raw()
    page = raw.get("pages", {}).get(page_id)
    if page is None:
        return PageLayout.from_defaults(width, height, raw.get("defaults"))
    known = {f.name for f in fields(PageLayout)}
    layout = PageLayout(**{k: v for k, v in page.items() if k in known})
    if (layout.width, layout.height) != (width, height):
        raise ValueError(
            f"{page_id}: layout.json was calibrated for {layout.width}x{layout.height}, "
            f"image is {width}x{height}. Re-run calibrate (or unlock the page)."
        )
    return layout


def save_layout(page_id: str, layout: PageLayout) -> None:
    raw = _load_raw()
    raw.setdefault("pages", {})[page_id] = asdict(layout)
    LAYOUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAYOUT_FILE.write_text(json.dumps(raw, indent=2) + "\n")


def is_locked(page_id: str) -> bool:
    return bool(_load_raw().get("pages", {}).get(page_id, {}).get("locked"))
