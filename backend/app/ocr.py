"""
Optional fast path: read the printed label under the user's tap with a small open-source OCR
(RapidOCR, models bundled in the pip package, runs offline on CPU in about a second).

If RapidOCR is not installed, or finds no text at the tap, callers fall back to the Gemma vision READ.
"""
import hashlib
import os
import threading
from collections import OrderedDict
from typing import Dict, List, Optional

from PIL import Image

USE_OCR = os.getenv("USE_OCR", "1") != "0"
OCR_MAX_SIDE = 1280          # larger photos are shrunk for OCR only
MIN_OCR_SCORE = 0.5
_CACHE_SIZE = 8

_engine = None
_engine_failed = False
_lock = threading.Lock()
_cache: "OrderedDict[str, List[Dict]]" = OrderedDict()


def _get_engine():
    global _engine, _engine_failed
    if _engine is not None or _engine_failed:
        return _engine
    with _lock:
        if _engine is None and not _engine_failed:
            try:
                from rapidocr import RapidOCR  # imported lazily: it is an optional dependency
                _engine = RapidOCR()
            except Exception:
                _engine_failed = True
    return _engine


def ocr_available() -> bool:
    return USE_OCR and _get_engine() is not None


def warm_up() -> None:
    if USE_OCR:
        _get_engine()


def read_text_boxes(img: Image.Image) -> List[Dict]:
    """All text found in the image as [{text, score, x0, y0, x1, y1}] in ORIGINAL pixel coordinates."""
    engine = _get_engine()
    if engine is None:
        return []

    key = hashlib.md5(img.tobytes()).hexdigest() + f"{img.size}"
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]

    w, h = img.size
    scale = min(1.0, OCR_MAX_SIDE / max(w, h))
    work = img if scale == 1.0 else img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)

    import numpy as np
    result = engine(np.array(work.convert("RGB"))[:, :, ::-1])      # RapidOCR expects BGR
    items: List[Dict] = []
    if result is not None and result.boxes is not None and result.txts is not None:
        scores = result.scores if result.scores is not None else [1.0] * len(result.txts)
        for box, text, score in zip(result.boxes, result.txts, scores):
            xs = [float(p[0]) / scale for p in box]
            ys = [float(p[1]) / scale for p in box]
            items.append({
                "text": str(text).strip(),
                "score": float(score),
                "x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys),
            })

    _cache[key] = items
    while len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)
    return items


def _stack_group(seed: Dict, items: List[Dict], min_score: float, max_lines: int = 4) -> List[Dict]:
    """
    A button label is often several lines (e.g. MICROWAVE / + / GRILL) and OCR returns one box per line.
    Grow a group from the seed by adding boxes that sit directly above/below it: they must overlap it
    horizontally and be separated by less than ~0.6 of a text height. Boxes on neighbouring buttons are
    either beside the label (no horizontal overlap) or a full button-pitch away, so they stay out.
    """
    group = [seed]
    x0, y0, x1, y1 = seed["x0"], seed["y0"], seed["x1"], seed["y1"]
    grew = True
    while grew and len(group) < max_lines:
        grew = False
        for it in items:
            if any(it is g for g in group) or not it["text"] or it["score"] < min_score:
                continue
            overlap = min(x1, it["x1"]) - max(x0, it["x0"])
            narrower = min(x1 - x0, it["x1"] - it["x0"])
            if overlap <= 0 or overlap < 0.25 * max(1.0, narrower):
                continue
            gap = max(it["y0"] - y1, y0 - it["y1"])           # negative when the boxes overlap vertically
            ref_h = max(y1 - y0, it["y1"] - it["y0"], 1.0)
            if gap > 0.6 * ref_h:
                continue
            group.append(it)
            x0, y0 = min(x0, it["x0"]), min(y0, it["y0"])
            x1, y1 = max(x1, it["x1"]), max(y1, it["y1"])
            grew = True
            if len(group) >= max_lines:
                break
    return group


def choose_label_lines_at(items: List[Dict], tap_x: float, tap_y: float, min_score: float = MIN_OCR_SCORE) -> Optional[List[str]]:
    """
    Pick the text whose box contains the tap, or sits within about one text-height of it, then join the
    other lines of the same button (see _stack_group). Anything farther away belongs to a different
    button, so return None (icon-only button, etc.).
    """
    seed, best_dist = None, None
    for it in items:
        text = it["text"]
        if not text or it["score"] < min_score or not any(ch.isalnum() for ch in text):
            continue
        dx = max(it["x0"] - tap_x, 0.0, tap_x - it["x1"])
        dy = max(it["y0"] - tap_y, 0.0, tap_y - it["y1"])
        dist = (dx * dx + dy * dy) ** 0.5
        height = max(1.0, it["y1"] - it["y0"])
        if dist > height:
            continue
        if best_dist is None or dist < best_dist:
            seed, best_dist = it, dist
    if seed is None:
        return None
    group = sorted(_stack_group(seed, items, min_score), key=lambda g: (round(g["y0"] / 8), g["x0"]))
    return [g["text"] for g in group]


def choose_label_at(items: List[Dict], tap_x: float, tap_y: float, min_score: float = MIN_OCR_SCORE) -> Optional[str]:
    lines = choose_label_lines_at(items, tap_x, tap_y, min_score)
    return " ".join(lines) if lines else None


def read_label_lines_at(img: Image.Image, x: float, y: float) -> Optional[List[str]]:
    """x, y are normalized (0-1). Returns the printed label lines of the tapped button, or None."""
    if not USE_OCR:
        return None
    items = read_text_boxes(img)
    if not items:
        return None
    w, h = img.size
    return choose_label_lines_at(items, x * w, y * h)


def read_label_at(img: Image.Image, x: float, y: float) -> Optional[str]:
    lines = read_label_lines_at(img, x, y)
    return " ".join(lines) if lines else None
