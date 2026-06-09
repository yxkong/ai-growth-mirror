"""Disk-cache schema versions for records and session reads."""

from __future__ import annotations

# Bump this when SessionRecord or SessionRead on-disk JSON shape changes.
CACHE_SCHEMA_VERSION = "1.0"

RECORD_SCHEMA_VERSION = CACHE_SCHEMA_VERSION
SESSION_READ_SCHEMA_VERSION = CACHE_SCHEMA_VERSION
