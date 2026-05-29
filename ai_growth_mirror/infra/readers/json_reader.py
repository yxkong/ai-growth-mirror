"""Read lightweight session fixtures from JSON payloads."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from ai_growth_mirror.domain.session.model import SessionRecord

_SESSION_RECORD_KEYS = {field.name for field in fields(SessionRecord)}


def _read_json_source(source: str | Path) -> dict[str, Any]:
    candidate = Path(source)
    raw = candidate.read_text(encoding="utf-8") if candidate.exists() else str(source)
    return json.loads(raw)


def _normalize_meta(payload: dict[str, Any]) -> dict[str, Any]:
    meta = dict(payload.get("meta") or payload)
    if "tool_name" not in meta and "tool" in meta:
        meta["tool_name"] = str(meta.pop("tool"))
    if "session_id" not in meta and "id" in meta:
        meta["session_id"] = str(meta["id"])
    return {key: value for key, value in meta.items() if key in _SESSION_RECORD_KEYS}


class JsonSessionAdapter:
    """Convenience loader for tests and one-off imports."""

    tool_name = "json_dump"

    def load(self, source: str | Path) -> SessionRecord:
        payload = _read_json_source(source)
        return SessionRecord.from_dict(_normalize_meta(payload))
