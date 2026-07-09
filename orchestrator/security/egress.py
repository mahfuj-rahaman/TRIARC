"""Egress gatekeeper: redact secrets/PII before any payload reaches a cloud endpoint
(docs/security.md Face 1).

Runs locally, before a payload leaves the machine for a Tier 2/3 (Fireworks/cloud)
endpoint. Pattern-based (not full entropy analysis) -- catches known key prefixes,
bearer tokens, generic alphanumeric secrets, emails, phone numbers, and local file
paths. A cloud call additionally requires the task's own `constraints.privacy ==
cloud_ok` (checked here as defense in depth; the registry already enforces it at
resolution time -- see architecture.md #9).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from orchestrator.schema import Privacy

_DEFAULT_LOG_PATH = ".triarc/redaction.log"

_KNOWN_PREFIX_PATTERNS: dict[str, re.Pattern[str]] = {
    "api_key": re.compile(r"\b(?:sk|fw|pk|rk)-[A-Za-z0-9]{16,}\b"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9\-_.=]{16,}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "phone": re.compile(r"(?<!\w)\+?\d[\d\-\s()]{7,}\d(?!\w)"),
    "windows_path": re.compile(r"[A-Za-z]:\\(?:Users|home)\\[^\\\s]+(?:\\[^\\\s]+)*"),
    "unix_home_path": re.compile(r"/(?:home|Users)/[^/\s]+(?:/[^/\s]+)*"),
}
_GENERIC_TOKEN_PATTERN = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")


class PrivacyConsentError(RuntimeError):
    """Raised when a payload would leave the machine without constraints.privacy == cloud_ok."""


@dataclass
class RedactionFinding:
    kind: str
    matched: str


@dataclass
class GatekeeperResult:
    redacted_text: str
    findings: list[RedactionFinding] = field(default_factory=list)


def _looks_high_entropy(token: str) -> bool:
    has_digit = any(char.isdigit() for char in token)
    has_alpha = any(char.isalpha() for char in token)
    return has_digit and has_alpha


def redact(text: str, *, custom_patterns: dict[str, re.Pattern[str]] | None = None) -> GatekeeperResult:
    """Redact secrets/PII from TEXT, returning the redacted text and what was found."""
    findings: list[RedactionFinding] = []
    redacted = text

    patterns = dict(_KNOWN_PREFIX_PATTERNS)
    patterns.update(custom_patterns or {})

    for kind, pattern in patterns.items():
        def _replace(match: re.Match[str], kind: str = kind) -> str:
            findings.append(RedactionFinding(kind=kind, matched=match.group(0)))
            return f"[REDACTED:{kind}]"

        redacted = pattern.sub(_replace, redacted)

    def _replace_generic(match: re.Match[str]) -> str:
        token = match.group(0)
        if not _looks_high_entropy(token):
            return token
        findings.append(RedactionFinding(kind="generic_secret", matched=token))
        return "[REDACTED:generic_secret]"

    redacted = _GENERIC_TOKEN_PATTERN.sub(_replace_generic, redacted)

    return GatekeeperResult(redacted_text=redacted, findings=findings)


class EgressGatekeeper:
    """Enforces task privacy consent and redacts secrets/PII before a cloud call."""

    def __init__(self, *, log_path: str | Path | None = _DEFAULT_LOG_PATH) -> None:
        self._log_path = Path(log_path) if log_path else None

    def check(self, payload: str, *, privacy: Privacy) -> GatekeeperResult:
        if privacy != Privacy.CLOUD_OK:
            raise PrivacyConsentError(
                "payload requires constraints.privacy == cloud_ok to leave the machine"
            )
        result = redact(payload)
        if result.findings:
            self._log(result.findings)
        return result

    def _log(self, findings: list[RedactionFinding]) -> None:
        if self._log_path is None:
            return
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._log_path.open("a", encoding="utf-8") as log_file:
            for finding in findings:
                log_file.write(
                    json.dumps({"timestamp": timestamp, "kind": finding.kind, "matched": finding.matched})
                    + "\n"
                )
