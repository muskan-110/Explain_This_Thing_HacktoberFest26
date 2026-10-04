import numpy as np
from typing import List, Dict, Any, Tuple
from backend.app.config import SIMILARITY_THRESHOLD
from backend.app.ingest import load_appliance_index
from backend.app.ollama_client import OllamaClient

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two numeric vectors."""
    a = np.array(v1, dtype=float)
    b = np.array(v2, dtype=float)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

def retrieve_top_k(
    appliance_id: str,
    query: str,
    top_k: int = 3,
    threshold: float = SIMILARITY_THRESHOLD,
    client: OllamaClient = None
) -> Tuple[List[Dict[str, Any]], float, str]:
    """
    Retrieves top_k chunks for a given appliance_id and query string.
    Returns: (matched_chunks, best_score, mode) where mode is 'kb' or 'no_kb'.
    """
    chunks = load_appliance_index(appliance_id)
    if not chunks:
        return [], 0.0, "no_kb"

    if client is None:
        client = OllamaClient()

    query_embedding = client.get_embedding(query)
    
    scored_chunks = []
    for chunk in chunks:
        emb = chunk.get("embedding", [])
        if not emb:
            continue
        score = cosine_similarity(query_embedding, emb)
        scored_chunks.append({
            "chunk_id": chunk["chunk_id"],
            "filename": chunk["filename"],
            "heading": chunk["heading"],
            "content": chunk["content"],
            "score": score
        })

    if not scored_chunks:
        return [], 0.0, "no_kb"

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    best_score = scored_chunks[0]["score"]

    if best_score < threshold:
        return scored_chunks[:top_k], best_score, "no_kb"

    return scored_chunks[:top_k], best_score, "kb"
