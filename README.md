# transcribe

## Setup

| Command | What it does |
|---|---|
| `brew install poppler` | Installs `pdftoppm` (PDF to image). |
| `uv sync` | Creates `.venv` and installs the project and its dependencies. |
| `uv run hf download mlx-community/Qwen3.5-9B-MLX-8bit` | Downloads the VLM (~10.5 GB) into the Hugging Face cache. |

## PDF to images

| Command | What it does |
|---|---|
| `pdftoppm -png "<file>.pdf" input/pages` | Writes one PNG per PDF page to `input/pages-1.png`, `input/pages-2.png`, ... |

## Pipeline

| Command | What it does |
|---|---|
| `uv run transcribe run` | Runs calibrate, slice, dictionary, extract and crosscheck on every image in `input/`. |
| `uv run python main.py` | Same as `uv run transcribe run`. |
| `uv run transcribe run --skip-dictionary` | Same, but reuses the existing `dictionary/locations.json`. |
| `uv run transcribe run --combine` | Same, and also writes `output/combined.csv`. |
| `uv run transcribe calibrate` | Detects row lines and columns per page and writes `config/layout.json`. Skips pages with `"locked": true`. |
| `uv run transcribe calibrate --force` | Same, including locked pages. |
| `uv run transcribe slice` | Writes `verification/<page>/overlay.png` and the `rows/`, `col2/`, `col3/` crops. |
| `uv run transcribe dictionary` | Reads every location crop and writes `dictionary/col2_reads.csv`, `dictionary/candidates.csv` (with counts), and seeds `dictionary/locations.json` if missing. |
| `uv run transcribe extract` | Reads every row crop plus a second phone-only read and writes `output/output-<n>.csv` and `output/output-<n>.summary.json`. |
| `uv run transcribe crosscheck` | Marks rows whose phone differs by one digit from another phone in any page for recheck. |
| `uv run transcribe combine` | Merges all `output/output-*.csv` into `output/combined.csv` with a page column. |

## Flags

| Flag | What it does |
|---|---|
| `--pages 1 2` | Limits a command to these page numbers or input file stems. |
| `--backend mlx` / `--backend mock` | Uses the local model, or a fake model for dry runs. |
| `--model <hf-id>` | Uses a different MLX model. |
| `--workers N` | (`extract` only) Processes N pages in parallel; each loads its own model copy. |
| `--margin-factor F` | (`calibrate`, `run`) Crop overlap is row height / F above and below each row. |

## Manual overrides

| Path | What it does |
|---|---|
| `manual/<page>/rows/row_XX.png` | Replaces the generated full-row crop for that row. |
| `manual/<page>/col2/row_XX.png` | Replaces the generated location crop for that row. |
| `manual/<page>/col3/row_XX.png` | Replaces the generated phone crop for that row. |
| `config/layout.json` | Per-page geometry; edit by hand and set `"locked": true` to keep it. |
| `dictionary/locations.json` | Allowed locations and `aliases` (misreading to canonical). |
