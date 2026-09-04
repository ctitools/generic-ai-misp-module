"""The single place that talks to the LLM (OpenAI-compatible chat completions).

Endpoint, key and model come from the environment / the repo's .env only, never from a request.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT = 120
DEFAULT_PARAMS = {"temperature": 0, "seed": 42, "top_p": 1, "max_tokens": 600, "think": False}


class LLMError(RuntimeError):
    pass


def env() -> dict[str, str]:
    """Shell semantics: a later line in .env overrides an earlier one; os.environ wins over both."""
    values: dict[str, str] = {}
    dotenv = REPO_ROOT / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    values.update(os.environ)
    return values


@dataclass(frozen=True)
class LLMSettings:
    base_url: str
    api_key: str
    model: str
    timeout: int = DEFAULT_TIMEOUT

    def __repr__(self) -> str:  # never leak the key into logs or test output
        key = "***" if self.api_key else ""
        return f"LLMSettings(base_url={self.base_url!r}, model={self.model!r}, api_key={key!r})"

    @classmethod
    def from_env(cls, model: str | None = None, timeout: int | None = None) -> "LLMSettings":
        values = env()
        return cls(
            base_url=values.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            api_key=values.get("OPENAI_API_KEY", ""),
            model=model or values.get("OPENAI_MODEL", ""),
            timeout=int(timeout or values.get("GENERIC_AI_REQUEST_TIMEOUT") or DEFAULT_TIMEOUT),
        )


def _request(url: str, settings: LLMSettings, payload: dict | None = None) -> Any:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise LLMError(f"Only http(s) LLM endpoints are allowed, got {url!r}")
    headers = {"Content-Type": "application/json"}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.timeout) as response:  # nosemgrep
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")[:300]
        raise LLMError(f"LLM endpoint returned HTTP {error.code}: {body}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise LLMError(
            f"LLM endpoint unreachable or timed out ({settings.timeout}s): {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise LLMError("LLM endpoint returned invalid JSON") from error


def llm_chat(
    messages: list[dict[str, str]],
    params: dict[str, Any],
    settings: LLMSettings,
    json_mode: bool = False,
) -> str:
    """One chat completion. Raises LLMError on any failure, truncation or empty answer."""
    params = {**DEFAULT_PARAMS, **params}
    payload: dict[str, Any] = {
        "model": settings.model,
        "messages": messages,
        "stream": False,
        "temperature": params["temperature"],
        "seed": params["seed"],
        "top_p": params["top_p"],
        "max_tokens": params["max_tokens"],
    }
    if not params["think"]:
        # Ollama ignores "think": false on the OpenAI-compatible route but honours this
        # (measured 2026-09-04 on qwen3.8); without it reasoning tokens eat max_tokens.
        payload["reasoning_effort"] = "none"
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _request(f"{settings.base_url}/chat/completions", settings, payload)
    try:
        choice = data["choices"][0]
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise LLMError("LLM answer had no message content") from error
    if choice.get("finish_reason") == "length":
        raise LLMError("LLM answer was truncated (max_tokens too small)")
    if not isinstance(content, str) or not content.strip():
        raise LLMError("LLM answer was empty")
    return content.strip()


def is_reachable(settings: LLMSettings) -> bool:
    try:
        _request(
            f"{settings.base_url}/models",
            LLMSettings(settings.base_url, settings.api_key, settings.model, 10),
        )
        return True
    except LLMError:
        return False


def model_info(settings: LLMSettings) -> dict[str, Any]:
    """Model name plus, for Ollama, digest / quantisation / server version (best effort)."""
    info: dict[str, Any] = {"name": settings.model}
    host = settings.base_url.removesuffix("/v1")
    short = LLMSettings(host, settings.api_key, settings.model, 10)
    try:
        info["server"] = "ollama " + _request(f"{host}/api/version", short)["version"]
        for model in _request(f"{host}/api/tags", short)["models"]:
            if model["name"] == settings.model:
                info["digest"] = model["digest"][:12]
                info["quantization"] = model.get("details", {}).get("quantization_level")
    except LLMError, KeyError, TypeError:
        pass  # not Ollama, or not reachable: name only
    return info
