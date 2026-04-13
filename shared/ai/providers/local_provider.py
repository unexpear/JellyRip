"""Local model provider adapter (Ollama)."""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

from shared.ai.providers.base import BaseProvider, ConnectionResult, ProviderInfo


class LocalProvider(BaseProvider):
    """Local model backend via Ollama HTTP API."""

    _DEFAULT_MODEL = "qwen2.5:14b-instruct"
    _MODELS = [
        "qwen2.5:14b-instruct",
        "qwen2.5:7b-instruct",
        "llama3.1:8b-instruct-q4_0",
        "mistral:7b-instruct",
        "gemma2:9b-it",
    ]

    def __init__(self) -> None:
        self._model = self._DEFAULT_MODEL
        self._base_url = "http://localhost:11434"

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="local",
            display_name="Local (Ollama)",
            category="local",
            requires_api_key=False,
            default_model=self._DEFAULT_MODEL,
            available_models=list(self._MODELS),
            help_url="https://ollama.com/download",
        )

    def configure(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        if model:
            self._model = model
        if "base_url" in kwargs:
            self._base_url = str(kwargs["base_url"]).rstrip("/")

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/tags", method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
            model_base = self._model.split(":")[0]
            for m in data.get("models", []):
                if model_base in m.get("name", ""):
                    return True
            return False
        except Exception:
            return False

    def _get_available_models(self) -> list[str]:
        """Query Ollama for actually-pulled models."""
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/tags", method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", []) if "name" in m]
        except Exception:
            return []

    def _call(self, system: str, user: str, max_tokens: int, timeout: float) -> str:
        body = json.dumps({
            "model": self._model,
            "system": system,
            "prompt": user,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
        return result.get("response", "(no response)")

    def test_connection(self, timeout: float = 10.0) -> ConnectionResult:
        try:
            # First check if Ollama is reachable
            req = urllib.request.Request(
                f"{self._base_url}/api/tags", method="GET",
            )
            start = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            ms = (time.time() - start) * 1000

            model_base = self._model.split(":")[0]
            found = False
            for m in data.get("models", []):
                if model_base in m.get("name", ""):
                    found = True
                    break

            if not found:
                pulled = [m.get("name", "?") for m in data.get("models", [])]
                return ConnectionResult(
                    success=False,
                    latency_ms=ms,
                    error=f"Model '{self._model}' not pulled. Available: {', '.join(pulled[:5]) or 'none'}",
                )
            return ConnectionResult(
                success=True,
                latency_ms=ms,
                model_confirmed=self._model,
            )
        except Exception as e:
            return ConnectionResult(success=False, error=str(e))

    def diagnose(self, payload_json: str, system_prompt: str,
                 max_tokens: int = 800, timeout: float = 20.0) -> str:
        return self._call(system_prompt, payload_json, max_tokens, timeout)

    def summarize(self, payload_json: str, system_prompt: str,
                  max_tokens: int = 1200, timeout: float = 20.0) -> str:
        return self._call(system_prompt, payload_json, max_tokens, timeout)
