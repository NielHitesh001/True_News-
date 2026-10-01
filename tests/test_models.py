"""Unit tests for Model serving interface and disk caching (M4)."""

from __future__ import annotations

import pytest
from newsx.models import BaseModelClient, DeterministicExtractorClient


class MockEchoModel(BaseModelClient):
    def __init__(self, cache_dir):
        super().__init__(model_id="mock-echo-model", cache_dir=cache_dir)
        self.call_count = 0

    def _call_backend(self, prompt: str, system_prompt: str = "") -> str:
        self.call_count += 1
        return f"Echo: {prompt}"


def test_model_client_caching(tmp_path):
    cache_dir = tmp_path / "cache"
    client = MockEchoModel(cache_dir=cache_dir)

    # First call - cache miss
    resp1 = client.complete("Hello world")
    assert resp1 == "Echo: Hello world"
    assert client.call_count == 1

    # Second call - cache hit
    resp2 = client.complete("Hello world")
    assert resp2 == "Echo: Hello world"
    assert client.call_count == 1  # Backend was not called again

    # Different prompt - cache miss
    resp3 = client.complete("Different prompt")
    assert resp3 == "Echo: Different prompt"
    assert client.call_count == 2


def test_deterministic_extractor_client(tmp_path):
    cache_dir = tmp_path / "cache"
    client = DeterministicExtractorClient(cache_dir=cache_dir)
    assert client.model_id == "deterministic-extractor-v1"
    assert len(client.settings_hash) > 0

    res = client.complete("Sample input text")
    assert res == "Sample input text"
