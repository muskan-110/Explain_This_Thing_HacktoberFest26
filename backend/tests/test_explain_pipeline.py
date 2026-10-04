import json
import pytest

from backend.app import explain as explain_mod
from backend.app.explain import run_explain_pipeline
from backend.app.textutils import has_devanagari

CHUNKS = [
    {"chunk_id": "a::notes.md::Mode Selection::1", "filename": "notes.md", "heading": "Mode Selection",
     "content": "Switches between Cool, Heat, Dry and Fan Only.", "score": 0.70},
    {"chunk_id": "a::notes.md::Fan speed::2", "filename": "notes.md", "heading": "Fan speed",
     "content": "Controls how strongly the air blows. Press repeatedly to cycle Low, Medium, High, Auto.", "score": 0.66},
    {"chunk_id": "a::notes.md::Timer::3", "filename": "notes.md", "heading": "Timer",
     "content": "Sets when the AC turns off.", "score": 0.50},
]

EN_CARD = {
    "button_name": "FAN SPEED", "what_it_does": "Controls how strongly the air blows.",
    "try_this": "Press it to change the speed.", "confidence": "high",
    "source": "knowledge_base", "source_ref": "", "passages_cover_button": True, "safety_flag": False,
}
HI_CARD = dict(EN_CARD, what_it_does="यह हवा की तेज़ी बदलता है।", try_this="इसे दबाकर गति बदलें।")


class FakeClient:
    """Stands in for Ollama. READ calls return `read`; EXPLAIN calls pop from `explain_queue`."""
    def __init__(self, label="FAN SPEED", icon="fan blades", explain_queue=None, read_queue=None):
        first = {"label_text": label, "icon_description": icon, "looks_like": "blue button"}
        self.read_queue = list(read_queue or [first])
        self.explain_queue = list(explain_queue or [EN_CARD])
        self.explain_calls = []
        self.read_calls = []

    def generate_chat(self, prompt, images_b64=None, json_schema=None, **kw):
        if "inspecting a button" in prompt:
            self.read_calls.append(images_b64)
            item = self.read_queue.pop(0) if len(self.read_queue) > 1 else self.read_queue[0]
            return json.dumps(item)
        self.explain_calls.append({"prompt": prompt, "images": images_b64})
        item = self.explain_queue.pop(0) if len(self.explain_queue) > 1 else self.explain_queue[0]
        return json.dumps(item)


@pytest.fixture(autouse=True)
def patch_io(monkeypatch):
    monkeypatch.setattr(explain_mod, "retrieve_top_k", lambda **kw: ([dict(c) for c in CHUNKS], 0.7, "kb"))
    monkeypatch.setattr(explain_mod, "log_request", lambda **kw: None)
    monkeypatch.setattr(explain_mod, "read_label_lines_at", lambda img, x, y: None)   # tests below opt in to OCR


def run(client, **kw):
    return run_explain_pipeline("nope", None, 0.3, 0.4, client=client, **kw)


def test_button_in_notes_cites_the_matching_heading():
    r = run(FakeClient())
    assert r.mode == "kb"
    assert r.card.source == "knowledge_base"
    assert r.card.source_ref == "notes.md / Fan speed"      # not Mode Selection, even though it scored higher
    assert r.retrieved_chunks[0].heading == "Fan speed"


def test_button_not_in_notes_never_gets_a_citation():
    r = run(FakeClient(label="IONIZER", icon="air purifier with wavy lines"))
    assert r.mode == "no_kb"
    assert r.card.source == "general_knowledge"
    assert r.card.source_ref is None
    assert r.card.confidence == "medium"                    # capped from "high"


def test_model_saying_notes_do_not_cover_it_downgrades():
    r = run(FakeClient(explain_queue=[dict(EN_CARD, passages_cover_button=False)]))
    assert r.card.source == "general_knowledge" and r.card.source_ref is None and r.mode == "no_kb"


def test_use_kb_false_is_general_knowledge():
    r = run(FakeClient(), use_kb=False)
    assert r.card.source == "general_knowledge" and r.card.source_ref is None


def test_explain_step_is_text_only():
    c = FakeClient()
    run(c)
    assert c.explain_calls and all(call["images"] is None for call in c.explain_calls)


def test_hindi_retry_fixes_english_answer():
    c = FakeClient(explain_queue=[EN_CARD, HI_CARD])
    r = run(c, language="hi")
    assert len(c.explain_calls) == 2
    assert "IMPORTANT" in c.explain_calls[1]["prompt"]
    assert has_devanagari(r.card.what_it_does) and has_devanagari(r.card.try_this)
    assert r.card.hindi_failed is False
    assert r.card.source_ref == "notes.md / Fan speed"


def test_hindi_failure_is_flagged_not_hidden():
    r = run(FakeClient(explain_queue=[EN_CARD]), language="hi")
    assert r.card.hindi_failed is True


def test_invariant_knowledge_base_always_has_source_ref():
    for label in ["FAN SPEED", "TIMER", "IONIZER", "ON/OFF", ""]:
        r = run(FakeClient(label=label))
        if r.card.source == "knowledge_base":
            assert r.card.source_ref
        else:
            assert r.card.source_ref is None


def test_burning_smell_triggers_safety_line():
    r = run(FakeClient(), question="there is a burning smell")
    assert r.card.safety_flag is True
    assert "ask someone you trust" in r.card.try_this


def test_read_uses_only_the_tight_crop_when_it_finds_text():
    c = FakeClient()
    run(c)
    assert len(c.read_calls) == 1 and len(c.read_calls[0]) == 1


def test_read_widens_once_when_tight_crop_reads_nothing():
    empty = {"label_text": "", "icon_description": "", "looks_like": ""}
    timer = {"label_text": "TIMER", "icon_description": "clock", "looks_like": "grey button"}
    c = FakeClient(read_queue=[empty, timer])
    import io
    from PIL import Image
    pattern = Image.new("RGB", (600, 800))
    pattern.putdata([((i % 600) % 256, ((i // 600) * 3) % 256, (i // 7) % 256) for i in range(600 * 800)])
    buf = io.BytesIO(); pattern.save(buf, format="PNG")
    r = run_explain_pipeline("nope", buf.getvalue(), 0.3, 0.4, client=c)
    assert len(c.read_calls) == 2
    assert c.read_calls[0] != c.read_calls[1]          # a different (wider) crop was sent
    assert r.read_result.label_text == "TIMER"
    assert r.card.source_ref == "notes.md / Timer"


def test_tight_crop_excludes_more_of_the_neighbourhood_than_wide_crop():
    from PIL import Image
    from backend.app.explain import process_crop_and_marker
    img = Image.new("RGB", (700, 700), "white")
    for xx in range(335, 365):
        for yy in range(335, 365):
            img.putpixel((xx, yy), (0, 0, 0))            # the "button" at the tap point
    def dark_fraction(frac):
        crop, *_ = process_crop_and_marker(img, 0.5, 0.5, crop_fraction=frac, min_side=64)
        px = list(crop.convert("L").tobytes())
        return sum(1 for v in px if v < 60) / len(px)
    assert dark_fraction(0.16) > dark_fraction(0.30)           # tight crop shows the button bigger
    crop, *_ = process_crop_and_marker(img, 0.5, 0.5, crop_fraction=0.16, min_side=64)
    assert crop.size == (512, 512)


def test_ocr_label_skips_the_slow_vision_read(monkeypatch):
    monkeypatch.setattr(explain_mod, "read_label_lines_at", lambda img, x, y: ["TIMER"])
    c = FakeClient(label="SOMETHING ELSE")
    r = run(c)
    assert c.read_calls == []                              # Gemma vision was never called
    assert r.read_result.label_text == "TIMER"
    assert r.card.source_ref == "notes.md / Timer"


def test_no_ocr_text_falls_back_to_gemma_vision():
    c = FakeClient(label="TIMER", icon="clock")
    r = run(c)
    assert len(c.read_calls) == 1
    assert r.read_result.label_text == "TIMER"


def test_quick_mode_has_no_notes_and_never_retrieves(monkeypatch):
    def boom(**kw):
        raise AssertionError("retrieval must not run in quick mode")
    monkeypatch.setattr(explain_mod, "retrieve_top_k", boom)
    c = FakeClient(label="TIMER")
    r = run_explain_pipeline(None, None, 0.3, 0.4, client=c, appliance_type_hint="Microwave")
    assert r.mode == "no_kb"
    assert r.card.source == "general_knowledge" and r.card.source_ref is None
    assert "Microwave" in c.explain_calls[0]["prompt"]


def test_symbol_button_without_a_matching_note_cites_nothing():
    r = run(FakeClient(label="+", icon="plus sign"), use_kb=True)      # CHUNKS has no Temperature heading
    assert r.card.source == "general_knowledge" and r.card.source_ref is None


def test_plus_button_cites_the_temperature_note_when_one_exists(monkeypatch):
    temp = {"chunk_id": "a::notes.md::Temperature Adjustment::4", "filename": "notes.md",
            "heading": "Temperature Adjustment", "content": "Plus raises the set temperature.", "score": 0.40}
    monkeypatch.setattr(explain_mod, "retrieve_top_k", lambda **kw: ([dict(c) for c in CHUNKS] + [temp], 0.7, "kb"))
    r = run(FakeClient(label="+", icon="plus sign"), use_kb=True)
    assert r.card.source == "knowledge_base"
    assert r.card.source_ref == "notes.md / Temperature Adjustment"


def test_multi_line_ocr_label_is_joined_and_the_model_is_warned_about_a_missed_plus(monkeypatch):
    monkeypatch.setattr(explain_mod, "read_label_lines_at", lambda img, x, y: ["MICROWAVE", "GRILL"])
    c = FakeClient()
    r = run_explain_pipeline(None, None, 0.5, 0.5, client=c, appliance_type_hint="Microwave")
    assert c.read_calls == []
    assert r.read_result.label_text == "MICROWAVE GRILL"
    prompt = c.explain_calls[0]["prompt"]
    assert "ONE button with 2 lines" in prompt and "MICROWAVE / GRILL" in prompt and "'+'" in prompt


def test_single_line_label_gets_no_multi_line_warning(monkeypatch):
    monkeypatch.setattr(explain_mod, "read_label_lines_at", lambda img, x, y: ["TURBO"])
    c = FakeClient()
    run_explain_pipeline(None, None, 0.5, 0.5, client=c)
    assert "lines of text" not in c.explain_calls[0]["prompt"]


def test_filler_try_this_is_replaced_with_honest_advice(monkeypatch):
    from backend.app.textutils import GENERIC_TRY_THIS
    monkeypatch.setattr(explain_mod, "read_label_lines_at", lambda img, x, y: ["MICROWAVE", "+", "CONVECTION"])
    card = dict(EN_CARD, try_this="I'm not sure, but you can press it to start.", passages_cover_button=False)
    r = run_explain_pipeline(None, None, 0.5, 0.5, client=FakeClient(explain_queue=[card]))
    assert r.card.try_this == GENERIC_TRY_THIS["en"]


def test_hindi_filler_is_replaced_with_hindi_advice(monkeypatch):
    from backend.app.textutils import GENERIC_TRY_THIS
    monkeypatch.setattr(explain_mod, "read_label_lines_at", lambda img, x, y: ["REHEAT"])
    card = dict(HI_CARD, try_this="\u092f\u0939 \u092c\u091f\u0928 \u0926\u092c\u093e\u0915\u0930 \u0926\u0947\u0916\u0947\u0902 \u0914\u0930 \u0926\u0947\u0916\u0947\u0902 \u0915\u094d\u092f\u093e \u0939\u094b\u0924\u093e \u0939\u0948\u0964", passages_cover_button=False)
    r = run_explain_pipeline(None, None, 0.5, 0.5, language="hi", client=FakeClient(explain_queue=[card]))
    assert r.card.try_this == GENERIC_TRY_THIS["hi"]
    assert has_devanagari(r.card.try_this)


def test_a_real_instruction_is_not_replaced(monkeypatch):
    monkeypatch.setattr(explain_mod, "read_label_lines_at", lambda img, x, y: ["FAN SPEED"])
    r = run_explain_pipeline(None, None, 0.5, 0.5, client=FakeClient())
    assert r.card.try_this == "Press it to change the speed."
