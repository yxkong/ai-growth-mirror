"""Privacy-safe reader diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReaderDiagnostics:
    detected: int = 0
    parsed: int = 0
    skipped: int = 0
    corrupt: int = 0
    schema_mismatch: int = 0
    orphan: int = 0
    unreadable: int = 0

    def as_dict(self) -> dict[str, int]:
        """Return the stable, privacy-safe diagnostics contract."""
        return {
            "detected": self.detected,
            "parsed": self.parsed,
            "skipped": self.skipped,
            "corrupt": self.corrupt,
            "schema_mismatch": self.schema_mismatch,
            "orphan": self.orphan,
            "unreadable": self.unreadable,
        }
