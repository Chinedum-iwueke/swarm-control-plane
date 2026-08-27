from __future__ import annotations

import re

_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----", re.IGNORECASE
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PRIVATE_KEY|API_KEY)\s*=\s*\S+"
)
_KNOWN_TOKEN = re.compile(
    r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|\d{6,12}:[A-Za-z0-9_-]{25,}|gh[oprsu]_[A-Za-z0-9]{20,})"
)
_SUDO_PASSWORD = re.compile(
    r"(?i)(?:sudo\s+password|password\s+for\s+[A-Za-z0-9._-]+)\s*[:=]\s*\S+"
)


def prohibited_input_reason(text: str, *, max_chars: int) -> str | None:
    if len(text) > max_chars:
        return "message_too_large"
    if _PRIVATE_KEY.search(text):
        return "private_key"
    if _SECRET_ASSIGNMENT.search(text):
        return "secret_assignment"
    if _KNOWN_TOKEN.search(text):
        return "credential_token"
    if _SUDO_PASSWORD.search(text):
        return "sudo_password"
    return None
