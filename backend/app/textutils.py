"""Small, dependency-free helpers: Devanagari detection and note-heading matching."""
import re
from typing import Any, Dict, List, Optional

# Generic words that say nothing about WHICH button it is.
_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into",
    "button", "buttons", "key", "icon", "symbol", "sign", "mark", "shape", "shaped",
    "image", "picture", "text", "label", "printed", "none", "unknown",
    "blue", "red", "green", "white", "black", "grey", "gray", "yellow", "orange",
    "round", "square", "small", "large", "line", "lines", "circle",
    "off",  # "ON/OFF" says nothing about which button it is; the icon decides
}


def has_devanagari(text: Optional[str]) -> bool:
    """True if the text contains at least one Devanagari (Hindi) character."""
    return any("\u0900" <= ch <= "\u097f" for ch in (text or ""))


def meaningful_tokens(text: Optional[str]) -> List[str]:
    """Lower-case words of 3+ letters that are not generic filler."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [w for w in words if len(w) >= 3 and w not in _STOPWORDS]


def _word_start_match(haystack: str, token: str) -> bool:
    variants = {token}
    if token.endswith("s") and len(token) > 4:
        variants.add(token[:-1])
    return any(re.search(r"\b" + re.escape(v), haystack) for v in variants)


# Buttons with no word on them. These words are what a note heading would plausibly use.
_SYMBOL_ALIASES = {
    "+": ["temperature", "temp", "increase", "up"],
    "-": ["temperature", "temp", "decrease", "down"],
    "\u2212": ["temperature", "temp", "decrease", "down"],
}


def heading_matches_read(heading: Optional[str], label_text: Optional[str], icon_description: Optional[str]) -> bool:
    """
    Does a note heading plausibly name the button the model read?
    - If the label has meaningful words, the heading must share one of them.
    - Only when the label has none (e.g. "ON/OFF") do we fall back to the icon words.
    """
    heading_l = (heading or "").lower()
    symbol = (label_text or "").strip()
    if symbol in _SYMBOL_ALIASES:
        return any(_word_start_match(heading_l, t) for t in _SYMBOL_ALIASES[symbol])
    label_tokens = meaningful_tokens(label_text)
    if label_tokens:
        return any(_word_start_match(heading_l, t) for t in label_tokens)
    return any(_word_start_match(heading_l, t) for t in meaningful_tokens(icon_description))


def find_matching_chunk(
    chunks: List[Dict[str, Any]],
    label_text: Optional[str],
    icon_description: Optional[str],
    min_score: float = 0.0,
) -> Optional[int]:
    """Index of the best-scoring chunk whose HEADING names the tapped button, else None."""
    for i, chunk in enumerate(chunks):
        if float(chunk.get("score", 0.0)) < min_score:
            continue
        if heading_matches_read(chunk.get("heading"), label_text, icon_description):
            return i
    return None


# ---- "Try this" guard -------------------------------------------------------------------------
# Without a manual note, a 4B model often writes filler ("I'm not sure, but press it to start"), and a
# confident-sounding "press it to start" is wrong for mode buttons. Replace that with honest advice.

GENERIC_TRY_THIS = {
    "en": "Not sure how to use it? Check the manual or ask someone before pressing.",
    "hi": "इसे कैसे इस्तेमाल करना है, पक्का नहीं है। दबाने से पहले मैनुअल देखें या किसी से पूछ लें।",
}

_FILLER_PATTERNS = [
    r"not sure", r"don'?t know", r"do not know", r"see what happens", r"try it and see",
    "\u092a\u0915\u094d\u0915\u093e \u0928\u0939\u0940\u0902",      # "pakka nahin" (not sure)
    "\u0915\u094d\u092f\u093e \u0939\u094b\u0924\u093e \u0939\u0948",  # "kya hota hai" (see what happens)
]
_CLAIMS_START = re.compile(r"\b(to start|start it|start cooking|starts? the|to begin|turns? (it )?on)\b")
_START_LABEL_WORDS = {"start", "power", "on", "off", "begin", "run", "cook", "cooking", "stop"}


def try_this_is_filler(text: Optional[str], label_text: Optional[str]) -> bool:
    """True if the 'try this' line is a non-answer, or claims the button starts something its label does not say."""
    t = (text or "").lower()
    if not t.strip():
        return True
    if any(re.search(p, t) for p in _FILLER_PATTERNS):
        return True
    if _CLAIMS_START.search(t):
        label_words = set(re.findall(r"[a-z]+", (label_text or "").lower()))
        if not (label_words & _START_LABEL_WORDS):
            return True
    return False
