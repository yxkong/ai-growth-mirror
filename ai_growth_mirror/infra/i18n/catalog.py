"""YAML-backed i18n catalog adapter with zh/en fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ...assets import I18N_DIR

SUPPORTED_LANGUAGES = frozenset({"zh", "en"})
DEFAULT_LANGUAGE = "zh"

_CATALOG_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def normalize_language(language: str) -> str:
    return language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def _resolve_catalog_path(stem: str, language: str) -> Path:
    lang = normalize_language(language)
    primary = I18N_DIR / f"{stem}_{lang}.yaml"
    fallback = I18N_DIR / f"{stem}_{DEFAULT_LANGUAGE}.yaml"
    return primary if primary.exists() else fallback


def load_catalog(stem: str, language: str = DEFAULT_LANGUAGE) -> dict[str, Any]:
    lang = normalize_language(language)
    cache_key = (stem, lang)
    if cache_key in _CATALOG_CACHE:
        return _CATALOG_CACHE[cache_key]

    path = _resolve_catalog_path(stem, lang)
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        data = {}
    _CATALOG_CACHE[cache_key] = data
    return data


def clear_catalog_cache() -> None:
    _CATALOG_CACHE.clear()
