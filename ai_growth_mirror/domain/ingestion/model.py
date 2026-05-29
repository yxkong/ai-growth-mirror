"""Domain contracts for ingestion and session collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..session.model import SessionRecord


@dataclass(frozen=True)
class ToolCollectorSpec:
    tool_name: str
    display_name: str
    adapter_cls: type[Any]


@dataclass(frozen=True)
class CollectedAdapterView:
    tool_name: str
    display_name: str
    session_count: int


@dataclass
class CollectionResult:
    sessions: list[SessionRecord] = field(default_factory=list)
    adapters: list[Any] = field(default_factory=list)
    adapter_views: list[CollectedAdapterView] = field(default_factory=list)
    display_name: str = ""
