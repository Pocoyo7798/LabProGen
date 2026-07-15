"""AIedu API client for LabProGen LLM features."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from src.core.paths import get_app_dir, get_config_dir

DEFAULT_AIEDU_CONFIG_FILENAME = "aiedu_config.json"

CONFIG_ENV_VARS = {
    "endpoint_url": "IAEDU_ENDPOINT",
    "api_key": "IAEDU_API_KEY",
    "channel_id": "IAEDU_CHANNEL_ID",
}


class AieduConfigError(RuntimeError):
    """Raised when AIedu credentials are missing or invalid."""


@dataclass(frozen=True)
class AieduConfig:
    endpoint_url: str
    api_key: str
    channel_id: str

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("endpoint_url", self.endpoint_url),
                ("api_key", self.api_key),
                ("channel_id", self.channel_id),
            )
            if not str(value or "").strip()
        ]
        if missing:
            joined = ", ".join(missing)
            raise AieduConfigError(f"AIedu configuration is incomplete: {joined}")


def _config_from_mapping(data: dict[str, Any]) -> AieduConfig | None:
    endpoint_url = str(data.get("endpoint_url") or "").strip()
    endpoint_url = endpoint_url.replace("agent-chat//api", "agent-chat/api")
    api_key = str(data.get("api_key") or "").strip()
    channel_id = str(data.get("channel_id") or "").strip()
    if not endpoint_url and not api_key and not channel_id:
        return None
    return AieduConfig(
        endpoint_url=endpoint_url,
        api_key=api_key,
        channel_id=channel_id,
    )


def get_aiedu_config_search_paths() -> tuple[Path, ...]:
    """Return config file locations to try when loading AIedu credentials."""
    return (
        get_config_dir() / DEFAULT_AIEDU_CONFIG_FILENAME,
        get_app_dir() / DEFAULT_AIEDU_CONFIG_FILENAME,
    )


def default_aiedu_config_path() -> Path:
    """Return the writable AIedu config path."""
    return get_config_dir() / DEFAULT_AIEDU_CONFIG_FILENAME


def load_aiedu_config(
    *,
    config_path: str | Path | None = None,
    search_paths: tuple[Path, ...] | None = None,
) -> AieduConfig | None:
    """Load AIedu credentials from a file and/or environment variables."""
    file_data: dict[str, Any] = {}
    if config_path is not None:
        candidates = [Path(config_path)]
    elif search_paths is not None:
        candidates = list(search_paths)
    else:
        candidates = list(get_aiedu_config_search_paths())

    for path in candidates:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            file_data.update(loaded)
            break

    merged = {
        "endpoint_url": os.getenv(CONFIG_ENV_VARS["endpoint_url"], file_data.get("endpoint_url", "")),
        "api_key": os.getenv(CONFIG_ENV_VARS["api_key"], file_data.get("api_key", "")),
        "channel_id": os.getenv(CONFIG_ENV_VARS["channel_id"], file_data.get("channel_id", "")),
    }
    return _config_from_mapping(merged)


def save_aiedu_config(
    config: AieduConfig,
    *,
    config_path: str | Path | None = None,
) -> Path:
    """Persist AIedu credentials to disk."""
    config.validate()
    path = Path(config_path) if config_path is not None else default_aiedu_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "endpoint_url": config.endpoint_url,
        "api_key": config.api_key,
        "channel_id": config.channel_id,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


@dataclass(frozen=True)
class AieduParseResult:
    text: str
    refused: bool = False
    stop_reason: str | None = None
    model_name: str | None = None


def _iter_json_events(response_text: str):
    """Yield JSON objects from AIedu NDJSON or concatenated responses."""
    stripped = response_text.strip()
    if not stripped:
        return

    line_events: list[dict[str, Any]] = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            line_events.append(payload)

    if line_events:
        yield from line_events
        return

    depth = 0
    start = None
    for index, char in enumerate(stripped):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                block = stripped[start : index + 1]
                try:
                    payload = json.loads(block)
                except json.JSONDecodeError:
                    start = None
                    continue
                if isinstance(payload, dict):
                    yield payload
                start = None


def parse_aiedu_response(response_text: str) -> AieduParseResult:
    """Parse AIedu stream events into assistant text and metadata."""
    parts: list[str] = []
    refused = False
    stop_reason: str | None = None
    model_name: str | None = None

    for event in _iter_json_events(response_text):
        if event.get("type") != "message":
            continue

        content = event.get("content")
        if isinstance(content, dict):
            chunk = content.get("content")
            if chunk:
                parts.append(str(chunk))

            metadata = content.get("response_metadata") or {}
            reason = metadata.get("stop_reason")
            if reason:
                stop_reason = str(reason)
                if reason == "refusal":
                    refused = True
            if metadata.get("model_name"):
                model_name = str(metadata["model_name"])
        elif isinstance(content, str) and content:
            parts.append(content)

    return AieduParseResult(
        text="".join(parts).strip(),
        refused=refused,
        stop_reason=stop_reason,
        model_name=model_name,
    )


def extract_message_content(response_text: str) -> str:
    """Extract the assistant message from an AIedu streaming/text response."""
    return parse_aiedu_response(response_text).text


class AieduClient:
    """Minimal HTTP client for the AIedu agent chat API."""

    def __init__(
        self,
        config: AieduConfig,
        *,
        timeout_seconds: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        config.validate()
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @classmethod
    def from_env(cls, **kwargs: Any) -> "AieduClient":
        config = load_aiedu_config()
        if config is None:
            raise AieduConfigError(
                "AIedu is not configured. Create config/aiedu_config.json or set "
                "IAEDU_ENDPOINT, IAEDU_API_KEY and IAEDU_CHANNEL_ID."
            )
        return cls(config, **kwargs)

    def complete(self, prompt: str) -> str:
        """Send one prompt and return the assistant text."""
        prompt = str(prompt or "").strip()
        if not prompt:
            raise ValueError("Prompt must not be empty")

        payload = {
            "channel_id": self.config.channel_id,
            "thread_id": str(uuid.uuid4()),
            "message": prompt,
            "user_info": "{}",
        }
        headers = {"x-api-key": self.config.api_key}

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.config.endpoint_url,
                    data=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(min(2 ** attempt, 8))
                continue

            if response.status_code == 429 or "Rate limit reached (429)" in response.text:
                time.sleep(min(2 ** (attempt + 1), 8))
                continue

            if not response.ok:
                raise RuntimeError(
                    f"AIedu request failed ({response.status_code}): {response.text[:500]}"
                )

            parsed = parse_aiedu_response(response.text)
            if parsed.refused:
                model_hint = f" ({parsed.model_name})" if parsed.model_name else ""
                raise RuntimeError(
                    "The AIedu model refused to generate content"
                    f"{model_hint}. Try a different agent/model in AIedu, "
                    "or shorten the protocol input."
                )
            if not parsed.text:
                raise RuntimeError(
                    "AIedu returned an empty response. Verify endpoint, channel ID and API key."
                )
            return parsed.text

        if last_error is not None:
            raise RuntimeError(f"AIedu request failed after retries: {last_error}") from last_error
        raise RuntimeError("AIedu request failed after retries.")
