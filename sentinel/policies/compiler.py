"""Deterministic policy compiler: validated :class:`Policy` -> engine rules.

No generated code is ever executed. The compiler maps the restricted schema onto
concrete rule objects the event engine understands.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from sentinel.policies.models import Policy
from sentinel.policies.validator import (
    ValidationContext,
    ValidationResult,
    validate_policy,
)


def load_policy_file(path: str | Path) -> Policy:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Policy.model_validate(raw)


def compile_policy(raw: dict, context: ValidationContext) -> ValidationResult:
    """Validate then return the compiled policy (as the validated model)."""
    return validate_policy(raw, context)


def load_policies_dir(directory: str | Path) -> list[Policy]:
    policies: list[Policy] = []
    for p in sorted(Path(directory).glob("*.yaml")):
        policies.append(load_policy_file(p))
    return policies
