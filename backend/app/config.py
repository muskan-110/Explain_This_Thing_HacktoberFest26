import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))

APPLIANCES_DIR = DATA_DIR / "appliances"
INDEX_DIR = DATA_DIR / "index"
LOGS_DIR = DATA_DIR / "logs"

# Ensure directories exist
INDEX_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
APPLIANCES_DIR.mkdir(parents=True, exist_ok=True)

# Ollama settings
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "gemma3:4b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# Retrieval settings
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.55"))

# Tracing
SENTRY_DSN = os.getenv("SENTRY_DSN", None)
