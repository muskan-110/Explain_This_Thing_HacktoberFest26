import pytest
from backend.app.ingest import ingest_appliance_knowledge
from backend.app.retrieval import retrieve_top_k
from backend.app.ollama_client import OllamaClient

def test_ingest_and_retrieval_example_ac():
    client = OllamaClient()
    health = client.check_health()
    if not health.get("online") or not health.get("has_embed_model"):
        pytest.skip("Ollama embedding model not available for retrieval test")

    # Ingest example AC notes
    count = ingest_appliance_knowledge("_example_ac", client=client)
    assert count > 0, "Ingested chunks count should be > 0 for _example_ac"

    # Test retrieval for 'fan speed'
    chunks, best_score, mode = retrieve_top_k(
        appliance_id="_example_ac",
        query="fan speed",
        top_k=3,
        threshold=0.4, # standard test threshold
        client=client
    )
    assert len(chunks) > 0
    headings = [c["heading"].lower() for c in chunks]
    contents = [c["content"].lower() for c in chunks]
    assert any("fan speed" in h or "fan speed" in c for h, c in zip(headings, contents))

    # Test retrieval for 'timer'
    chunks, best_score, mode = retrieve_top_k(
        appliance_id="_example_ac",
        query="timer",
        top_k=3,
        threshold=0.4,
        client=client
    )
    assert len(chunks) > 0
    headings = [c["heading"].lower() for c in chunks]
    contents = [c["content"].lower() for c in chunks]
    assert any("timer" in h or "timer" in c for h, c in zip(headings, contents))
