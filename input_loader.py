"""
input_loader.py — Kuku Promo Finder
Auto-detects the input pack (zip or folder) from the data/ directory,
or accepts a custom path via CLI argument.

Priority:
  1. --input <path> CLI argument
  2. data/*.zip     → auto-unzipped
  3. data/<folder>/ → used directly if it contains .txt files
"""

import os
import sys
import zipfile
import argparse
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data"
SUPPORTED_EXTENSIONS = {".txt"}


def find_txt_files(folder: Path) -> list:
    """Return all .txt files recursively inside folder."""
    return list(folder.rglob("episode-*.txt"))


def try_unzip(zip_path: Path, extract_to: Path) -> Path | None:
    """
    Unzip the archive and return the folder containing .txt episode files.
    Returns None if no episode .txt files are found inside.
    """
    print(f"  📦 Found zip: {zip_path.name} — extracting...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)
    print(f"  ✅ Extracted to: {extract_to}")

    # Find the subfolder that has .txt files
    txts = find_txt_files(extract_to)
    if not txts:
        return None
    # Return the common parent of all .txt files
    return txts[0].parent


def resolve_input_folder(cli_path: str | None = None) -> Path:
    """
    Resolve and return the Path to the folder containing episode .txt files.
    Raises SystemExit with a friendly message if nothing is found.
    """

    # ── 1. CLI --input argument ─────────────────────────────────────────────
    if cli_path:
        p = Path(cli_path)
        if not p.exists():
            _abort(f"Path not found: {p}")
        if p.is_file() and p.suffix == ".zip":
            extract_dir = p.parent / p.stem
            folder = try_unzip(p, extract_dir)
            if not folder:
                _abort(f"No episode-*.txt files found inside {p.name}")
            return folder
        txts = find_txt_files(p)
        if not txts:
            _abort(f"No episode-*.txt files found inside {p}")
        return p

    # ── 2. data/ directory ──────────────────────────────────────────────────
    DATA_DIR.mkdir(exist_ok=True)

    # 2a. Check for a zip file first
    zips = sorted(DATA_DIR.glob("*.zip"))
    if zips:
        zip_path = zips[0]
        extract_dir = DATA_DIR / zip_path.stem
        if extract_dir.exists():
            # Already unzipped before
            txts = find_txt_files(extract_dir)
            if txts:
                print(f"  ✅ Using previously extracted: {extract_dir.name}/")
                return txts[0].parent
        folder = try_unzip(zip_path, extract_dir)
        if not folder:
            _abort(f"No episode-*.txt files found inside {zip_path.name}")
        return folder

    # 2b. Check for a folder directly inside data/
    subfolders = [d for d in DATA_DIR.iterdir() if d.is_dir()]
    for subfolder in subfolders:
        txts = find_txt_files(subfolder)
        if txts:
            print(f"  ✅ Using folder: data/{subfolder.name}/")
            return txts[0].parent

    # ── 3. Nothing found ────────────────────────────────────────────────────
    _abort_not_found()


def _abort(msg: str):
    print(f"\n❌ Error: {msg}\n")
    sys.exit(1)


def _abort_not_found():
    print("""
❌  No episode data found.

Please add your Kuku input pack to the data/ folder in one of two ways:

  Option A — Drop the zip file:
    data/
    └── your-show-input-pack.zip      ← script auto-extracts this

  Option B — Drop the extracted folder:
    data/
    └── I Married a Broken Soldier. He was a Duke/
        ├── episode-001-....txt
        ├── episode-002-....txt
        └── ...

  Option C — Pass the path directly:
    python run.py --input /path/to/your/episode/folder
    python run.py --input /path/to/your/pack.zip

The episode data is Kuku's confidential content — never commit it to GitHub.
""")
    sys.exit(1)


def detect_data_folder() -> Path | None:
    """
    Return the episodes folder if data is available, else None.
    Used by both app.py and can be imported anywhere.
    """
    DATA_DIR.mkdir(exist_ok=True)

    # Already unzipped folder inside data/
    for sub in DATA_DIR.iterdir():
        if sub.is_dir():
            txts = find_txt_files(sub)
            if txts:
                return txts[0].parent

    # Zip file inside data/
    zips = sorted(DATA_DIR.glob("*.zip"))
    if zips:
        extract_dir = DATA_DIR / zips[0].stem
        if extract_dir.exists():
            txts = find_txt_files(extract_dir)
            if txts:
                return txts[0].parent
        folder = try_unzip(zips[0], extract_dir)
        return folder

    return None


def parse_args():
    """Parse CLI arguments for run.py."""
    parser = argparse.ArgumentParser(
        description="Kuku Promo Finder — find the best promo clips in microdrama screenplays."
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=None,
        help="Path to episode folder or .zip file (default: auto-detect from data/)",
    )
    parser.add_argument(
        "--max-windows", "-m",
        type=int,
        default=16,
        help="Max number of windows to score via API (default: 16 to respect free-tier RPD limits)",
    )
    parser.add_argument(
        "--top-n", "-n",
        type=int,
        default=20,
        help="Number of top promos to return (default: 20)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="raw_outputs",
        help="Directory to save output JSON files (default: raw_outputs/)",
    )
    parser.add_argument(
        "--confidential", "-c",
        action="store_true",
        help="Run in 100%% Confidential Mode: Zero external API calls (uses on-device heuristic engine)",
    )
    return parser.parse_args()
