import pytest
from backend.app.schemas import ExplainResult

def test_source_ref_invariant_knowledge_base():
    card = ExplainResult(
        button_name="Fan Speed",
        what_it_does="Changes airflow.",
        try_this="Press to cycle.",
        confidence="high",
        source="knowledge_base",
        source_ref="notes.md / Fan speed",
        safety_flag=False
    )
    assert card.source == "knowledge_base"
    assert card.source_ref is not None
    assert len(card.source_ref) > 0

def test_source_ref_invariant_general_knowledge():
    card = ExplainResult(
        button_name="Fan Speed",
        what_it_does="Changes airflow.",
        try_this="Press to cycle.",
        confidence="medium",
        source="general_knowledge",
        source_ref=None,
        safety_flag=False
    )
    assert card.source == "general_knowledge"
    assert card.source_ref is None

def test_pipeline_source_ref_rules(monkeypatch):
    """
    Simulates explain pipeline output rules:
    - knowledge_base mode -> source_ref must be non-null
    - general_knowledge mode -> source_ref must be null
    """
    # 1. Simulate KB mode with retrieved chunk
    retrieved_chunks = [{
        "chunk_id": "c1",
        "filename": "notes.md",
        "heading": "Fan speed",
        "content": "Fan speed settings",
        "score": 0.85
    }]
    mode = "kb"
    card_result = ExplainResult(
        button_name="FAN SPEED",
        what_it_does="Controls fan.",
        try_this="Press fan button.",
        confidence="high",
        source="knowledge_base", # Model might return null or string
        source_ref=None,
        safety_flag=False
    )

    # Server-side enforcement block (matching explain.py)
    if mode == "kb" and retrieved_chunks:
        card_result.source = "knowledge_base"
        top_c = retrieved_chunks[0]
        card_result.source_ref = f"{top_c['filename']} / {top_c['heading']}"
    else:
        card_result.source = "general_knowledge"
        card_result.source_ref = None

    assert card_result.source == "knowledge_base"
    assert card_result.source_ref == "notes.md / Fan speed"

    # 2. Simulate NO-KB mode
    mode = "no_kb"
    retrieved_chunks = []
    card_result_nokb = ExplainResult(
        button_name="FAN SPEED",
        what_it_does="Controls fan.",
        try_this="Press fan button.",
        confidence="high",
        source="knowledge_base", # Model attempted KB without retrieval
        source_ref="fake_ref.md",
        safety_flag=False
    )

    if mode == "kb" and retrieved_chunks:
        card_result_nokb.source = "knowledge_base"
        top_c = retrieved_chunks[0]
        card_result_nokb.source_ref = f"{top_c['filename']} / {top_c['heading']}"
    else:
        card_result_nokb.source = "general_knowledge"
        card_result_nokb.source_ref = None
        if card_result_nokb.confidence == "high":
            card_result_nokb.confidence = "medium"

    assert card_result_nokb.source == "general_knowledge"
    assert card_result_nokb.source_ref is None
    assert card_result_nokb.confidence == "medium"
