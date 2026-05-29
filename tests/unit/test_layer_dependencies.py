"""Guardrails: infra must not depend on application; domain stays pure."""

from __future__ import annotations

import ast
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[2] / "ai_growth_mirror"

# Known debt: snapshot HTML still assembles view in application; infra only archives.
_INFRA_APPLICATION_IMPORT_ALLOWLIST = {
    _PKG_ROOT / "infra" / "snapshots.py",
}


def _module_import_targets(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.level:
                top = node.module.split(".", 1)[0]
                targets.add(top)
            else:
                targets.add(node.module)
    return targets


def test_infra_does_not_import_application():
    infra_root = _PKG_ROOT / "infra"
    violations: list[str] = []
    for path in infra_root.rglob("*.py"):
        if path in _INFRA_APPLICATION_IMPORT_ALLOWLIST:
            continue
        for target in _module_import_targets(path):
            if target.startswith("ai_growth_mirror.application") or target == "application":
                violations.append(f"{path.relative_to(_PKG_ROOT)} imports {target}")
            if ".application." in target or target.endswith(".application"):
                violations.append(f"{path.relative_to(_PKG_ROOT)} imports {target}")
    assert not violations, "\n".join(violations)


def test_domain_does_not_import_infra_or_application():
    domain_root = _PKG_ROOT / "domain"
    violations: list[str] = []
    for path in domain_root.rglob("*.py"):
        for target in _module_import_targets(path):
            if "ai_growth_mirror.infra" in target or target.startswith("infra"):
                violations.append(f"{path.relative_to(_PKG_ROOT)} imports {target}")
            if "ai_growth_mirror.application" in target or ".application" in target:
                violations.append(f"{path.relative_to(_PKG_ROOT)} imports {target}")
    assert not violations, "\n".join(violations)
