"""Cost policy for token-based session accounting."""
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


DEFAULT_PRICING = TokenPricing(2.50, 10.00)
MODEL_PRICING: tuple[tuple[str, TokenPricing], ...] = (
    ("opus", TokenPricing(15.00, 75.00, 18.75, 1.50)),
    ("sonnet", TokenPricing(3.00, 15.00, 3.75, 0.30)),
    ("claude", TokenPricing(3.00, 15.00, 3.75, 0.30)),
    ("haiku", TokenPricing(0.80, 4.00, 1.00, 0.08)),
)


def resolve_pricing(models_used: list[str] | None) -> TokenPricing:
    """Resolve session pricing from the highest-signal model family."""

    combined = " ".join(models_used or []).lower()
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
) -> Optional[float]:
    """Return estimated USD cost, or None if no token data is available."""
    usage = TokenUsage(
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
        cache_read_tokens=cache_read_tokens or 0,
        cache_write_tokens=cache_write_tokens or 0,
    )
    if not usage.has_billable_usage:
        return None
    return resolve_pricing(models_used).estimate(usage)


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
