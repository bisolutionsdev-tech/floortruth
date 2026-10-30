"""Versioned pricebook and deterministic inference cost math.

- All money is integer USD micros (1 USD = 1,000,000 micros). No binary float.
- Rates are Meta Standard text-model rates published at
  https://dev.meta.ai/docs/pricing-rate-limits (retrieved 2026-10-29).
  Historical/illustrative snapshot: each entry carries effective_from,
  citation_url and last_verified_at. Do not hard-code forever — recheck
  before production use.
- Unknown usage or missing prices -> cost None (null), never $0.00.
"""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass

PRICEBOOK_VERSION = "2026-10-29"
PRICING_SOURCE_URL = "https://dev.meta.ai/docs/pricing-rate-limits"
PRICING_VERIFIED_AT = "2026-10-29"

# Seed: (model, meter, unit, rate_per_unit_micros, notes)
# Text meters are per 1M tokens; audio/image/frame/search are per unit.
PRICEBOOK_SEED: list[tuple[str, str, str, int, str]] = [
    # Muse Spark — $1.25 / $0.15 / $4.25 per 1M input / cached / output
    ("muse-spark-1.3", "input_text", "per_1m_tokens", 1_250_000, "Standard text input"),
    ("muse-spark-1.3", "cached_input_text", "per_1m_tokens", 150_000, "Standard cached input"),
    ("muse-spark-1.3", "output_text", "per_1m_tokens", 4_250_000, "Standard text output"),
    ("muse-spark-1.2", "input_text", "per_1m_tokens", 1_250_000, "Standard text input"),
    ("muse-spark-1.2", "cached_input_text", "per_1m_tokens", 150_000, "Standard cached input"),
    ("muse-spark-1.2", "output_text", "per_1m_tokens", 4_250_000, "Standard text output"),
    ("muse-spark-1.1", "input_text", "per_1m_tokens", 1_250_000, "Standard text input"),
    ("muse-spark-1.1", "cached_input_text", "per_1m_tokens", 150_000, "Standard cached input"),
    ("muse-spark-1.1", "output_text", "per_1m_tokens", 4_250_000, "Standard text output"),
    # Muse Wonder — $4.00 / $0.20 / $20.00 per 1M input / cached / output
    ("muse-wonder-1.0", "input_text", "per_1m_tokens", 4_000_000, "Standard text input"),
    ("muse-wonder-1.0", "cached_input_text", "per_1m_tokens", 200_000, "Standard cached input"),
    ("muse-wonder-1.0", "output_text", "per_1m_tokens", 20_000_000, "Standard text output"),
    # Muse Voice Transcribe — $0.18 per audio hour  => 50 micros per audio second
    ("muse-voice-transcribe-1.0", "audio_seconds", "audio_second", 50, "$0.18/hour"),
    # SAM 3.1 — $2.50 per 1,000 images; $0.20 per 1,000 video frames (min 50 frames/request)
    ("sam-3.1", "images", "image", 2_500, "$2.50 per 1,000 images"),
    ("sam-3.1", "video_frames", "video_frame", 200, "$0.20 per 1,000 frames; min 50 frames billed per request"),
    # Muse Image — $0.01 per returned image
    ("muse-image-1.0", "generated_images", "generated_image", 10_000, "$0.01 per returned image"),
    # Web search grounding — $2.50 per 1,000 searches, plus model token cost
    ("web-search-grounding", "searches", "search_query", 2_500, "$2.50 per 1,000 searches; model tokens billed separately"),
]


class InvalidUsageError(ValueError):
    """Provider usage is internally inconsistent; never silently capped."""


class UnknownPriceError(ValueError):
    """No effective pricebook entry for this model/meter; cost is null, not zero."""


@dataclass
class CostResult:
    cost_usd_micros: int | None
    pricebook_version: str
    breakdown_micros: dict
    usage_source: str
    assumptions: list

    @property
    def cost_usd_6dp(self) -> str | None:
        if self.cost_usd_micros is None:
            return None
        return f"{self.cost_usd_micros / 1_000_000:.6f}"


def seed_pricebook(db: sqlite3.Connection, version: str = PRICEBOOK_VERSION) -> int:
    """Idempotent seed of the versioned pricebook. Returns rows present."""
    for model, meter, unit, rate, notes in PRICEBOOK_SEED:
        db.execute(
            "INSERT OR IGNORE INTO pricebook_entries "
            "(version, provider, model, mode, meter, unit, rate_per_unit_micros, "
            "effective_from, citation_url, last_verified_at, notes) "
            "VALUES (?, 'meta', ?, 'standard', ?, ?, ?, '2026-10-29', ?, ?, ?)",
            (version, model, meter, unit, rate, PRICING_SOURCE_URL, PRICING_VERIFIED_AT, notes),
        )
    db.commit()
    return db.execute(
        "SELECT COUNT(*) FROM pricebook_entries WHERE version = ?", (version,)
    ).fetchone()[0]


def _rate(db: sqlite3.Connection, version: str, model: str, meter: str) -> int:
    row = db.execute(
        "SELECT rate_per_unit_micros FROM pricebook_entries "
        "WHERE version=? AND provider='meta' AND model=? AND meter=? "
        "AND effective_from <= '2026-10-29' AND (effective_to IS NULL OR effective_to > '2026-10-29')",
        (version, model, meter),
    ).fetchone()
    if row is None or row[0] is None:
        raise UnknownPriceError(f"No effective price for {model}/{meter} in pricebook {version}")
    return int(row[0])


def _meter_cost(quantity: int, rate_per_unit_micros: int, unit: str) -> int:
    if unit == "per_1m_tokens":
        return (quantity * rate_per_unit_micros) // 1_000_000
    return quantity * rate_per_unit_micros


def cost_for_usage(
    db: sqlite3.Connection,
    model: str,
    *,
    input_tokens: int | None = None,
    cached_input_tokens: int | None = None,
    output_tokens: int | None = None,
    usage_source: str = "reported",
    version: str = PRICEBOOK_VERSION,
    audio_seconds: int | None = None,
    images: int | None = None,
    video_frames: int | None = None,
    generated_images: int | None = None,
    searches: int | None = None,
) -> CostResult:
    """Deterministic cost of one inference attempt. Integer micros; None if unknown.

    Cached input is charged once at the cache rate and deducted from the
    uncached input quantity — never both at full price. Unknown cache with
    known input is treated as uncached (documented assumption).
    """
    for name, value in (("input_tokens", input_tokens), ("cached_input_tokens", cached_input_tokens),
                        ("output_tokens", output_tokens)):
        if value is not None and value < 0:
            raise InvalidUsageError(f"{name} must be non-negative")
    if (input_tokens is not None and cached_input_tokens is not None
            and cached_input_tokens > input_tokens):
        raise InvalidUsageError("cached_input_tokens exceeds input_tokens; refusing to silently cap")

    quantities = {
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "audio_seconds": audio_seconds, "images": images, "video_frames": video_frames,
        "generated_images": generated_images, "searches": searches,
    }
    if all(v is None for v in quantities.values()):
        return CostResult(None, version, {}, usage_source,
                          ["No provider usage reported; cost unavailable, not $0.00"])

    meter_for = {
        "input_tokens": "input_text", "output_tokens": "output_text",
        "audio_seconds": "audio_seconds", "images": "images",
        "video_frames": "video_frames", "generated_images": "generated_images",
        "searches": "searches",
    }
    unit_for = {
        "input_tokens": "per_1m_tokens", "output_tokens": "per_1m_tokens",
        "audio_seconds": "audio_second", "images": "image",
        "video_frames": "video_frame", "generated_images": "generated_image",
        "searches": "search_query",
    }
    breakdown: dict[str, int] = {}
    assumptions: list[str] = []
    total = 0

    if input_tokens is not None:
        cached = cached_input_tokens or 0
        if cached_input_tokens is None:
            assumptions.append("cached_input_tokens not reported; treated as 0 (all input uncached)")
        uncached = input_tokens - cached
        rate = _rate(db, version, model, "input_text")
        breakdown["input_text_micros"] = _meter_cost(uncached, rate, "per_1m_tokens")
        total += breakdown["input_text_micros"]
        if cached:
            cache_rate = _rate(db, version, model, "cached_input_text")
            breakdown["cached_input_text_micros"] = _meter_cost(cached, cache_rate, "per_1m_tokens")
            total += breakdown["cached_input_text_micros"]

    for key in ("output_tokens", "audio_seconds", "images", "video_frames",
                "generated_images", "searches"):
        qty = quantities[key]
        if qty is None:
            continue
        rate = _rate(db, version, model, meter_for[key])
        part = _meter_cost(qty, rate, unit_for[key])
        breakdown[f"{meter_for[key]}_micros"] = part
        total += part

    return CostResult(total, version, breakdown, usage_source, assumptions)


def estimate_cost(
    db: sqlite3.Connection,
    model: str,
    max_input_tokens: int,
    max_output_tokens: int,
    version: str = PRICEBOOK_VERSION,
) -> CostResult:
    """Deterministic pre-call cost forecast (upper bound, no LLM involved)."""
    return cost_for_usage(
        db, model, input_tokens=max_input_tokens, output_tokens=max_output_tokens,
        usage_source="estimated", version=version,
    )


def micros_to_usd_str(micros: int | None, decimals: int = 6) -> str | None:
    if micros is None:
        return None
    return f"{micros / 1_000_000:.{decimals}f}"
