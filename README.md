# transcribe

Handwritten diary pages → per-page CSV in `output/`. You review and export from `final_output/` by hand (not wired to the pipeline).

## Setup

| Command | What it does |
|---|---|
| `brew install poppler` | Installs `pdftoppm` (PDF to image). |
| `uv sync` | Creates `.venv` and installs dependencies. |
| `uv run hf download mlx-community/Qwen3.5-9B-MLX-8bit` | Downloads the VLM (~10.5 GB). Use a smaller MLX build if RAM is tight. |

## PDF to images

| Command | What it does |
|---|---|
| `pdftoppm -png "<file>.pdf" input/pages` | Writes `input/pages-01.png`, `input/pages-02.png`, … |

## Pipeline

| Command | What it does |
|---|---|
| `uv run transcribe run` | Calibrate → slice → dictionary → extract → crosscheck for every file in `input/`. |
| `uv run python main.py` | Same as `uv run transcribe run`. |
| `uv run transcribe run --skip-dictionary` | Reuses `dictionary/locations.json`; skips the location-column VLM pass. |
| `uv run transcribe calibrate` | Row/column geometry → `config/layout.json`. Skips pages with `"locked": true`. |
| `uv run transcribe calibrate --force` | Same, including locked pages. |
| `uv run transcribe slice` | `verification/<page>/overlay.png` and `rows/`, `col2/`, `col3/` crops. |
| `uv run transcribe dictionary` | Location crops → `dictionary/col2_reads.csv`, `candidates.csv`; seeds `locations.json` if missing. |
| `uv run transcribe extract` | Row crops + phone second read → `output/output-<n>.csv` and `.summary.json`. |
| `uv run transcribe crosscheck` | Re-scans all `output/output-*.csv` for one-digit-apart phone pairs; sets `recheck` + `notes`. |

## Review and export (manual)

| Command | What it does |
|---|---|
| `cp output/output-*.csv final_output/` | You copy what you want to review. Nothing in the repo writes here automatically. |
| `python final_output/clipper.py` | After your edits: `final_output/clipped/<file>.csv` with columns `name`, `place`, `phone` only. |
| `python final_output/clipper.py output-1.csv` | Same for named files. |

## Flags

| Flag | What it does |
|---|---|
| `--pages 1 2` | Limit to page numbers or stems (e.g. `pages-01`). |
| `--backend mlx` / `mock` | Real VLM or dry-run fake backend. |
| `--model <hf-id>` | Override MLX model id. |
| `--workers N` | (`extract`) Parallel pages; each worker loads its own model. |
| `--margin-factor F` | Row crop overlap = row height / F. |

## Manual overrides

| Path | What it does |
|---|---|
| `manual/<page>/rows/row_XX.png` | Replace generated full-row crop. |
| `manual/<page>/col2/row_XX.png` | Replace location crop. |
| `manual/<page>/col3/row_XX.png` | Replace phone crop. |
| `config/layout.json` | Per-page pixels; `"locked": true` keeps calibrate from overwriting. |
| `dictionary/locations.json` | Canonical locations + `aliases`. |

---

## Technical overview

### Libraries

| Layer | Library | Role |
|---|---|---|
| Runtime / deps | **uv**, **Python 3.12+** | Environment and CLI entry (`transcribe` script). |
| Arrays / geometry | **NumPy** | Row-line search, ink profiles, column valleys (`calibrate.py`). |
| Images | **Pillow (PIL)** | Load pages, crop strips, draw verification overlay, save PNGs. |
| VLM inference | **mlx-vlm**, **MLX** (Apple Silicon) | Load `Qwen3.5-9B-MLX-8bit`; greedy decode on crop images. |
| VLM stack (transitive) | **transformers**, **opencv-python**, etc. | Pulled in by mlx-vlm; OpenCV used only for ad-hoc CLAHE tests, not in the default pipeline. |
| PDF input | **poppler** (`pdftoppm`, system) | External; not a Python dependency. |

### Process specification

1. **Input** — PNG/JPEG in `input/`. One file = one diary page (~31 handwritten rows). Page id = filename stem; page number = trailing digits (`pages-01` → `1`).

2. **Calibrate** (`calibrate.py`, `layout.py`) — Per page, independently:
   - **Rows:** Score horizontal bands for faint ruled lines; search `start_h` and `row_h` so 32 lines best match; 31 data rows between them.
   - **Columns:** Vertical ink profile in the row band; three ink clusters, or one wide span with two valleys (cream paper / bleed-through). Yields `x_left`, `x_right`, `col2_x0`, `col2_x1`. Stored in `config/layout.json`.
   - **Overlap:** Each row crop extends `row_h / margin_factor` above/below (default factor 4).

3. **Slice** (`slicing.py`) — For each page: 31× `rows/` (full width), 31× `col2/` (location), 31× `col3/` (phone column, 2× upscale). `overlay.png` for visual QA. Manual crops in `manual/` override generated paths (`paths.resolve_crop`).

4. **Dictionary pass** (`dictionary.py`, `prompts.col2_prompt`) — VLM reads each `col2` crop; normalize `Ph-11` / `Sec-49` etc.; aggregate counts → `dictionary/candidates.csv`. `locations.json` is edited by you; used to guide the row prompt and fill `dictionary_key`.

5. **Extract pass** (`extract.py`, `checks.py`) — Per row:
   - VLM on `rows/` crop → JSON `{name, location, phone}`; regex validation; optional retry prompt if invalid.
   - **Phone:** Second VLM read on enlarged `col3/` crop. If it disagrees with the row read, keep the crop read, set `recheck=true`, put both values in `notes` (human review, not auto-correction).
   - **Missing phone:** Model `null` / blank → `phone=NaN`, no `checks_failed` for phone; name and location still kept.
   - **Failed parse:** Field → `NaN`, listed in `checks_failed`, `recheck=true`.

6. **Crosscheck** (`crosscheck.py`, optional, runs at end of `run`) — Across all `output/output-*.csv`: if two 10-digit phones differ in exactly one digit, flag the less frequent (or both if tied) with `recheck=true` and a `near-dup of …` note. Catches likely digit swaps when the same contact repeats; does not change values.

7. **Output schema** — `output/output-<n>.csv`: `row`, `name`, `location`, `dictionary_key`, `phone`, `recheck`, `checks_failed`, `notes`, `raw`. Summary JSON with counts.

8. **Final export** — No code path from `output/` to `final_output/`. You copy, edit, then run `final_output/clipper.py` locally.

### Image preprocessing (CLAHE)

Tested CLAHE (L-channel, clip 2.0) on the new cream-paper scans vs raw crops: **same location reads** on sample rows; **not enabled** in the pipeline. What mattered for the darker scans was **column detection** (valley fallback when ink is one continuous span). Always check `verification/<page>/overlay.png` after calibrate/slice.

### Ready to run

- 30 pages in `input/` (`pages-01` … `pages-30`).
- Re-run geometry after the calibrate fix: `uv run transcribe run` (long run: ~31 rows × 2–3 VLM calls × 30 pages) or calibrate+slice first on one page.
- First full book: run dictionary once, fix `dictionary/locations.json`, then `uv run transcribe run --skip-dictionary` for extract-only passes.
