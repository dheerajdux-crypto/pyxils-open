"""Small JSON sidecar persistence for resumable download metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def metadata_path(destination: str | Path) -> Path:
    path = Path(destination)
    return path.with_name(path.name + ".pyxils.json")


def load_metadata(destination: str | Path) -> dict[str, Any] | None:
    path = metadata_path(destination)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def save_metadata(destination: str | Path, data: dict[str, Any]) -> None:
    path = metadata_path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def remove_metadata(destination: str | Path) -> None:
    try:
        metadata_path(destination).unlink()
    except FileNotFoundError:
        pass
