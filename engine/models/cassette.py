"""Record / replay model responses → cache/cassettes/<key>.json, so UI work spends no credits."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from engine import config


class CassetteMiss(LookupError):
    """Replay mode asked for a response nobody recorded."""


def _strip_images(obj: Any) -> Any:
    """Replace inline base64 images by their hash: keys stay stable and cassettes stay small."""
    if isinstance(obj, dict):
        return {k: _strip_images(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_images(v) for v in obj]
    if isinstance(obj, str) and obj.startswith("data:") and ";base64," in obj:
        return "sha256:" + hashlib.sha256(obj.encode()).hexdigest()
    return obj


def request_key(request: dict) -> str:
    """Same request (model, messages, tools, params) → same key. Images count by content."""
    canonical = json.dumps(_strip_images(request), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


class Cassettes:
    def __init__(self, folder: Optional[Path] = None):
        self.folder = Path(folder or config.CASSETTES)

    def path(self, key: str) -> Path:
        return self.folder / f"{key}.json"

    def has(self, key: str) -> bool:
        return self.path(key).exists()

    def load(self, key: str, request: Optional[dict] = None) -> dict:
        p = self.path(key)
        if not p.exists():
            model = (request or {}).get("model", "?")
            raise CassetteMiss(
                f"no recorded response for this {model} request (key {key}) in {self.folder}. "
                "Run once with MODEL_MODE=record to record it (spends credits)."
            )
        return json.loads(p.read_text(encoding="utf-8"))["response"]

    def save(self, key: str, request: dict, response: dict) -> Path:
        self.folder.mkdir(parents=True, exist_ok=True)
        p = self.path(key)
        p.write_text(json.dumps({
            "key": key,
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "request": _strip_images(request),
            "response": response,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        return p
