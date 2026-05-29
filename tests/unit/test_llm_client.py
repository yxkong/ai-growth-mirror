import pytest

from ai_growth_mirror.infra.llm.factory import make_llm_client
from ai_growth_mirror.infra.llm.gateway import GatewayBackedLlmClient
from ai_growth_mirror.infra.llm.json_repair import repair_json
from ai_growth_mirror.infra.llm.providers.openai import OpenAIChatAdapter
from ai_growth_mirror.infra.llm.unified import UnifiedLLMClient


@pytest.mark.parametrize(
    "raw,expected_keys,need_repair",
    [
        ('{"a": 1}', ["a"], False),
        ("```json\n{\"a\": 1}\n```", ["a"], True),
        ('{"a": 1,}', ["a"], True),
    ],
)
def test_repair_json_levels(raw, expected_keys, need_repair):
    parsed, levels = repair_json(raw)
    assert list(parsed.keys()) == expected_keys  # type: ignore[union-attr]
    assert bool(levels) == need_repair


def test_unified_client_delegates():
    def delegate(**_: str) -> str:
        return '{"x": true}'

    c = UnifiedLLMClient(delegate)
    r = c.complete_json(system="s", user="u", model="m", provider="p")
    assert r.parsed_json == {"x": True}


@pytest.mark.parametrize(
    "provider,expected_model,expected_url",
    [
        ("deepseek", "deepseek-v4-pro", "https://api.deepseek.com"),
        ("glm", "glm-5.1", "https://open.bigmodel.cn/api/paas/v4/"),
    ],
)
def test_make_llm_client_aliases(monkeypatch, provider, expected_model, expected_url):
    captured = {}

    def fake_init(self, *, model, api_key=None, base_url=None):  # pragma: no cover - monkeypatched
        captured["model"] = model
        captured["base_url"] = base_url

    monkeypatch.setattr(OpenAIChatAdapter, "__init__", fake_init)
    client = make_llm_client(provider)
    assert isinstance(client, GatewayBackedLlmClient)
    assert isinstance(client.adapter, OpenAIChatAdapter)
    assert captured["model"] == expected_model
    assert captured["base_url"] == expected_url
