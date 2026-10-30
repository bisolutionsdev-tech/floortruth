"""Inference provider layer: MetaChatProvider built against the active MockProvider path.

NO Meta API key exists in this environment, so no live calls are attempted here.
- `MockProvider` is ACTIVE: deterministic, synthetic-only, cites only real
  observation IDs, never approves anything. Its usage figures are ESTIMATED
  (fixed demo vector: 2,000 in / 400 out tokens), not provider-reported.
- `MetaChatProvider` wraps app.meta_adapter.suggest and becomes active only when
  FLOORTRUTH_ENABLE_MODEL_API=true AND MODEL_API_KEY is set. Activation steps
  and the LIVE_API_NOT_VERIFIED status are documented in
  docs/LIVE_API_SMOKE_TEST.md. Never claim a live test succeeded.

Model output is advisory (SUGGESTED). Approvals, budgets and arithmetic stay in
deterministic application code.
"""
from __future__ import annotations
import time
import uuid
from typing import Protocol
from app import meta_adapter


class InferenceProvider(Protocol):
    name: str
    def analyze(self, case: dict, evidence: list[dict], evidence_fingerprint: str) -> dict: ...


class MockProvider:
    """Deterministic stand-in. Mirrors the Meta response contract without a network call."""
    name = "mock"
    # Fixed demo usage vector (matches the $0.00420 finops test vector); ESTIMATED, not reported.
    MOCK_INPUT_TOKENS = 2000
    MOCK_OUTPUT_TOKENS = 400

    def analyze(self, case: dict, evidence: list[dict], evidence_fingerprint: str) -> dict:
        started = time.monotonic()
        allowed = sorted({s["id"] for s in evidence})
        hyps = []
        topics = case.get("hypotheses") or []
        for i, h in enumerate(topics[:2]):
            hyps.append({
                "hypothesis_id": f"H{i+1}",
                "statement": h.get("claim", ""),
                "supporting_evidence_ids": allowed[:2],
                "contradicting_evidence_ids": [],
                "falsification_test": h.get("verify", ""),
                "status": "UNVERIFIED",
            })
        while len(hyps) < 2:  # contract requires at least two competing hypotheses
            hyps.append({
                "hypothesis_id": f"H{len(hyps)+1}",
                "statement": "The observed pattern may reflect an unmeasured common factor",
                "supporting_evidence_ids": allowed[:1],
                "contradicting_evidence_ids": [],
                "falsification_test": "Collect an independent comparator before concluding",
                "status": "UNVERIFIED",
            })
        duration_ms = int((time.monotonic() - started) * 1000)
        return {
            "mode": "demo",
            "provider": "mock",
            "model": "mock-deterministic-v1",
            "analysis": {
                "schema_version": "1.1",
                "case_id": case.get("id"),
                "source_fingerprint": evidence_fingerprint,
                "hypotheses": hyps,
                "missing_evidence": [case.get("missing_evidence", "Independent process measurement")],
                "pilot_proposal": "Test a voluntary readiness checklist at shift handoff",
                "safety_and_privacy_constraints": ["No worker ranking", "Supervisor review before use"],
                "causal_limit": "Uncontrolled observation; no verified cause",
                "proposed_by": "AI_ADVISORY_ONLY",
            },
            "evidence_ids": allowed,
            "evidence_fingerprint": evidence_fingerprint,
            "usage": {
                "input_tokens": self.MOCK_INPUT_TOKENS,
                "output_tokens": self.MOCK_OUTPUT_TOKENS,
                "cached_input_tokens": 0,
                "usage_source": "estimated",
            },
            "duration_ms": duration_ms,
            "request_id": uuid.uuid4().hex,
            "warning": "Mock provider: deterministic demo output. Usage is estimated, not provider-reported. "
                       "Explanations are UNVERIFIED suggestions, not facts.",
        }


class MetaChatProvider:
    """Live Meta Muse Chat Completions provider. Inactive without a configured key."""
    name = "meta"

    def is_configured(self) -> bool:
        return meta_adapter.enabled()

    def analyze(self, case: dict, evidence: list[dict], evidence_fingerprint: str) -> dict:
        if not self.is_configured():
            return {
                "mode": "unavailable", "provider": "meta", "model": None,
                "error_type": "NOT_CONFIGURED",
                "text": "Meta Model API is not configured (FLOORTRUTH_ENABLE_MODEL_API + MODEL_API_KEY). "
                        "See docs/LIVE_API_SMOKE_TEST.md. LIVE_API_NOT_VERIFIED.",
                "evidence_fingerprint": evidence_fingerprint,
                "usage": {"usage_source": "not_reported"},
                "request_id": uuid.uuid4().hex,
            }
        started = time.monotonic()
        result = meta_adapter.suggest(
            {"id": case.get("id"), "title": case.get("title"),
             "evidence_ids": [s["id"] for s in evidence]}, evidence)
        duration_ms = int((time.monotonic() - started) * 1000)
        usage = result.get("usage") or {}
        return {
            "mode": result.get("mode"), "provider": "meta",
            "model": result.get("model"), "analysis": result.get("analysis"),
            "text": result.get("text"), "evidence_ids": result.get("evidence_ids", []),
            "evidence_fingerprint": evidence_fingerprint,
            "usage": {
                "input_tokens": usage.get("prompt_tokens") or usage.get("input_tokens"),
                "output_tokens": usage.get("completion_tokens") or usage.get("output_tokens"),
                "cached_input_tokens": usage.get("cached_input_tokens", 0),
                "provider_total_tokens": usage.get("total_tokens"),
                "raw": usage,
                "usage_source": "reported" if usage else "not_reported",
                "provider_request_id": result.get("provider_request_id"),
            },
            "duration_ms": duration_ms,
            "request_id": uuid.uuid4().hex,
            "warning": result.get("warning"),
            "error_type": result.get("error_type"),
        }


def select_provider() -> InferenceProvider:
    """Active provider: Meta when configured, otherwise the mock path."""
    live = MetaChatProvider()
    return live if live.is_configured() else MockProvider()


def provider_status() -> dict:
    live = MetaChatProvider()
    configured = live.is_configured()
    return {
        "active_provider": "meta" if configured else "mock",
        "meta_configured": configured,
        "meta_model": "muse-spark-1.3",
        "live_api": "LIVE_API_NOT_VERIFIED" if not configured else "configured (unverified this run)",
        "mock_active": not configured,
        "note": "No Meta API key exists in this environment. Set MODEL_API_KEY + "
                "FLOORTRUTH_ENABLE_MODEL_API=true per docs/LIVE_API_SMOKE_TEST.md to activate.",
    }
