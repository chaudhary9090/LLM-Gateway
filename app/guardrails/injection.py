"""Prompt injection heuristic detection guardrail."""

import re
from typing import Tuple

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions|prompts|directives)", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions|directives)", re.IGNORECASE),
    re.compile(r"system\s+(?:override|prompt|reset)", re.IGNORECASE),
    re.compile(r"jailbreak\s+(?:mode|prompt|active)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:DAN|unfiltered|jailbroken)", re.IGNORECASE),
    re.compile(r"bypass\s+(?:safety|filter|guardrails)", re.IGNORECASE),
]


def detect_prompt_injection(text: str) -> Tuple[bool, str]:
    """Scans text for adversarial prompt injection heuristics.

    Returns:
        (is_injection, matched_pattern_description)
    """
    if not text:
        return False, ""

    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, match.group(0)

    return False, ""
