"""Suggest a PageLayout per page from the image itself.

Rows: the diary has faint grey ruled lines; we fit an arithmetic progression of
N_ROWS + 1 lines to the "light grey" row profile.
Columns: the handwriting's vertical ink profile has three clusters,
name | location | phone; column 2 is cut from the end of cluster 1 to the start of
cluster 3 (i.e. col 1 and col 3 are cut off, the gaps are kept as margin).

The result is only a suggestion: always eyeball verification/<page>/overlay.png.
"""

import numpy as np
from PIL import Image

from transcribe.layout import (
    DEFAULT_FRACTIONS,
    DEFAULT_MARGIN_FACTOR,
    N_ROWS,
    PageLayout,
)

INK_THRESHOLD = 140  # grayscale; ruled lines are ~180-220, pen ink is darker
START_SEARCH = (0.11, 0.15)  # fraction of height; narrow enough to avoid off-by-one-row fits
ROW_H_SEARCH = (0.024, 0.030)


def _smooth(x: np.ndarray, k: int) -> np.ndarray:
    return np.convolve(x, np.ones(k) / k, mode="same")


def _max_filter(x: np.ndarray, k: int) -> np.ndarray:
    pad = k // 2
    xp = np.pad(x, pad, mode="edge")
    return np.lib.stride_tricks.sliding_window_view(xp, k).max(axis=1)


def fit_rows(rgb: np.ndarray) -> tuple[float, float, float]:
    """Return (start_h, row_h, confidence). Confidence ~ line strength at fit / background."""
    h, w, _ = rgb.shape
    mx, mn = rgb.max(-1), rgb.min(-1)
    light_grey = ((mx - mn) < 35) & (mx > 120) & (mx < 235)
    prof = light_grey[:, int(0.1 * w) : int(0.9 * w)].mean(1)
    prof_max = _max_filter(prof, 5)

    starts = np.arange(START_SEARCH[0] * h, START_SEARCH[1] * h, 1.0)
    row_hs = np.arange(ROW_H_SEARCH[0] * h, ROW_H_SEARCH[1] * h, 0.05)
    k = np.arange(N_ROWS + 1)
    idx = np.rint(starts[:, None, None] + row_hs[None, :, None] * k).astype(int)
    idx = np.clip(idx, 0, h - 1)
    score = prof_max[idx].sum(-1)
    si, ri = np.unravel_index(np.argmax(score), score.shape)
    confidence = float(score[si, ri] / (N_ROWS + 1) / (np.median(prof) + 1e-6))
    return float(starts[si]), float(row_hs[ri]), confidence


def _runs(mask: np.ndarray) -> list[list[int]]:
    runs, start = [], None
    for x, v in enumerate(mask):
        if v and start is None:
            start = x
        elif not v and start is not None:
            runs.append([start, x])
            start = None
    if start is not None:
        runs.append([start, len(mask)])
    return runs


def fit_columns(gray: np.ndarray, y0: int, y1: int) -> dict[str, int] | None:
    """Three heaviest ink clusters = name | location | phone. None if not found."""
    w = gray.shape[1]
    prof = _smooth((gray[y0:y1] < INK_THRESHOLD).mean(0), 15)
    high = float(np.percentile(prof[int(0.05 * w) : int(0.95 * w)], 90))

    merged = []
    for r in _runs(prof > 0.1 * high):
        if merged and r[0] - merged[-1][1] < 0.02 * w:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    # Clusters touching the border are scanner edge shadows or diary month tabs.
    inner = [r for r in merged if r[0] > 0.01 * w and r[1] < 0.99 * w]
    clusters = sorted(sorted(inner, key=lambda r: -prof[r[0] : r[1]].sum())[:3])
    if len(clusters) < 3:
        return None
    (c1, _), (_, _), (c3_start, c3_end) = clusters
    pad = int(0.03 * w)
    return {
        "x_left": max(0, c1 - pad),
        "x_right": min(w, c3_end + pad),
        "col2_x0": clusters[0][1],
        "col2_x1": c3_start,
    }


def calibrate_page(path, margin_factor: float = DEFAULT_MARGIN_FACTOR) -> tuple[PageLayout, dict]:
    img = Image.open(path)
    rgb = np.asarray(img.convert("RGB")).astype(int)
    gray = np.asarray(img.convert("L")).astype(int)
    h, w = gray.shape

    start_h, row_h, conf = fit_rows(rgb)
    cols = fit_columns(gray, int(start_h), int(start_h + N_ROWS * row_h))
    columns_detected = cols is not None
    if cols is None:
        fallback = PageLayout.from_defaults(w, h)
        cols = {k: getattr(fallback, k) for k in ("x_left", "x_right", "col2_x0", "col2_x1")}
    layout = PageLayout(
        width=w,
        height=h,
        start_h=round(start_h, 1),
        row_h=round(row_h, 2),
        margin_factor=margin_factor,
        **cols,
    )
    report = {
        "row_confidence": round(conf, 2),
        "columns_detected": columns_detected,
        "start_h_frac": round(start_h / h, 4),
        "row_h_frac": round(row_h / h, 4),
        "col2_frac": (round(cols["col2_x0"] / w, 3), round(cols["col2_x1"] / w, 3)),
        "default_col2_frac": (DEFAULT_FRACTIONS["col2_x0"], DEFAULT_FRACTIONS["col2_x1"]),
    }
    return layout, report
