import json
from datetime import datetime, timezone
from typing import Dict, Any
from backend.app.config import LOGS_DIR

REQUESTS_LOG_PATH = LOGS_DIR / "requests.jsonl"
FEEDBACK_LOG_PATH = LOGS_DIR / "feedback.jsonl"

def log_request(
    request_id: str,
    appliance_id: str,
    timings: Dict[str, float],
    mode: str,
    retrieved_chunk_ids: list[str],
    output: Dict[str, Any],
    model_name: str
):
    """Logs detailed explain request metadata to data/logs/requests.jsonl."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "appliance_id": appliance_id,
        "mode": mode,
        "model_name": model_name,
        "timings": timings,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "output": output
    }
    try:
        with open(REQUESTS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

def save_feedback(request_id: str, helpful: bool, comment: str = None) -> bool:
    """Saves user feedback to data/logs/feedback.jsonl."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "helpful": helpful,
        "comment": comment or ""
    }
    try:
        with open(FEEDBACK_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return True
    except Exception:
        return False
