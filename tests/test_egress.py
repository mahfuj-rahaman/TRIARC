import json

import pytest

from orchestrator.schema import Privacy
from orchestrator.security.egress import EgressGatekeeper, PrivacyConsentError, redact


def test_redact_masks_known_prefix_api_key():
    result = redact("here is my key sk-abcdEFGH12345678zzz, use it")

    assert "sk-abcdEFGH12345678zzz" not in result.redacted_text
    assert "[REDACTED:api_key]" in result.redacted_text
    assert result.findings[0].kind == "api_key"


def test_redact_masks_email():
    result = redact("contact me at jane.doe@example.com please")

    assert "jane.doe@example.com" not in result.redacted_text
    assert "[REDACTED:email]" in result.redacted_text


def test_redact_masks_phone_number():
    result = redact("call me at 415-555-0132 tomorrow")

    assert "415-555-0132" not in result.redacted_text
    assert "[REDACTED:phone]" in result.redacted_text


def test_redact_masks_windows_home_path():
    result = redact(r"the file lives at C:\Users\mahfuj\secrets.txt")

    assert "mahfuj" not in result.redacted_text
    assert "[REDACTED:windows_path]" in result.redacted_text


def test_redact_masks_generic_high_entropy_token():
    token = "aB3dE9fGhJ2kLmN8pQrS5tUvW1xYz012"
    result = redact(f"token={token}")

    assert token not in result.redacted_text
    assert any(f.kind == "generic_secret" for f in result.findings)


def test_redact_leaves_plain_long_word_alone():
    word = "supercalifragilisticexpialidocioussupercalifragilistic"
    result = redact(f"the word is {word}")

    assert word in result.redacted_text
    assert result.findings == []


def test_redact_leaves_clean_text_untouched():
    result = redact("scaffold a login route with a username field")

    assert result.redacted_text == "scaffold a login route with a username field"
    assert result.findings == []


def test_gatekeeper_rejects_local_privacy():
    gatekeeper = EgressGatekeeper(log_path=None)

    with pytest.raises(PrivacyConsentError):
        gatekeeper.check("hello", privacy=Privacy.LOCAL)


def test_gatekeeper_logs_findings_to_local_file(tmp_path):
    log_path = tmp_path / "redaction.log"
    gatekeeper = EgressGatekeeper(log_path=log_path)

    gatekeeper.check("email me at jane.doe@example.com", privacy=Privacy.CLOUD_OK)

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["kind"] == "email"
    assert entry["matched"] == "jane.doe@example.com"


def test_gatekeeper_does_not_create_log_file_when_nothing_found(tmp_path):
    log_path = tmp_path / "redaction.log"
    gatekeeper = EgressGatekeeper(log_path=log_path)

    gatekeeper.check("scaffold a login route", privacy=Privacy.CLOUD_OK)

    assert not log_path.exists()
