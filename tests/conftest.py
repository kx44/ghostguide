import pytest


@pytest.fixture(autouse=True)
def _activity_log(tmp_path, monkeypatch):
    """Tests write their sends to a log of their own, and each starts with the switch off and nothing counted."""
    from engine import activity

    monkeypatch.setattr(activity, "LOG", tmp_path / "activity.jsonl")
    monkeypatch.setattr(activity, "_pictures", 0)
    monkeypatch.setattr(activity, "_local_only", False)
    monkeypatch.setattr(activity, "_withheld_t", {})
