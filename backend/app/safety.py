import re
from typing import Tuple

SAFETY_KEYWORDS = [
    r"\bgas\b",
    r"\bburn(ing)?\b",
    r"\bsmell\b",
    r"\bsmoke\b",
    r"\bspark(s|ing)?\b",
    r"\b(electric\s+)?shock\b",
    r"\bwater\b",
    r"\bleak(ing)?\b",
    r"\berror\b",
    r"\bfault\b",
    r"\bwarning\b",
    r"\bdanger\b",
    r"\bhazard\b",
    r"\bcode\b",
    r"\be[0-9]{1,2}\b",
    r"\bf[0-9]{1,2}\b"
]

SAFE_ADVICE = "Switch it off and ask someone you trust."

def check_safety(*texts: str) -> Tuple[bool, str]:
    """
    Checks if any input text contains safety hazards or warning indicators.
    Returns (is_unsafe: bool, warning_message: str)
    """
    combined_text = " ".join([t for t in texts if t]).lower()
    for pattern in SAFETY_KEYWORDS:
        if re.search(pattern, combined_text):
            return True, SAFE_ADVICE
    return False, ""
