"""Model providers.

Ollama is the default so the whole tool runs on a workstation with no data
leaving it — a real constraint for BEPs, which routinely carry information the
appointing party has classified as sensitive under ISO 19650-5. Any
OpenAI-compatible endpoint works too; both are configured in the JSON settings.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from ..settings import get as setting

THINK_TAG = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


class AIError(RuntimeError):
    """Raised when a model cannot be reached or refuses to answer usefully."""


@dataclass
class Completion:
    text: str
    model: str
    provider: str
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "model": self.model,
                "provider": self.provider, "elapsed_ms": self.elapsed_ms}


def _post(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise AIError(f"model endpoint returned {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AIError(f"cannot reach the model endpoint at {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AIError("the model took too long to answer; raise ai.timeout_seconds") from exc


def _get(url: str, timeout: float) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AIError(f"cannot reach {url}: {exc}") from exc


def clean(text: str) -> str:
    """Strip reasoning tags and the wrappers small models like to add."""
    if setting("ai.strip_think_tags", True):
        text = THINK_TAG.sub("", text)
    text = text.strip()
    # Models often fence their answer even when told not to.
    fence = re.match(r"^```[a-zA-Z]*\n(.*)\n```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return text


class OllamaProvider:
    """Local Ollama daemon (https://ollama.com)."""

    name = "ollama"

    def __init__(self) -> None:
        self.base_url = str(setting("ai.base_url", "http://localhost:11434")).rstrip("/")
        self.timeout = float(setting("ai.timeout_seconds", 180))

    def available_models(self) -> list[str]:
        data = _get(f"{self.base_url}/api/tags", timeout=min(10.0, self.timeout))
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    def resolve_model(self, requested: str | None = None) -> str:
        """Pick the configured model, or the first installed fallback."""
        installed = self.available_models()
        if not installed:
            raise AIError("Ollama is running but has no models installed. Try: ollama pull qwen3:30b-instruct")
        wanted = requested or str(setting("ai.model", ""))
        candidates = [wanted, *setting("ai.fallback_models", [])]
        bare = {name.split(":")[0]: name for name in installed}
        for candidate in candidates:
            if not candidate:
                continue
            if candidate in installed:
                return candidate
            if candidate.split(":")[0] in bare:
                return bare[candidate.split(":")[0]]
        return installed[0]

    def complete(self, system: str, prompt: str, *, model: str | None = None,
                 temperature: float | None = None) -> Completion:
        import time

        chosen = self.resolve_model(model)
        payload = {
            "model": chosen,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": float(setting("ai.temperature", 0.35) if temperature is None else temperature),
                "top_p": float(setting("ai.top_p", 0.9)),
                "num_ctx": int(setting("ai.num_ctx", 16384)),
                "num_predict": int(setting("ai.num_predict", 1400)),
            },
        }
        started = time.monotonic()
        data = _post(f"{self.base_url}/api/generate", payload, self.timeout)
        text = clean(data.get("response", ""))
        if not text:
            raise AIError(f"{chosen} returned an empty answer")
        return Completion(text=text, model=chosen, provider=self.name,
                          elapsed_ms=int((time.monotonic() - started) * 1000))


class OpenAICompatibleProvider:
    """Any endpoint that speaks the OpenAI chat-completions shape."""

    name = "openai_compatible"

    def __init__(self) -> None:
        self.base_url = str(setting("ai.base_url", "")).rstrip("/")
        self.timeout = float(setting("ai.timeout_seconds", 180))
        self.api_key = str(setting("ai.api_key", "") or "")

    def available_models(self) -> list[str]:
        model = str(setting("ai.model", ""))
        return [model] if model else []

    def resolve_model(self, requested: str | None = None) -> str:
        return requested or str(setting("ai.model", ""))

    def complete(self, system: str, prompt: str, *, model: str | None = None,
                 temperature: float | None = None) -> Completion:
        import time

        chosen = self.resolve_model(model)
        payload = {
            "model": chosen,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": float(setting("ai.temperature", 0.35) if temperature is None else temperature),
            "stream": False,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})},
            method="POST",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AIError(f"cannot reach the model endpoint: {exc}") from exc
        text = clean(data["choices"][0]["message"]["content"])
        return Completion(text=text, model=chosen, provider=self.name,
                          elapsed_ms=int((time.monotonic() - started) * 1000))


PROVIDERS = {"ollama": OllamaProvider, "openai_compatible": OpenAICompatibleProvider}


def get_provider(name: str | None = None):
    key = (name or setting("ai.provider", "ollama")).lower()
    if key not in PROVIDERS:
        raise AIError(f"unknown AI provider '{key}' (configured: {', '.join(PROVIDERS)})")
    return PROVIDERS[key]()


def status() -> dict[str, Any]:
    """What the UI shows in the assist panel when nothing has been asked yet."""
    if not setting("ai.enabled", True):
        return {"enabled": False, "reachable": False, "reason": "disabled in settings"}
    try:
        provider = get_provider()
        models = provider.available_models()
        return {
            "enabled": True,
            "reachable": True,
            "provider": provider.name,
            "base_url": getattr(provider, "base_url", ""),
            "model": provider.resolve_model(),
            "models": models,
        }
    except AIError as exc:
        return {"enabled": True, "reachable": False, "reason": str(exc),
                "provider": setting("ai.provider", "ollama"),
                "base_url": setting("ai.base_url", "")}
