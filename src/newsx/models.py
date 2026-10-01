"""Model Serving Interface and Disk Caching (M4).

Provides a swappable interface for learned and deterministic language models.
Guarantees reproducible execution via fixed settings and SHA-256 disk caching (spec §4).
"""

from __future__ import annotations

import abc
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any, Optional

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"


class BaseModelClient(abc.ABC):
    """Abstract base class for all swappable model backends."""

    def __init__(self, model_id: str, cache_dir: Optional[Path] = None) -> None:
        self.model_id = model_id
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @abc.abstractmethod
    def _call_backend(self, prompt: str, system_prompt: str = "") -> str:
        """Raw backend execution to be implemented by subclasses."""
        pass

    @property
    def settings_hash(self) -> str:
        settings_str = f"model={self.model_id}:temperature=0.0:seed=42"
        return hashlib.sha256(settings_str.encode("utf-8")).hexdigest()[:12]

    def _get_cache_key(self, prompt: str, system_prompt: str = "") -> str:
        key_raw = f"{self.model_id}:{self.settings_hash}:{system_prompt}:{prompt}"
        return hashlib.sha256(key_raw.encode("utf-8")).hexdigest()

    def complete(self, prompt: str, system_prompt: str = "") -> str:
        """Completes the prompt, checking disk cache first."""
        cache_key = self._get_cache_key(prompt, system_prompt)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with cache_file.open("r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    return cached_data.get("response", "")
            except Exception:
                pass

        # Call underlying model backend
        response = self._call_backend(prompt, system_prompt)

        # Write to disk cache
        try:
            with cache_file.open("w", encoding="utf-8") as f:
                json.dump(
                    {
                        "model_id": self.model_id,
                        "settings_hash": self.settings_hash,
                        "prompt": prompt,
                        "system_prompt": system_prompt,
                        "response": response,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass

        return response


class DeterministicExtractorClient(BaseModelClient):
    """Deterministic, zero-dependency model client for claim splitting and neutralization."""

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        super().__init__(model_id="deterministic-extractor-v1", cache_dir=cache_dir)

    def _call_backend(self, prompt: str, system_prompt: str = "") -> str:
        # Returns raw prompt for deterministic downstream parsing
        return prompt


class OllamaModelClient(BaseModelClient):
    """Client for locally served open-weight models via Ollama."""

    def __init__(
        self,
        model_id: str = "gemma:7b",
        host: str = "http://localhost:11434",
        cache_dir: Optional[Path] = None,
    ) -> None:
        super().__init__(model_id=model_id, cache_dir=cache_dir)
        self.host = host.rstrip("/")

    def _call_backend(self, prompt: str, system_prompt: str = "") -> str:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model_id,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "seed": 42,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "").strip()
        except Exception as e:
            # On local backend failure or offline mode, fallback gracefully
            return f"[OLLAMA_OFFLINE: {type(e).__name__}]"
