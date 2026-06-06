"""Cost policy for token-based session accounting.

Token counts for tools that do not embed real usage in their logs (e.g. Gemini
Antigravity) are *estimated* from content length. Estimated costs should be
displayed with a leading ``~`` in the UI.

Built-in fallback prices are provided via ``MODEL_PRICING``. Users can override
them per-model-family in ``config.yaml`` under the ``pricing`` key.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

_ONE_MILLION = 1_000_000


@dataclass(frozen=True)
class TokenPricing:
    input_per_million: float
    output_per_million: float
    cache_write_per_million: float = 0.0
    cache_read_per_million: float = 0.0

    def estimate(self, usage: "TokenUsage") -> float:
        amount = (
            usage.input_tokens * self.input_per_million
            + usage.output_tokens * self.output_per_million
            + usage.cache_write_tokens * self.cache_write_per_million
            + usage.cache_read_tokens * self.cache_read_per_million
        ) / _ONE_MILLION
        return round(amount, 6)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_input_surface(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    @property
    def has_billable_usage(self) -> bool:
        return any(
            (
                self.input_tokens,
                self.output_tokens,
                self.cache_read_tokens,
                self.cache_write_tokens,
            )
        )


# ── built-in fallback prices (USD per 1 M tokens) ────────────────────────────
# These are used when no user-defined pricing is found in config.yaml.
# Prices change frequently — configure your own under `pricing:` in config.yaml.
DEFAULT_PRICING = TokenPricing(2.50, 10.00)
MODEL_PRICING: tuple[tuple[str, TokenPricing], ...] = (
    ("opus",    TokenPricing(15.00, 75.00, 18.75, 1.50)),
    ("sonnet",  TokenPricing(3.00,  15.00,  3.75, 0.30)),
    ("claude",  TokenPricing(3.00,  15.00,  3.75, 0.30)),
    ("haiku",   TokenPricing(0.80,   4.00,  1.00, 0.08)),
    ("gemini",  TokenPricing(1.25,   5.00)),
    ("deepseek", TokenPricing(0.27,  1.10)),
    ("gpt",     TokenPricing(2.50,  10.00)),
)


def resolve_pricing(
    models_used: list[str] | None,
    *,
    user_pricing: dict[str, TokenPricing] | None = None,
) -> TokenPricing:
    """Resolve session pricing from the highest-signal model family.

    Lookup order:
    1. ``user_pricing`` dict (from config.yaml ``pricing`` section)
    2. Built-in ``MODEL_PRICING`` fallback table
    3. ``DEFAULT_PRICING``
    """
    combined = " ".join(models_used or []).lower()

    # User-configured prices take priority
    if user_pricing:
        for token, pricing in user_pricing.items():
            if token.lower() in combined:
                return pricing

    # Built-in fallback
    for token, pricing in MODEL_PRICING:
        if token in combined:
            return pricing

    return DEFAULT_PRICING


def estimate_cost(
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    cache_read_tokens: Optional[int] = None,
    cache_write_tokens: Optional[int] = None,
    models_used: Optional[list[str]] = None,
    *,
    user_pricing: dict[str, "TokenPricing"] | None = None,
) -> Optional[float]:
    """Return estimated USD cost, or None if no token data is available.

    When ``user_pricing`` is provided (loaded from config.yaml), it takes
    precedence over the built-in fallback table.
    """
    usage = TokenUsage(
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
        cache_read_tokens=cache_read_tokens or 0,
        cache_write_tokens=cache_write_tokens or 0,
    )
    if not usage.has_billable_usage:
        return None
    return resolve_pricing(models_used, user_pricing=user_pricing).estimate(usage)


def cache_hit_rate(
    cache_read_tokens: Optional[int],
    input_tokens: Optional[int],
    cache_write_tokens: Optional[int] = None,
) -> Optional[float]:
    """Fraction of all input tokens that were served from cache (0–1).

    cache_read / (input + cache_read + cache_write)

    Denominator = total tokens processed as input across all three buckets:
    - input_tokens: uncached, paid at full input rate
    - cache_read_tokens: served from existing cache (cheapest)
    - cache_write_tokens: written to cache on this request (also processed)

    Omitting cache_write inflates the hit rate because large first-turn
    cache-writes are excluded from the denominator.
    """
    usage = TokenUsage(
        input_tokens=input_tokens or 0,
        cache_read_tokens=cache_read_tokens or 0,
        cache_write_tokens=cache_write_tokens or 0,
    )
    if usage.cache_read_tokens <= 0 or input_tokens is None:
        return None
    if usage.total_input_surface <= 0:
        return None
    return round(usage.cache_read_tokens / usage.total_input_surface, 4)
