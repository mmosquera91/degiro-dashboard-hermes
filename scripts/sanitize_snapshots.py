#!/usr/bin/env python3
"""One-off sanitizer: replace NaN/inf floats with None in all snapshot JSON files."""

import json
import logging
import os
import sys
from pathlib import Path

# Add app/ to path so we can import _sanitize_floats
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from market_data import _sanitize_floats

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path("/data/snapshots")
files_found = list(SNAPSHOT_DIR.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json"))
if not files_found:
    logger.info("No snapshot files found in %s", SNAPSHOT_DIR)
    sys.exit(0)

logger.info("Found %d snapshot files to sanitize", len(files_found))
for file_path in sorted(files_found):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        sanitized = _sanitize_floats(data)
        tmp_path = file_path.with_suffix(".json.tmp")
        with open(tmp_path, "w") as f:
            json.dump(sanitized, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp_path, file_path)
        logger.info("Sanitized: %s", file_path.name)
    except Exception as e:
        logger.warning("Failed to sanitize %s: %s", file_path.name, e)

logger.info("Done. %d files processed.", len(files_found))