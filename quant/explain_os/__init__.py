"""ExplainOS — fact / computation / prediction / advice split with mandatory
provenance (v2.2 §8). Every recommendation surfaces source_url, updated_at,
cache status, formula version, per-weight contributions, risk penalty, price
plan and do-not-buy conditions. Forbidden promotional language is rejected."""

from quant.explain_os.language_guard import FORBIDDEN_PHRASES, check_text, scrub_payload
from quant.explain_os.score_breakdown import build_score_breakdown
from quant.explain_os.advice_card import build_advice_card

__all__ = [
    "FORBIDDEN_PHRASES",
    "check_text",
    "scrub_payload",
    "build_score_breakdown",
    "build_advice_card",
]
