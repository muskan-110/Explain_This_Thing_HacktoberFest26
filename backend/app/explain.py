import io
import json
import os
import time
import uuid
import base64
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image, ImageDraw

from backend.app.config import APPLIANCES_DIR, OLLAMA_VISION_MODEL
from backend.app.schemas import ExplainResponse, ExplainResult, Timings, ReadResult
from backend.app.ollama_client import OllamaClient
from backend.app.retrieval import retrieve_top_k
from backend.app.safety import check_safety
from backend.app.prompts import (
    READ_PROMPT,
    READ_JSON_SCHEMA,
    EXPLAIN_JSON_SCHEMA,
    build_explain_prompt
)
from backend.app.feedback import log_request
from backend.app.tracing import trace_span
from backend.app.textutils import has_devanagari, find_matching_chunk, try_this_is_filler, GENERIC_TRY_THIS
from backend.app.ocr import read_label_lines_at

# Speed/quality knobs (all overridable with environment variables).
READ_NUM_PREDICT = 80
EXPLAIN_NUM_PREDICT = 260          # Devanagari JSON needs room; 150 truncates it
MIN_RETRIEVAL_SCORE = float(os.getenv("MIN_RETRIEVAL_SCORE", "0.40"))
READ_WITH_FULL_IMAGE = os.getenv("READ_WITH_FULL_IMAGE", "0") == "1"
# Tight crop first (only the tapped button), wider crop only if nothing readable came back.
TIGHT_CROP_FRACTION = float(os.getenv("READ_CROP_TIGHT", "0.16"))
WIDE_CROP_FRACTION = float(os.getenv("READ_CROP_WIDE", "0.30"))


def process_crop_and_marker(
    img: Image.Image,
    x: float,
    y: float,
    crop_fraction: float = 0.22,
    min_side: int = 256,
) -> Tuple[Image.Image, Image.Image, str, str]:
    """
    Crops square around normalized (x,y), resizes to 512x512.
    Also creates a copy with a red ring marker around tap point.
    Returns: (cropped_img, marked_img, cropped_b64, marked_b64)
    """
    w, h = img.size
    cx = int(x * w)
    cy = int(y * h)

    side = int(max(min_side, crop_fraction * min(w, h)))
    side = max(2, min(side, w, h))   # never larger than the image, so the crop stays square
    half = side // 2

    left = cx - half
    top = cy - half
    right = cx + half
    bottom = cy + half

    if left < 0:
        right = min(w, right - left)
        left = 0
    if top < 0:
        bottom = min(h, bottom - top)
        top = 0
    if right > w:
        left = max(0, left - (right - w))
        right = w
    if bottom > h:
        top = max(0, top - (bottom - h))
        bottom = h

    cropped = img.crop((left, top, right, bottom)).resize((512, 512), Image.Resampling.LANCZOS)

    marked = img.copy().convert("RGB")
    draw = ImageDraw.Draw(marked)
    r = int(max(15, min(w, h) * 0.03))
    line_width = max(3, int(min(w, h) * 0.006))

    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        outline="red",
        width=line_width
    )

    def img_to_b64(image: Image.Image) -> str:
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    return cropped, marked, img_to_b64(cropped), img_to_b64(marked)


def build_query(read_result: ReadResult, question: Optional[str]) -> str:
    """Retrieval query from what was READ on the button. No appliance name: it made every chunk score alike."""
    parts = [read_result.label_text, read_result.icon_description, question or ""]
    return " ".join(p.strip() for p in parts if p and p.strip())


def _read(client: OllamaClient, images_b64: List[str]) -> Optional[ReadResult]:
    try:
        raw = client.generate_chat(
            prompt=READ_PROMPT,
            images_b64=images_b64,
            json_schema=READ_JSON_SCHEMA,
            model=OLLAMA_VISION_MODEL,
            temperature=0.0,
            num_predict=READ_NUM_PREDICT,
        )
        data = json.loads(raw)
        data.setdefault("looks_like", "")
        return ReadResult(**data)
    except Exception:
        return None


def _read_nothing(r: Optional[ReadResult]) -> bool:
    return r is None or not (r.label_text.strip() or r.icon_description.strip())


def _call_explain(client: OllamaClient, prompt: str) -> ExplainResult:
    # Text-only: the READ step already turned the image into label + icon text.
    raw = client.generate_chat(
        prompt=prompt,
        images_b64=None,
        json_schema=EXPLAIN_JSON_SCHEMA,
        model=OLLAMA_VISION_MODEL,
        temperature=0.0,
        num_predict=EXPLAIN_NUM_PREDICT,
    )
    data = json.loads(raw)
    data.pop("source_ref", None)
    data["source"] = "general_knowledge"      # decided by the server below
    data.setdefault("safety_flag", False)
    return ExplainResult(**data)


def _hindi_ok(card: ExplainResult) -> bool:
    return has_devanagari(card.what_it_does) and has_devanagari(card.try_this)


def run_explain_pipeline(
    appliance_id: Optional[str],
    image_bytes: Optional[bytes],
    x: float,
    y: float,
    question: Optional[str] = None,
    language: str = "en",
    use_kb: bool = True,
    client: Optional[OllamaClient] = None,
    appliance_type_hint: Optional[str] = None,
) -> ExplainResponse:
    """appliance_id=None is "quick mode": any uploaded photo, no saved notes, general knowledge only."""
    request_id = str(uuid.uuid4())
    if client is None:
        client = OllamaClient()

    timings = Timings()
    t_start = time.time()

    # Load appliance details (quick mode has no saved appliance)
    appliance_dir = APPLIANCES_DIR / appliance_id if appliance_id else None
    appliance_name = "Home Appliance"
    appliance_type = (appliance_type_hint or "").strip() or "appliance"

    if appliance_dir is not None:
        config_file = appliance_dir / "appliance.json"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    app_data = json.load(f)
                    appliance_name = app_data.get("name", appliance_name)
                    appliance_type = app_data.get("type", appliance_type)
            except Exception:
                pass
        use_kb_effective = use_kb
    else:
        use_kb_effective = False

    # Step 1: Crop & marker
    t0 = time.time()
    with trace_span("crop_image"):
        if image_bytes:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        else:
            panel_path = appliance_dir / "panel.jpg" if appliance_dir is not None else None
            if panel_path is None or not panel_path.exists():
                img = Image.new("RGB", (600, 800), color=(240, 240, 240))
            else:
                img = Image.open(panel_path).convert("RGB")

        cropped, marked, crop_b64, marked_b64 = process_crop_and_marker(
            img, x, y, crop_fraction=TIGHT_CROP_FRACTION, min_side=64
        )
    timings.crop_ms = round((time.time() - t0) * 1000, 2)

    # Step 2: READ the tapped button.
    #  (a) OCR: about a second on CPU, reads printed labels. (b) Gemma vision: slow on CPU, handles icon-only buttons.
    t0 = time.time()
    label_note = ""
    with trace_span("read_button", model_name=OLLAMA_VISION_MODEL):
        ocr_lines = None
        try:
            ocr_lines = read_label_lines_at(img, x, y)
        except Exception:
            ocr_lines = None

        if ocr_lines:
            ocr_label = " ".join(ocr_lines)
            read_result = ReadResult(label_text=ocr_label, icon_description="", looks_like="printed text (read by OCR)")
            if len(ocr_lines) > 1:
                # OCR does not read a lone "+" between lines, so say so instead of letting the model guess.
                label_note = (
                    f" (this is ONE button with {len(ocr_lines)} lines of text: {' / '.join(ocr_lines)}. "
                    "A '+' sign between the lines may be missed. A button naming two functions "
                    "usually runs them together.)"
                )
        else:
            # Tight crop first so neighbouring buttons cannot be mistaken for the tapped one.
            read_result = _read(client, [crop_b64] + ([marked_b64] if READ_WITH_FULL_IMAGE else []))
            if _read_nothing(read_result):
                # Nothing readable up close (e.g. an unusually big button): widen once.
                _, _, wide_b64, _ = process_crop_and_marker(
                    img, x, y, crop_fraction=WIDE_CROP_FRACTION, min_side=128
                )
                wide_result = _read(client, [wide_b64])
                if wide_result is not None:
                    read_result = wide_result
                    crop_b64 = wide_b64
            if read_result is None:
                read_result = ReadResult(label_text="", icon_description="", looks_like="")
    timings.read_ms = round((time.time() - t0) * 1000, 2)

    # Step 3: Retrieval, then a deterministic gate: a note HEADING must name the tapped button.
    t0 = time.time()
    retrieved_chunks: List[Dict[str, Any]] = []
    mode = "no_kb"
    query = build_query(read_result, question)

    if use_kb_effective and query and appliance_id:
        with trace_span("retrieve_kb"):
            retrieved_chunks, _best, _mode = retrieve_top_k(
                appliance_id=appliance_id,
                query=query,
                top_k=5,
                threshold=0.0,
                client=client
            )
        idx = find_matching_chunk(
            retrieved_chunks,
            read_result.label_text,
            read_result.icon_description,
            min_score=MIN_RETRIEVAL_SCORE,
        )
        if idx is not None:
            retrieved_chunks.insert(0, retrieved_chunks.pop(idx))
            mode = "kb"
    # Embedding happens inside retrieve_top_k, so embed time is included in retrieve_ms.
    timings.embed_ms = 0.0
    timings.retrieve_ms = round((time.time() - t0) * 1000, 2)
    chunk_ids = [c["chunk_id"] for c in retrieved_chunks]

    # Only the matched note goes to the model; unrelated passages invite mixed-up answers.
    passages_text = ""
    if mode == "kb" and retrieved_chunks:
        c = retrieved_chunks[0]
        passages_text = f"Note [{c['filename']} / {c['heading']}]:\n{c['content']}\n"

    # Step 4: EXPLAIN (text only), with one stricter retry if Hindi comes back in English
    t0 = time.time()
    card_result: Optional[ExplainResult] = None
    prompt_args = dict(
        appliance_name=appliance_name,
        appliance_type=appliance_type,
        label_text=read_result.label_text,
        icon_description=read_result.icon_description,
        user_question=question,
        passages_text=passages_text,
        language=language,
        use_kb=(mode == "kb"),
        label_note=label_note,
    )
    with trace_span("explain_button", model_name=OLLAMA_VISION_MODEL):
        try:
            card_result = _call_explain(client, build_explain_prompt(**prompt_args))
            if language == "hi" and not _hindi_ok(card_result):
                try:
                    retry = _call_explain(client, build_explain_prompt(**prompt_args, hindi_strict=True))
                except Exception:
                    retry = None
                if retry is not None and _hindi_ok(retry):
                    card_result = retry
                else:
                    if retry is not None:
                        card_result = retry
                    card_result.hindi_failed = True
        except Exception:
            card_result = ExplainResult(
                button_name=read_result.label_text or "Selected Button",
                what_it_does="Controls a setting or function on this appliance.",
                try_this="Press once to toggle or change setting.",
                confidence="low",
                source="general_knowledge",
                source_ref=None,
                passages_cover_button=False,
                safety_flag=False,
                hindi_failed=(language == "hi"),
            )
    timings.explain_ms = round((time.time() - t0) * 1000, 2)

    # Server-side enforcement: the model never decides source or source_ref.
    kb_ok = mode == "kb" and bool(retrieved_chunks) and card_result.passages_cover_button
    if kb_ok:
        top_c = retrieved_chunks[0]
        card_result.source = "knowledge_base"
        card_result.source_ref = f"{top_c['filename']} / {top_c['heading']}"
    else:
        mode = "no_kb"
        card_result.source = "general_knowledge"
        card_result.source_ref = None
        if card_result.confidence == "high":
            card_result.confidence = "medium"

    # Replace filler / misleading 'try this' lines with honest advice
    if try_this_is_filler(card_result.try_this, read_result.label_text):
        card_result.try_this = GENERIC_TRY_THIS.get(language, GENERIC_TRY_THIS["en"])

    # Step 5: Safety check
    is_unsafe, safe_advice = check_safety(
        read_result.label_text,
        question or "",
        card_result.what_it_does,
        card_result.try_this
    )
    if is_unsafe:
        card_result.safety_flag = True
        card_result.try_this = safe_advice

    timings.total_ms = round((time.time() - t_start) * 1000, 2)

    # Step 6: Log request
    log_request(
        request_id=request_id,
        appliance_id=appliance_id or "quick",
        timings=timings.model_dump(),
        mode=mode,
        retrieved_chunk_ids=chunk_ids,
        output=card_result.model_dump(),
        model_name=OLLAMA_VISION_MODEL
    )

    retrieved_chunk_infos = [
        {
            "chunk_id": c["chunk_id"],
            "filename": c["filename"],
            "heading": c["heading"],
            "content": c["content"],
            "score": round(float(c.get("score", 0.0)), 4)
        }
        for c in retrieved_chunks
    ]

    return ExplainResponse(
        request_id=request_id,
        card=card_result,
        read_result=read_result,
        retrieved_chunks=retrieved_chunk_infos,
        timings=timings,
        mode=mode,
        cropped_image_base64=crop_b64,
        marked_image_base64=marked_b64
    )
