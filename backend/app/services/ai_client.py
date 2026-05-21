from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings


def is_ai_configured() -> bool:
    settings = get_settings()
    return bool(settings.ai_api_key)


def extract_json_object(content: str) -> dict[str, Any]:
    if not content:
        return {}
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content, flags=re.IGNORECASE)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    raw = re.search(r"(\{[\s\S]*\})", content)
    if raw:
        try:
            parsed = json.loads(raw.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def chat_json(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.15,
) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.ai_api_key:
        return None
    url = f"{settings.ai_api_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model or settings.ai_model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.ai_api_key}",
    }
    try:
        req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urlopen(req, timeout=settings.ai_timeout_seconds) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        content = (((parsed.get("choices") or [{}])[0]).get("message") or {}).get("content", "")
        return extract_json_object(content)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None
