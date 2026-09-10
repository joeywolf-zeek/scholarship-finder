"""Persisted application status, keyed by scholarship id."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

VALID_STATUSES = {"not started", "in progress", "submitted", "awarded", "rejected"}


def load_statuses(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def save_statuses(path: Path, statuses: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(statuses, f, indent=2, sort_keys=True)
        f.write("\n")


def set_status(path: Path, scholarship_id: str, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}, got {status!r}")
    statuses = load_statuses(path)
    statuses[scholarship_id] = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save_statuses(path, statuses)
