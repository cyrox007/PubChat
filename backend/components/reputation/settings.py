from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReputationAIConfig:
    provider: str
    endpoint: str
    api_key: str
    model: str
    timeout_seconds: float
    assessment_ttl_hours: int
    behavior_window_days: int
    enforcement_mode: str

    def configured(self) -> bool:
        if self.provider == "disabled":
            return False
        if self.provider == "http_json":
            return bool(self.endpoint)
        return False


def load_reputation_ai_config() -> ReputationAIConfig:
    provider = os.getenv("REPUTATION_AI_PROVIDER", "disabled").strip().lower() or "disabled"
    enforcement_mode = os.getenv("REPUTATION_ENFORCEMENT_MODE", "required").strip().lower() or "required"
    if enforcement_mode not in {"required", "shadow"}:
        enforcement_mode = "required"
    return ReputationAIConfig(
        provider=provider,
        endpoint=os.getenv("REPUTATION_AI_ENDPOINT", "").strip(),
        api_key=os.getenv("REPUTATION_AI_API_KEY", ""),
        model=os.getenv("REPUTATION_AI_MODEL", "").strip(),
        timeout_seconds=max(1.0, float(os.getenv("REPUTATION_AI_TIMEOUT_SECONDS", "15"))),
        assessment_ttl_hours=max(1, min(24 * 30, int(os.getenv("REPUTATION_AI_TTL_HOURS", "168")))),
        behavior_window_days=max(7, min(365, int(os.getenv("REPUTATION_BEHAVIOR_WINDOW_DAYS", "90")))),
        enforcement_mode=enforcement_mode,
    )


reputation_ai_config = load_reputation_ai_config()
