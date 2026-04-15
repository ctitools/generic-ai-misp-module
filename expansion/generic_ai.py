import hashlib
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

misperrors = {"error": "Error"}
mispattributes = {
    "input": ["text", "comment"],
    "output": ["EventReport"],
    "format": "misp_standard",
}
moduleinfo = {
    "version": "0.2",
    "author": "OpenCode",
    "description": (
        "Generic AI MISP expansion scaffold with live backend support and a deterministic fallback."
    ),
    "module-type": ["expansion"],
    "name": "Generic AI",
    "logo": "",
    "requirements": [],
    "features": (
        "This module accepts text-like MISP attributes or direct text input, "
        "summarises them through a live backend when configured, and returns "
        "a MISP EventReport. If the backend is unavailable it falls back to a "
        "deterministic summary so the pipeline still produces a visible result."
    ),
    "references": [],
    "input": "Raw text or a MISP attribute of type text/comment.",
    "output": (
        "A markdown EventReport containing the generated summary plus event-level "
        "ai-computer-assisted tags for MISP ingestion."
    ),
}
moduleconfig = [
    "backend",
    "api_base",
    "ollama_host",
    "request_timeout",
    "verify_ssl",
    "default_model_id",
    "default_use_case_category",
    "system_prompt",
    "user_prompt",
    "summary_sentences",
    "summary_chars",
    "event_report_name",
    "event_report_distribution",
]

AI_COMPUTER_ASSISTED_TAG_NAMES = (
    'ai-computer-assisted:assistance-level="ai-generated"',
    'ai-computer-assisted:review-level="unreviewed"',
)

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "gemma4:latest"
DEFAULT_SYSTEM_PROMPT = (
    "You summarise cyber threat intelligence text for MISP users. Return only "
    "the summary in markdown with concise factual wording."
)
DEFAULT_USER_PROMPT = (
    "Summarise the following CTI content for a MISP event report. Cover the "
    "threat, delivery method, infrastructure, impact, and response actions if present."
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE_RE = re.compile(r"\s+")
_MARKDOWN_HEADING_RE = re.compile(r"(?m)^\s{0,3}#+\s*")


class BackendError(RuntimeError):
    pass


def _normalise_text(text: str) -> str:
    without_headings = _MARKDOWN_HEADING_RE.sub("", text)
    return _WHITESPACE_RE.sub(" ", without_headings).strip()


def _coerce_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, coerced))


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default


def _get_config(request: dict[str, Any]) -> dict[str, Any]:
    config = request.get("config")
    return config if isinstance(config, dict) else {}


def _get_setting(
    request: dict[str, Any],
    key: str,
    *env_keys: str,
    default: Any = None,
) -> Any:
    if key in request and request[key] not in (None, ""):
        return request[key]

    config = _get_config(request)
    if key in config and config[key] not in (None, ""):
        return config[key]

    for env_key in env_keys:
        value = os.getenv(env_key)
        if value not in (None, ""):
            return value

    return default


def _extract_input_text(request: dict[str, Any]) -> str:
    if request.get("text"):
        return str(request["text"])

    attribute = request.get("attribute")
    if attribute:
        attribute_type = attribute.get("type")
        if attribute_type not in mispattributes["input"]:
            raise ValueError("Unsupported attribute type.")
        if not attribute.get("uuid"):
            raise ValueError('This module requires an "attribute" with a uuid.')
        value = attribute.get("value")
        if not value:
            raise ValueError('This module requires an "attribute" with a non-empty value.')
        return str(value)

    raise ValueError('This module requires either a "text" field or a supported "attribute" field.')


def _summarise_deterministically(text: str, sentence_limit: int, char_limit: int) -> str:
    normalised = _normalise_text(text)
    if not normalised:
        raise ValueError("The provided text is empty after normalisation.")

    sentences = [
        sentence.strip() for sentence in _SENTENCE_SPLIT_RE.split(normalised) if sentence.strip()
    ]
    if len(sentences) == 1:
        if len(normalised) <= char_limit:
            return normalised
        return f"{normalised[: char_limit - 3].rstrip()}..."

    selected: list[str] = []
    current_length = 0
    for sentence in sentences:
        projected_length = current_length + len(sentence) + (1 if selected else 0)
        if projected_length > char_limit and selected:
            break
        if projected_length > char_limit:
            return f"{sentence[: char_limit - 3].rstrip()}..."
        selected.append(sentence)
        current_length = projected_length
        if len(selected) >= sentence_limit:
            break
    return " ".join(selected)


def _request_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout: int,
    verify_ssl: bool,
) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise BackendError("Only http(s) backend URLs are allowed.")

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")

    context = None
    if url.startswith("https://") and not verify_ssl:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    try:
        # URL scheme and netloc are validated immediately above.
        # nosemgrep
        with urllib.request.urlopen(
            request,
            timeout=timeout,
            context=context,
        ) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise BackendError(f"HTTP {error.code} from backend: {body[:300]}") from error
    except urllib.error.URLError as error:
        raise BackendError(f"Failed to reach backend: {error.reason}") from error
    except TimeoutError as error:
        raise BackendError("Backend request timed out.") from error
    except json.JSONDecodeError as error:
        raise BackendError("Backend returned invalid JSON.") from error


def _build_messages(
    request: dict[str, Any],
    source_text: str,
    *,
    use_case: str,
    char_limit: int,
) -> list[dict[str, str]]:
    system_prompt = _get_setting(request, "system_prompt", default=DEFAULT_SYSTEM_PROMPT)
    user_prompt = _get_setting(request, "user_prompt", default=DEFAULT_USER_PROMPT)
    use_case_prompt = _get_setting(request, "use_case_prompt", default="")
    prompt_parts = [
        user_prompt,
        f"Use-case category: {use_case}.",
        f"Keep the answer under roughly {char_limit} characters when possible.",
    ]
    if use_case_prompt:
        prompt_parts.append(str(use_case_prompt))
    prompt_parts.extend(["Source text:", source_text])
    return [
        {"role": "system", "content": str(system_prompt)},
        {"role": "user", "content": "\n\n".join(prompt_parts)},
    ]


def _extract_openai_content(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise BackendError("OpenAI response did not contain message content.") from error

    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        combined = "\n".join(part for part in parts if part).strip()
        if combined:
            return combined
    raise BackendError("OpenAI response content was empty.")


def _extract_ollama_content(response: dict[str, Any]) -> str:
    try:
        content = response["message"]["content"]
    except (KeyError, TypeError) as error:
        raise BackendError("Ollama response did not contain message content.") from error
    if not isinstance(content, str) or not content.strip():
        raise BackendError("Ollama response content was empty.")
    return content.strip()


def _call_openai(
    request: dict[str, Any],
    *,
    source_text: str,
    use_case: str,
    model_id: str,
    timeout: int,
    verify_ssl: bool,
    char_limit: int,
) -> tuple[str, dict[str, Any]]:
    api_key = _get_setting(request, "api_key", "OPENAI_API_KEY")
    api_base = _get_setting(
        request,
        "api_base",
        "GENERIC_AI_API_BASE",
        "OPENAI_BASE_URL",
        default=DEFAULT_OPENAI_BASE_URL,
    ).rstrip("/")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model_id,
        "messages": _build_messages(
            request,
            source_text,
            use_case=use_case,
            char_limit=char_limit,
        ),
    }
    response = _request_json(
        f"{api_base}/chat/completions",
        payload,
        headers=headers,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )
    return _extract_openai_content(response), {
        "backend": "openai",
        "model_fingerprint": response.get("system_fingerprint"),
        "raw_model_id": response.get("model", model_id),
    }


def _call_ollama(
    request: dict[str, Any],
    *,
    source_text: str,
    use_case: str,
    model_id: str,
    timeout: int,
    verify_ssl: bool,
    char_limit: int,
) -> tuple[str, dict[str, Any]]:
    ollama_host = _get_setting(
        request,
        "ollama_host",
        "GENERIC_AI_OLLAMA_HOST",
        "OLLAMA_HOST",
        default=DEFAULT_OLLAMA_HOST,
    ).rstrip("/")
    payload = {
        "model": model_id,
        "stream": False,
        "messages": _build_messages(
            request,
            source_text,
            use_case=use_case,
            char_limit=char_limit,
        ),
    }
    model_parameters = request.get("model_parameters")
    if isinstance(model_parameters, dict) and model_parameters:
        payload["options"] = model_parameters

    response = _request_json(
        f"{ollama_host}/api/chat",
        payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
        verify_ssl=verify_ssl,
    )
    return _extract_ollama_content(response), {
        "backend": "ollama",
        "model_fingerprint": response.get("created_at"),
        "raw_model_id": response.get("model", model_id),
    }


def _call_backend(
    request: dict[str, Any],
    *,
    source_text: str,
    use_case: str,
    model_id: str,
    timeout: int,
    verify_ssl: bool,
    char_limit: int,
) -> tuple[str, dict[str, Any]]:
    backend = (
        str(_get_setting(request, "backend", "GENERIC_AI_BACKEND", default="")).strip().lower()
    )
    if not backend:
        raise BackendError("No live backend configured.")
    if backend == "openai":
        return _call_openai(
            request,
            source_text=source_text,
            use_case=use_case,
            model_id=model_id,
            timeout=timeout,
            verify_ssl=verify_ssl,
            char_limit=char_limit,
        )
    if backend == "ollama":
        return _call_ollama(
            request,
            source_text=source_text,
            use_case=use_case,
            model_id=model_id,
            timeout=timeout,
            verify_ssl=verify_ssl,
            char_limit=char_limit,
        )
    raise BackendError(f"Unsupported backend: {backend}")


def _build_event_report_content(summary: str, metadata: dict[str, Any]) -> str:
    lines = [
        "# Generic AI Summary",
        "",
        summary.strip(),
        "",
        "## Metadata",
        "",
        f"- Backend: `{metadata['backend']}`",
        f"- Model: `{metadata['model_id']}`",
        f"- Mode: `{metadata['mode']}`",
        f"- Use-case: `{metadata['use_case_category']}`",
        f"- Source hash: `{metadata['content_hash']}`",
    ]
    if metadata.get("backend_error"):
        lines.append(f"- Backend error: `{metadata['backend_error']}`")
    return "\n".join(lines)


def _build_event_report(
    request: dict[str, Any],
    *,
    content: str,
    use_case: str,
) -> dict[str, str]:
    name = _get_setting(
        request,
        "event_report_name",
        default=f"Generic AI Summary ({use_case})",
    )
    attribute = request.get("attribute") or {}
    distribution = _get_setting(
        request,
        "event_report_distribution",
        default=attribute.get("distribution", 0),
    )
    return {
        "uuid": str(uuid.uuid4()),
        "distribution": str(distribution),
        "name": str(name),
        "content": content,
    }


def _build_event_tags() -> list[dict[str, Any]]:
    return [{"name": tag_name, "local": False} for tag_name in AI_COMPUTER_ASSISTED_TAG_NAMES]


def _resolve_runtime_settings(request: dict[str, Any]) -> dict[str, Any]:
    backend = (
        str(_get_setting(request, "backend", "GENERIC_AI_BACKEND", default="")).strip().lower()
    )
    model_id_default = DEFAULT_OLLAMA_MODEL if backend == "ollama" else "deterministic-fallback"
    return {
        "sentence_limit": _coerce_int(
            _get_setting(request, "summary_sentences", default=3),
            default=3,
            minimum=1,
            maximum=10,
        ),
        "char_limit": _coerce_int(
            _get_setting(request, "summary_chars", default=500),
            default=500,
            minimum=80,
            maximum=4000,
        ),
        "timeout": _coerce_int(
            _get_setting(request, "request_timeout", "GENERIC_AI_REQUEST_TIMEOUT", default=60),
            default=60,
            minimum=1,
            maximum=600,
        ),
        "verify_ssl": _coerce_bool(
            _get_setting(request, "verify_ssl", "GENERIC_AI_VERIFY_SSL", default=False),
            default=False,
        ),
        "use_case": str(
            _get_setting(
                request,
                "use_case_category",
                default=_get_setting(request, "default_use_case_category", default="summarization"),
            )
        ),
        "backend": backend,
        "model_id": str(
            _get_setting(
                request,
                "model_id",
                "GENERIC_AI_MODEL",
                "OPENAI_MODEL",
                default=_get_setting(request, "default_model_id", default=model_id_default),
            )
        ),
    }


def _generate_summary(
    request: dict[str, Any],
    *,
    source_text: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    backend_error = None
    backend_details: dict[str, Any] = {"backend": settings["backend"] or "deterministic-fallback"}
    model_id = str(settings["model_id"])

    try:
        summary, backend_details = _call_backend(
            request,
            source_text=source_text,
            use_case=str(settings["use_case"]),
            model_id=model_id,
            timeout=int(settings["timeout"]),
            verify_ssl=bool(settings["verify_ssl"]),
            char_limit=int(settings["char_limit"]),
        )
        mode = "live-backend"
        if backend_details.get("raw_model_id"):
            model_id = str(backend_details["raw_model_id"])
    except BackendError as error:
        backend_error = str(error)
        try:
            summary = _summarise_deterministically(
                source_text,
                sentence_limit=int(settings["sentence_limit"]),
                char_limit=int(settings["char_limit"]),
            )
        except ValueError as deterministic_error:
            return {"error": str(deterministic_error)}
        mode = "fallback-after-backend-error" if settings["backend"] else "deterministic-fallback"

    return {
        "summary": summary,
        "mode": mode,
        "backend_error": backend_error,
        "backend_details": backend_details,
        "model_id": model_id,
    }


def dict_handler(request: dict[str, Any]) -> dict[str, Any]:
    try:
        source_text = _extract_input_text(request)
    except ValueError as error:
        return {"error": str(error)}

    settings = _resolve_runtime_settings(request)
    generated = _generate_summary(request, source_text=source_text, settings=settings)
    if "error" in generated:
        return generated

    normalised = _normalise_text(source_text)
    metadata = {
        "status_code": 200,
        "backend": generated["backend_details"].get(
            "backend", settings["backend"] or "deterministic-fallback"
        ),
        "backend_error": generated["backend_error"],
        "model_id": generated["model_id"],
        "model_fingerprint": generated["backend_details"].get("model_fingerprint"),
        "model_parameters": request.get("model_parameters") or {},
        "mode": generated["mode"],
        "use_case_category": settings["use_case"],
        "content_hash": hashlib.sha256(normalised.encode("utf-8")).hexdigest(),
        "source_characters": len(normalised),
        "summary_characters": len(generated["summary"]),
        "summary_sentences": (
            len(_SENTENCE_SPLIT_RE.split(generated["summary"])) if generated["summary"] else 0
        ),
        "tlp_level": request.get("tlp_level"),
        "reference_uploaded_file": request.get("reference_uploaded_file"),
    }

    event_report_content = _build_event_report_content(generated["summary"], metadata)
    event_report = _build_event_report(
        request,
        content=event_report_content,
        use_case=str(settings["use_case"]),
    )

    return {
        "results": {
            "EventReport": [event_report],
            "Tag": _build_event_tags(),
        },
        "answer": {
            "summary": generated["summary"],
            "event_report_markdown": event_report_content,
        },
        "metadata": metadata,
        "tags": list(AI_COMPUTER_ASSISTED_TAG_NAMES),
    }


def handler(q: str | bool = False) -> dict[str, Any] | bool:  # pylint: disable=invalid-name
    if q is False:
        return False
    return dict_handler(json.loads(q))


def introspection() -> dict[str, Any]:
    return mispattributes


def version() -> dict[str, Any]:
    moduleinfo["config"] = moduleconfig
    return moduleinfo
