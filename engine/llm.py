"""Cached LLM client for the prediction pipeline.

Routes through LocalAPI (localhost:8000) which proxies to opencode.
Cache keyed on sha256(model + system + user + params).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import httpx

DEFAULT_BASE_URL = os.getenv("LOCALAI_URL", "http://localhost:8000/v1")
DEFAULT_MODEL = os.getenv("LOCALAI_MODEL", "localapi/mimo-v2.5-free")
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "llm"
REQUEST_TIMEOUT = 120.0
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0


def _cache_key(model: str, system: str, user: str, params: dict[str, Any]) -> str:
    """Compute sha256 cache key from prompt components."""
    payload = json.dumps(
        {"model": model, "system": system, "user": user, "params": params},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_cache(key: str) -> Optional[dict]:
    """Load cached response if it exists."""
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _save_cache(key: str, data: dict) -> None:
    """Save response to disk cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{key}.json"
    cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_json(text: str) -> Optional[str]:
    """Extract JSON from LLM response, tolerating markdown fences."""
    text = text.strip()
    # Try direct parse first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        if lines[0].startswith("```") and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1])
            try:
                json.loads(text)
                return text
            except json.JSONDecodeError:
                pass
    # Find first { or [ and try from there
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        end = text.rfind(end_char)
        if end > start:
            candidate = text[start : end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue
    return None


# Statistics
stats = {"calls": 0, "cache_hits": 0, "tolerant_extractions": 0, "retries": 0}


def chat_completion(
    system: str,
    user: str,
    *,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    use_cache: bool = True,
    parse_json: bool = True,
) -> dict[str, Any]:
    """Send a chat completion request with caching and retry.

    Returns:
        {"content": str, "parsed": Any|None, "cached": bool, "model": str}
    """
    params = {
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Check cache
    key = _cache_key(model, system, user, params)
    if use_cache:
        cached = _load_cache(key)
        if cached is not None:
            stats["cache_hits"] += 1
            cached["cached"] = True
            return cached

    # Build messages
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Retry loop
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.post(
                f"{base_url}/chat/completions",
                json=body,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code in (429, 500, 502, 503, 504):
                stats["retries"] += 1
                wait = RETRY_BACKOFF * (2 ** attempt)
                time.sleep(wait)
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                continue
            resp.raise_for_status()
            break
        except httpx.TimeoutException:
            stats["retries"] += 1
            wait = RETRY_BACKOFF * (2 ** attempt)
            time.sleep(wait)
            last_error = f"Timeout on attempt {attempt + 1}"
            continue
        except httpx.HTTPStatusError as e:
            stats["retries"] += 1
            wait = RETRY_BACKOFF * (2 ** attempt)
            time.sleep(wait)
            last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            continue
    else:
        # All retries exhausted
        return {
            "content": "",
            "parsed": None,
            "cached": False,
            "model": model,
            "error": last_error,
        }

    # Parse response
    resp_data = resp.json()
    content = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")

    # Tolerant JSON extraction
    parsed = None
    tolerant = False
    if parse_json and content:
        extracted = _extract_json(content)
        if extracted is not None:
            try:
                parsed = json.loads(extracted)
            except json.JSONDecodeError:
                pass
        if parsed is None and content.strip():
            tolerant = True
            stats["tolerant_extractions"] += 1

    stats["calls"] += 1

    result = {
        "content": content,
        "parsed": parsed,
        "cached": False,
        "model": model,
        "tolerant": tolerant,
    }

    # Cache the result
    if use_cache:
        _save_cache(key, result)

    return result


def get_stats() -> dict[str, int]:
    """Return call statistics."""
    return dict(stats)


def reset_stats() -> None:
    """Reset call statistics."""
    stats.clear()
    stats.update({"calls": 0, "cache_hits": 0, "tolerant_extractions": 0, "retries": 0})
