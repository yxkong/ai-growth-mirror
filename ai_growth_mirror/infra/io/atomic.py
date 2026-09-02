"""Atomic same-directory text and JSON writes."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Replace *path* with a complete text payload or leave it unchanged."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)
    try:
        handle = os.fdopen(descriptor, "w", encoding=encoding, newline="")
        descriptor = -1
        with handle:
            handle.write(content)
            handle.flush()
            if os.name != "nt":
                os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temp_path.unlink(missing_ok=True)


def atomic_write_json(path: Path, payload: Any, *, encoding: str = "utf-8") -> None:
    """Serialize *payload* with the project's stable JSON format and replace *path*."""
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding=encoding,
    )
