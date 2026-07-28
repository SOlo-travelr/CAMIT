"""Optional natural-language -> policy translator.

The LLM's ONLY job here is to emit JSON that conforms to the restricted policy
schema. It never executes code, assigns track IDs, or computes distances. The
output is always passed through :func:`validate_policy`, and the system runs
fully without any LLM credentials (``LLM_PROVIDER=none``).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from sentinel.policies.validator import (
    ValidationContext,
    ValidationOutcome,
    ValidationResult,
    validate_policy,
)

SCHEMA_HINT = """
Return ONLY a JSON object with this shape (no prose, no code):
{
  "policy_id": str, "name": str, "enabled": true,
  "scope": {"camera_ids": [str], "schedule": {"timezone": str, "days": [str], "start": "HH:MM", "end": "HH:MM"}},
  "subjects": {"primary": {"class": str}, "secondary": {"class": str}|null},
  "zones": {"include": [str], "exclude": [str]},
  "conditions": {"all": [
     {"type": "zone_entry"|"dwell_time"|"object_motion"|"proximity"|"predicted_separation",
      "subject": str|null, "subjects": [str]|null,
      "minimum_seconds": num|null, "minimum_speed_mps": num|null,
      "horizon_seconds": num|null, "threshold_meters": num|null}]},
  "event": {"type": "restricted_zone"|"loitering"|"proximity"|"collision_risk",
            "cooldown_seconds": int, "minimum_duration_ms": int,
            "severity": "low"|"medium"|"high"|"critical", "confidence_threshold": num},
  "evidence": {"pre_event_seconds": num, "post_event_seconds": num, "save_clip": bool, "save_snapshot": bool},
  "review": {"human_confirmation_required": bool}
}
Only use camera_ids and zones from the provided context. If information is
missing, still return valid JSON and list assumptions in the "name" field.
""".strip()


@dataclass
class TranslationResult:
    validation: ValidationResult
    raw_json: dict | None
    llm_used: bool
    missing_info: list[str]


class LanguageTranslator:
    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        self.provider = provider or os.getenv("LLM_PROVIDER", "none")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

    @property
    def enabled(self) -> bool:
        return self.provider not in ("none", "", None)

    def translate(self, text: str, context: ValidationContext) -> TranslationResult:
        if not self.enabled:
            return TranslationResult(
                validation=ValidationResult(
                    ValidationOutcome.REJECTED,
                    errors=[
                        "LLM policy translation is disabled (LLM_PROVIDER=none). "
                        "Author the policy YAML directly or enable a provider."
                    ],
                ),
                raw_json=None,
                llm_used=False,
                missing_info=[],
            )

        raw = self._call_llm(text, context)  # pragma: no cover - network dependent
        validation = validate_policy(raw, context)
        missing = [e for e in validation.errors if "Unknown" in e or "requires" in e]
        return TranslationResult(validation, raw, llm_used=True, missing_info=missing)

    def _call_llm(self, text: str, context: ValidationContext) -> dict:  # pragma: no cover
        from openai import OpenAI  # optional import

        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )
        system = (
            "You translate operator safety requests into a restricted policy JSON schema. "
            "You never write code. You only select from the allowed enums.\n"
            f"Allowed cameras: {sorted(context.camera_ids)}\n"
            f"Allowed zones: {sorted(context.zone_ids)}\n"
            f"{SCHEMA_HINT}"
        )
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(resp.choices[0].message.content or "{}")
