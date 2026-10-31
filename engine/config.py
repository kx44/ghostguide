"""Paths, model IDs, MODEL_MODE and thresholds. Values come from the environment, then `.env`."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
CASSETTES = CACHE / "cassettes"
LOGS = CACHE / "logs"
COST_LOG = LOGS / "costs.jsonl"
TUTORIALS = ROOT / "tutorials"
COMPILED = TUTORIALS / "compiled"
APPMAPS = ROOT / "appmaps"


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env reader: KEY=VALUE lines; real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def is_secure(url: str) -> bool:
    """Keys and pictures only travel over https. Plain http only to this PC itself."""
    u = urlparse(url)
    return u.scheme == "https" or (u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost", "::1"))


MODEL_MODES = ("live", "record", "replay")


def model_mode() -> str:
    mode = env("MODEL_MODE", "replay").lower()
    if mode not in MODEL_MODES:
        raise ValueError(f"MODEL_MODE must be one of {MODEL_MODES}, got {mode!r}")
    return mode


def budget_usd() -> float:
    return float(env("BUDGET_USD", "4.00"))


# Model IDs
SPARK = "muse-spark-1.3"
SPARK_CONTRIBUTOR = "muse-spark-1.3-contributor"
WONDER = "muse-wonder-1.0"
TRANSCRIBE = "muse-voice-transcribe-1.0"
SAM = "sam-3.1"

# USD per million tokens (input, output). Unknown models are refused in live mode.
PRICES = {
    SPARK: (1.25, 4.25),
    SPARK_CONTRIBUTOR: (0.10, 0.20),
    WONDER: (4.00, 20.00),
}

TRANSCRIBE_USD_PER_HOUR = 0.18
WEB_SEARCH_USD = 0.0025     # per query the model makes


def compile_model() -> str:
    """Compiling runs on Spark 1.3. COMPILE_MODEL or `compile --tune` picks the Contributor rate while tuning prompts."""
    return env("COMPILE_MODEL", SPARK)


# Meta allows at most 50 images per request.
MAX_IMAGES = 50

# Live thresholds
SCHEME_LIGHT_ABOVE = 0.45   # brightness in the ring around the target → light scheme
SCHEME_RING_PX = 48
