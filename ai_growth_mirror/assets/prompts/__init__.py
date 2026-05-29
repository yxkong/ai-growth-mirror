"""Prompt asset loading for structured report generation."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator

from jinja2 import Environment, FileSystemLoader, Template

ASSET_ROOT = Path(__file__).parent
_PROMPT_DIRS: ContextVar[tuple[Path, ...]] = ContextVar("growth_mirror_prompt_dirs", default=())


def normalize_report_language(language: str | None) -> str:
    """Report locale for LLM natural-language output (default zh)."""
    return language if language in ("zh", "en") else "zh"


def _normalize_prompt_dirs(paths: tuple[Path | str, ...]) -> tuple[Path, ...]:
    normalized: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        if not raw:
            continue
        path = Path(raw).expanduser()
        key = str(path.resolve(strict=False)).lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(path)
    return tuple(normalized)


def current_prompt_asset_dirs() -> tuple[Path, ...]:
    return _PROMPT_DIRS.get()


def set_prompt_asset_dirs(*paths: Path | str) -> None:
    _PROMPT_DIRS.set(_normalize_prompt_dirs(paths))


def clear_prompt_asset_dirs() -> None:
    _PROMPT_DIRS.set(())


@contextmanager
def prompt_asset_scope(*paths: Path | str) -> Iterator[tuple[Path, ...]]:
    merged = _normalize_prompt_dirs(current_prompt_asset_dirs() + _normalize_prompt_dirs(paths))
    token = _PROMPT_DIRS.set(merged)
    try:
        yield merged
    finally:
        _PROMPT_DIRS.reset(token)


def build_prompt_environment(*extra_dirs: Path) -> Environment:
    search_dirs = [str(path) for path in _normalize_prompt_dirs(current_prompt_asset_dirs() + extra_dirs)]
    search_dirs.append(str(ASSET_ROOT))
    return Environment(loader=FileSystemLoader(search_dirs), autoescape=False)


def get_prompt_template(asset_path: str, *extra_dirs: Path) -> Template:
    env = build_prompt_environment(*extra_dirs)
    return env.get_template(asset_path)


def render_prompt_asset(asset_path: str, *extra_dirs: Path, **context: object) -> str:
    return get_prompt_template(asset_path, *extra_dirs).render(**context)
