"""Outbound LLM privacy and mandatory execution-boundary tests."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from ai_growth_mirror.domain.common.contracts import LlmCallRequest
from ai_growth_mirror.infra.llm.execution import complete_json_with_retries
from ai_growth_mirror.infra.llm.privacy import sanitize_outbound_text


CANARY_SECRET = "agm-canary-super-secret"


class _CapturingGateway:
    def __init__(self) -> None:
        self.request: LlmCallRequest | None = None

    def complete_json(self, request: LlmCallRequest):
        self.request = request
        return {"ok": True}


class _FailOnceGateway:
    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, request: LlmCallRequest):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError(f"timeout {CANARY_SECRET}")
        return {"ok": True}


def test_llm_execution_sanitizes_user_prompt_but_not_system_prompt() -> None:
    gateway = _CapturingGateway()
    system = "Static rubric: keep the word password as an analysis category."
    prompt = "\n".join(
        (
            "Implement cache recovery for this task.",
            r"Project: C:\Users\alice\My Secret Project\service.py",
            "Unix: /home/alice/private/service.py",
            "Email: alice@example.com",
            f"Authorization: Bearer {CANARY_SECRET}",
            f"api_key={CANARY_SECRET}",
            f"password: {CANARY_SECRET}",
            "-----BEGIN PRIVATE KEY-----\nsecret-material\n-----END PRIVATE KEY-----",
        )
    )

    result = complete_json_with_retries(
        llm=gateway,
        request=LlmCallRequest(prompt=prompt, system=system),
    )

    assert result == {"ok": True}
    assert gateway.request is not None
    assert gateway.request.system == system
    assert "Implement cache recovery" in gateway.request.prompt
    for raw_value in (
        CANARY_SECRET,
        r"C:\Users\alice\My Secret Project\service.py",
        "/home/alice/private/service.py",
        "alice@example.com",
        "secret-material",
    ):
        assert raw_value not in gateway.request.prompt


def test_sanitizer_applies_length_budget_after_redaction() -> None:
    result = sanitize_outbound_text(f"token={CANARY_SECRET} " + "x" * 200, max_chars=32)
    assert CANARY_SECRET not in result
    assert len(result) <= 32


def test_feature_modules_cannot_bypass_shared_llm_execution() -> None:
    package_root = Path(__file__).resolve().parents[2] / "ai_growth_mirror"
    allowed = {
        package_root / "infra" / "llm" / "execution.py",
        package_root / "infra" / "llm" / "gateway.py",
    }
    violations: list[str] = []
    for path in package_root.rglob("*.py"):
        if path in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "complete_json"
            ):
                violations.append(str(path.relative_to(package_root)))
    assert not violations, "Direct complete_json calls bypass privacy: " + ", ".join(violations)


def test_all_llm_features_mark_untrusted_evidence_in_prompts() -> None:
    prompt_root = (
        Path(__file__).resolve().parents[2]
        / "ai_growth_mirror"
        / "assets"
        / "prompts"
    )
    for feature in ("session_read", "prompt_lens", "work_focus", "growth_coach"):
        system = (prompt_root / feature / "system.md.j2").read_text(encoding="utf-8")
        user = (prompt_root / feature / "user.md.j2").read_text(encoding="utf-8")
        assert "UNTRUSTED_EVIDENCE_BEGIN" in user
        assert "UNTRUSTED_EVIDENCE_END" in user
        assert "UNTRUSTED_EVIDENCE" in system


def test_retry_log_does_not_echo_exception_or_untrusted_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.llm-privacy")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        result = complete_json_with_retries(
            llm=_FailOnceGateway(),
            request=LlmCallRequest(prompt="safe"),
            retry_delays=(0.0,),
            logger=logger,
            log_context=f"session-read:{CANARY_SECRET}",
        )

    assert result == {"ok": True}
    assert CANARY_SECRET not in caplog.text
    assert "exception_type=RuntimeError" in caplog.text
