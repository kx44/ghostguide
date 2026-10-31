"""The overlay's plain logic (settings, keys, tray menu, window placement), tested in Node so the full suite covers it."""
import shutil
import subprocess
from pathlib import Path

import pytest

OVERLAY = Path("overlay")


@pytest.mark.skipif(not shutil.which("node") or not (OVERLAY / "node_modules").exists(), reason="needs Node and npm install")
def test_overlay_unit_tests():
    r = subprocess.run(["node", "test/unit.mjs"], cwd=OVERLAY, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
