"""Product identity and outward-facing naming for AI Growth Mirror."""

from __future__ import annotations

from pathlib import Path

PRODUCT_NAME = "AI Growth Mirror"
PRODUCT_LABEL_ZH = "AI 成长镜"
PRODUCT_SLUG = "ai-growth-mirror"
PRODUCT_RUNTIME_DIRNAME = ".ai-growth-mirror-runtime"
PRODUCT_HOME_DIRNAME = ".ai-growth-mirror"
SNAPSHOT_ARCHIVE_DIRNAME = "ai-growth-mirror-archive"
LEGACY_SNAPSHOT_ARCHIVE_DIRNAMES = ("snapshot-archive",)
PRIMARY_REPORT_FILENAME = "ai-growth-mirror.html"
PRIMARY_REPORT_JSON_FILENAME = "ai-growth-mirror.json"
PRIMARY_REPORT_SUMMARY_FILENAME = "ai-growth-mirror.summary.json"
JSON_SCHEMA_ID = "ai-growth-mirror/1.0"
CLI_NAME = "ai-growth-mirror"
# Stable prefix for personal `generate` run_id (suffix is scope hash, not timestamp).
PERSONAL_REPORT_RUN_ID_PREFIX = "personal"

DEFAULT_HOME_DIR = Path.home() / PRODUCT_HOME_DIRNAME


def default_home_dir() -> Path:
    return DEFAULT_HOME_DIR
