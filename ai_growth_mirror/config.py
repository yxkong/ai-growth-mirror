"""Configuration and provider defaults for the growth mirror product."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .product import DEFAULT_HOME_DIR, PRODUCT_RUNTIME_DIRNAME

DEFAULT_CONFIG_PATH = DEFAULT_HOME_DIR / "config.yaml"
LOCAL_CONFIG_BASENAME = "config.yaml"

PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "claude": {
        "model": "aws-claude-sonnet-4-6",
        "base_url": "",
    },
    "gemini": {
        "model": "gemini-3_1-pro-preview",
        "base_url": "",
    },
    "openai": {
        "model": "azure-gpt-5_4-mini",
        "base_url": "",
    },
    "openai_compatible": {
        "model": "gpt-4.1-mini",
        "base_url": "",
    },
    "deepseek": {
        "model": "deepseek-v4-pro",
        "base_url": "https://api.deepseek.com",
    },
    "glm": {
        "model": "glm-5.1",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
    },
}

PROVIDER_ENV_KEYS: dict[str, tuple[str, ...]] = {
    "claude": ("ANTHROPIC_API_KEY",),
    "gemini": ("GOOGLE_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "openai_compatible": ("OPENAI_API_KEY", "OPENAI_COMPATIBLE_API_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY", "OPENAI_API_KEY"),
    "glm": ("ZHIPUAI_API_KEY", "BIGMODEL_API_KEY", "GLM_API_KEY"),
}


def normalize_provider(provider: str | None) -> str:
    value = (provider or "deepseek").strip().lower().replace("-", "_")
    if value == "openai-compatible":
        value = "openai_compatible"
    return value or "deepseek"


def provider_default_model(provider: str | None) -> str:
    normalized = normalize_provider(provider)
    return PROVIDER_DEFAULTS.get(normalized, PROVIDER_DEFAULTS["deepseek"])["model"]


def provider_default_base_url(provider: str | None) -> str:
    normalized = normalize_provider(provider)
    return PROVIDER_DEFAULTS.get(normalized, PROVIDER_DEFAULTS["deepseek"])["base_url"]


def provider_api_key_envs(provider: str | None) -> tuple[str, ...]:
    normalized = normalize_provider(provider)
    return PROVIDER_ENV_KEYS.get(normalized, ("OPENAI_API_KEY",))


def resolve_provider_api_key(provider: str | None, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    for env_key in provider_api_key_envs(provider):
        value = os.environ.get(env_key)
        if value:
            return value
    return None


def llm_auth_missing(provider: str | None, api_key: str | None) -> bool:
    return not bool(resolve_provider_api_key(provider, explicit=api_key))


def resolve_config_path(explicit: Path | None = None, *, cwd: Path | None = None) -> Path:
    """Pick config file: explicit path, else ./config.yaml when present, else home default."""
    if explicit is not None:
        return explicit.expanduser()
    local = (cwd or Path.cwd()) / LOCAL_CONFIG_BASENAME
    if local.is_file():
        return local
    return DEFAULT_CONFIG_PATH


def default_config_path(*, cwd: Path | None = None) -> Path:
    return resolve_config_path(cwd=cwd)

def default_cache_dir(*, cwd: Path | None = None) -> Path:
    """Project-local cache under cwd (same scope as report output and runtime manifest)."""
    return (cwd or Path.cwd()) / PRODUCT_RUNTIME_DIRNAME / "cache"



@dataclass
class ToolConfig:
    enabled: bool = True
    data_root: Optional[Path] = None


@dataclass
class LLMConfig:
    provider: str = "deepseek"
    model: str = field(default_factory=lambda: provider_default_model("deepseek"))
    api_key: Optional[str] = None
    base_url: str = field(default_factory=lambda: provider_default_base_url("deepseek"))

    def finalize(self) -> None:
        self.provider = normalize_provider(self.provider)
        if not self.model:
            self.model = provider_default_model(self.provider)
        if not self.base_url:
            self.base_url = provider_default_base_url(self.provider)
        if not self.api_key:
            self.api_key = resolve_provider_api_key(self.provider)


@dataclass
class CacheConfig:
    enabled: bool = True
    dir: Path = field(default_factory=default_cache_dir)
    # Reserved; not enforced. 0 = no calendar expiry (disk cache is mtime + schema only).
    ttl_days: int = 0


@dataclass
class ReportConfig:
    language: str = "zh"
    output_dir: Path = field(default_factory=Path.cwd)
    prompt_dirs: list[Path] = field(default_factory=list)
    # User-configured AI asset root directories (skills, prompts, rules).
    # Each path is scanned by agent_asset_enricher and checked during
    # session-level reusable-asset detection. Example config.yaml entry:
    #   report:
    #     asset_roots:
    #       - /path/to/your/agent-hub
    #       - ~/.cursor/skills
    asset_roots: list[Path] = field(default_factory=list)
    # Optional private/local method framework names. These are merged with names
    # extracted from asset_roots and only become level evidence when observed in
    # session skill/slash usage.
    local_method_frameworks: list[str] = field(default_factory=list)
    min_quality: str = "medium"
    # Optional scope filters (same semantics as CLI --repo/--dir/--keyword).
    scope_repos: list[str] = field(default_factory=list)
    scope_dirs: list[Path] = field(default_factory=list)
    scope_keywords: list[str] = field(default_factory=list)


@dataclass
class GrowthMirrorConfig:
    tools: dict[str, ToolConfig] = field(default_factory=dict)
    llm: LLMConfig = field(default_factory=LLMConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    report: ReportConfig = field(default_factory=ReportConfig)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "GrowthMirrorConfig":
        cfg = cls()
        config_path = resolve_config_path(path)
        if config_path.exists():
            try:
                import yaml

                with open(config_path, "r", encoding="utf-8") as handle:
                    data = yaml.safe_load(handle) or {}
                _apply_yaml(cfg, data)
            except ImportError:
                pass
        cfg.llm.finalize()
        return cfg

def _apply_yaml(cfg: GrowthMirrorConfig, data: dict) -> None:
    if "llm" in data:
        llm = data["llm"] or {}
        provider = llm.get("provider", cfg.llm.provider)
        provider_changed = normalize_provider(provider) != normalize_provider(cfg.llm.provider)
        cfg.llm.provider = provider
        if "model" in llm:
            cfg.llm.model = llm.get("model", cfg.llm.model)
        elif provider_changed:
            cfg.llm.model = provider_default_model(provider)
        if "base_url" in llm:
            cfg.llm.base_url = llm.get("base_url", cfg.llm.base_url)
        elif provider_changed:
            cfg.llm.base_url = provider_default_base_url(provider)
        cfg.llm.api_key = llm.get("api_key", cfg.llm.api_key)
    if "cache" in data:
        cache = data["cache"] or {}
        cfg.cache.enabled = cache.get("enabled", cfg.cache.enabled)
        if cache.get("dir"):
            cfg.cache.dir = Path(cache["dir"]).expanduser()
        cfg.cache.ttl_days = cache.get("ttl_days", cfg.cache.ttl_days)
    if "report" in data:
        report = data["report"] or {}
        cfg.report.language = report.get("language", cfg.report.language)
        if report.get("output_dir"):
            cfg.report.output_dir = Path(report["output_dir"]).expanduser()
        if report.get("prompt_dirs"):
            cfg.report.prompt_dirs = [Path(item).expanduser() for item in report.get("prompt_dirs", []) if item]
        if report.get("asset_roots"):
            cfg.report.asset_roots = [Path(item).expanduser() for item in report.get("asset_roots", []) if item]
        if report.get("local_method_frameworks"):
            cfg.report.local_method_frameworks = [
                str(item).strip()
                for item in report.get("local_method_frameworks", [])
                if str(item).strip()
            ]
        if report.get("min_quality"):
            cfg.report.min_quality = str(report.get("min_quality") or "medium")
        if report.get("scope_repos"):
            cfg.report.scope_repos = [str(item).strip() for item in report.get("scope_repos", []) if item]
        if report.get("scope_dirs"):
            cfg.report.scope_dirs = [Path(item).expanduser() for item in report.get("scope_dirs", []) if item]
        if report.get("scope_keywords"):
            cfg.report.scope_keywords = [str(item).strip() for item in report.get("scope_keywords", []) if item]
    if "tools" in data:
        for tool_name, tool_data in data["tools"].items():
            tool_cfg = ToolConfig()
            if isinstance(tool_data, dict):
                tool_cfg.enabled = tool_data.get("enabled", True)
                if tool_data.get("data_root"):
                    tool_cfg.data_root = Path(tool_data["data_root"]).expanduser()
            cfg.tools[tool_name] = tool_cfg
