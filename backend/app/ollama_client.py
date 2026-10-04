import httpx
from typing import List, Dict, Any, Optional
from backend.app.config import OLLAMA_HOST, OLLAMA_VISION_MODEL, OLLAMA_EMBED_MODEL

class OllamaClientError(Exception):
    pass

class OllamaClient:
    def __init__(self, host: str = OLLAMA_HOST):
        self.host = host.rstrip("/")

    def check_health(self) -> Dict[str, Any]:
        """Checks if Ollama server is running and returns available models."""
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(f"{self.host}/api/tags")
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", [])]
                    has_vision = any(OLLAMA_VISION_MODEL in m for m in models)
                    has_embed = any(OLLAMA_EMBED_MODEL in m for m in models)
                    return {
                        "online": True,
                        "models": models,
                        "has_vision_model": has_vision,
                        "has_embed_model": has_embed,
                    }
        except Exception as e:
            return {
                "online": False,
                "error": str(e),
                "has_vision_model": False,
                "has_embed_model": False,
            }
        return {
            "online": False,
            "has_vision_model": False,
            "has_embed_model": False,
        }

    def get_embedding(self, text: str, model: str = OLLAMA_EMBED_MODEL, keep_alive: str = "30m") -> List[float]:
        """Generates text embedding using specified Ollama embedding model."""
        with httpx.Client(timeout=30.0) as client:
            # Try /api/embed first (newer Ollama API)
            try:
                res = client.post(
                    f"{self.host}/api/embed",
                    json={"model": model, "input": text, "keep_alive": keep_alive}
                )
                if res.status_code == 200:
                    data = res.json()
                    embeddings = data.get("embeddings", [])
                    if embeddings:
                        return embeddings[0]
            except Exception:
                pass

            # Fallback to /api/embeddings (classic Ollama API)
            res = client.post(
                f"{self.host}/api/embeddings",
                json={"model": model, "prompt": text, "keep_alive": keep_alive}
            )
            if res.status_code == 200:
                data = res.json()
                if "embedding" in data:
                    return data["embedding"]

            raise OllamaClientError(
                f"Failed to generate embedding with model '{model}'. "
                f"Ensure Ollama is running and run `ollama pull {model}` if needed. "
                f"Response: {res.status_code} {res.text}"
            )

    def generate_chat(
        self,
        prompt: str,
        images_b64: Optional[List[str]] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        model: str = OLLAMA_VISION_MODEL,
        temperature: float = 0.0,
        num_predict: int = 150,
        keep_alive: str = "30m"
    ) -> str:
        """Sends a completion request to Ollama chat endpoint."""
        message: Dict[str, Any] = {
            "role": "user",
            "content": prompt
        }
        if images_b64:
            message["images"] = images_b64

        options: Dict[str, Any] = {
            "temperature": temperature,
            "num_predict": num_predict
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [message],
            "stream": False,
            "keep_alive": keep_alive,
            "options": options
        }
        if json_schema:
            payload["format"] = json_schema

        with httpx.Client(timeout=120.0) as client:
            res = client.post(f"{self.host}/api/chat", json=payload)
            if res.status_code == 200:
                data = res.json()
                return data.get("message", {}).get("content", "")

            raise OllamaClientError(
                f"Ollama chat generation failed for model '{model}'. "
                f"Run `ollama pull {model}` if missing. Error: {res.status_code} {res.text}"
            )

