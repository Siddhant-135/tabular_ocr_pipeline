"""Cut each page into 31 row strips and 31 column-2 strips, plus a verification overlay.

verification/<page>/
    overlay.png     page with red nominal row lines, green row x-extent, blue col-2 band
    rows/row_XX.png full-width row crops (with overlap margins) -> main VLM pass
    col2/row_XX.png location-column crops                     -> dictionary pass
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from transcribe.layout import PageLayout
from transcribe.paths import COL2, MANUAL_DIR, ROWS, VERIFICATION_DIR, crop_dir, crop_name

RED = (230, 0, 0)
GREEN = (0, 170, 0)
BLUE = (0, 90, 255)


def slice_page(path: Path, layout: PageLayout) -> dict[str, int]:
    page_id = path.stem
    img = Image.open(path).convert("RGB")

    counts = {}
    for kind, box_fn in ((ROWS, layout.row_box), (COL2, layout.col2_box)):
        out = crop_dir(page_id, kind)
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("row_*.png"):
            old.unlink()
        for i in range(layout.n_rows):
            img.crop(box_fn(i)).save(out / crop_name(i))
        counts[kind] = layout.n_rows

    draw_overlay(img, layout, page_id).save(VERIFICATION_DIR / page_id / "overlay.png")
    return counts


def draw_overlay(img: Image.Image, layout: PageLayout, page_id: str) -> Image.Image:
    over = img.copy()
    d = ImageDraw.Draw(over)
    font = ImageFont.load_default(size=max(14, round(layout.row_h * 0.45)))

    for i in range(layout.n_rows):
        top, bottom = layout.row_band(i)
        d.line([(0, top), (layout.width, top)], fill=RED, width=2)
        if i == layout.n_rows - 1:
            d.line([(0, bottom), (layout.width, bottom)], fill=RED, width=2)
        label = f"{i + 1}" + ("*" if _has_manual(page_id, i) else "")
        d.text((4, top + 2), label, fill=RED, font=font)

    y0, y1 = layout.row_band(0)[0], layout.row_band(layout.n_rows - 1)[1]
    for x in (layout.x_left, layout.x_right):
        d.line([(x, y0), (x, y1)], fill=GREEN, width=2)
    for x in (layout.col2_x0, layout.col2_x1):
        d.line([(x, y0), (x, y1)], fill=BLUE, width=3)
    return over


def _has_manual(page_id: str, i: int) -> bool:
    return any((MANUAL_DIR / page_id / kind / crop_name(i)).exists() for kind in (ROWS, COL2))
