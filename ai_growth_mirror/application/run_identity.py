"""Stable personal-report run identifiers (not clock-based)."""

from __future__ import annotations

import hashlib
from typing import Sequence

from ..domain.session.scope import SessionScope
from ..product import PERSONAL_REPORT_RUN_ID_PREFIX

# Default scope (all enabled tools, last-30-days → now, auto session read, zh).
DEFAULT_PERSONAL_RUN_ID = f"{PERSONAL_REPORT_RUN_ID_PREFIX}-default"


def resolve_personal_run_id(
    *,
    tools: Sequence[str],
    since_label: str,
    until_label: str,
    session_read_mode: str,
    language: str,
    scope_filters: SessionScope | None = None,
) -> str:
    """Return a deterministic run id for the same CLI analysis scope.

    Same tools + time window + session read mode + language (+ scope filters) always
    yields the same id across days; only changes when the user changes inputs.
    """
    scope = scope_filters or SessionScope()
    scope_part = "|".join(
        [
            ",".join(scope.repos),
            ",".join(str(path) for path in scope.dirs),
            ",".join(scope.keywords),
        ]
    )
    payload = "|".join(
        [
            ",".join(sorted(tools)),
            since_label,
            until_label,
            session_read_mode,
            language,
            scope_part,
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
    return f"{PERSONAL_REPORT_RUN_ID_PREFIX}-{digest}"
