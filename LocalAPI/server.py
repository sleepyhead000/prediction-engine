"""LocalAPI — OpenAI-compatible proxy for opencode.

Translates OpenAI /v1/chat/completions requests into opencode's native API.
Point any OpenAI-compatible tool at http://localhost:8000/v1.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OPENCODE_HOST = os.getenv("OPENCODE_HOST", "127.0.0.1")
OPENCODE_PORT = int(os.getenv("OPENCODE_PORT", "4096"))
PROXY_PORT = int(os.getenv("PROXY_PORT", "8000"))
OPENCODE_BIN = os.getenv(
    "OPENCODE_BIN",
    r"C:\Users\khanc\nodejs\node_modules\opencode-ai\bin\opencode.exe",
)

# Map OpenAI model names → opencode provider/model IDs.
# Extend this dict or use MODEL_OVERRIDES env var (JSON).
MODEL_MAP: dict[str, dict[str, str]] = {
    "gpt-4o": {"id": "gpt-4o", "providerID": "openai"},
    "gpt-4o-mini": {"id": "gpt-4o-mini", "providerID": "openai"},
    "gpt-4": {"id": "gpt-4", "providerID": "openai"},
    "gpt-3.5-turbo": {"id": "gpt-3.5-turbo", "providerID": "openai"},
    "claude-sonnet-4-20250514": {"id": "claude-sonnet-4-20250514", "providerID": "anthropic"},
    "claude-3-5-sonnet-20241022": {"id": "claude-3-5-sonnet-20241022", "providerID": "anthropic"},
    "claude-3-haiku-20240307": {"id": "claude-3-haiku-20240307", "providerID": "anthropic"},
}

# ---------------------------------------------------------------------------
# OpenCode process management
# ---------------------------------------------------------------------------
_oc_process: subprocess.Popen | None = None


def _start_opencode():
    """Start opencode serve as a background process."""
    global _oc_process
    if _oc_process is not None:
        return
    try:
        _oc_process = subprocess.Popen(
            [OPENCODE_BIN, "serve", "--port", str(OPENCODE_PORT), "--hostname", OPENCODE_HOST],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        time.sleep(1)  # give it a moment to bind
    except Exception as e:
        print(f"Warning: could not start opencode serve: {e}", file=sys.stderr)


def _stop_opencode():
    """Stop the opencode process we started."""
    global _oc_process
    if _oc_process is not None:
        _oc_process.terminate()
        try:
            _oc_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _oc_process.kill()
        _oc_process = None


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------
_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            base_url=f"http://{OPENCODE_HOST}:{OPENCODE_PORT}",
            timeout=120.0,
        )
    return _http


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    _start_opencode()
    yield
    _stop_opencode()
    if _http and not _http.is_closed:
        await _http.aclose()


app = FastAPI(title="LocalAPI", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resolve_model(model_name: str) -> dict[str, str]:
    """Resolve an OpenAI model name to opencode's provider/model format."""
    if model_name in MODEL_MAP:
        return MODEL_MAP[model_name]
    # Try prefix matching: "gpt-4o-2024-08-06" → "gpt-4o"
    for prefix, ref in sorted(MODEL_MAP.items(), key=lambda x: -len(x[0])):
        if model_name.startswith(prefix):
            return ref
    # Passthrough: try providerID/modelID format (e.g. "anthropic/claude-3-5-sonnet")
    if "/" in model_name:
        provider, model_id = model_name.split("/", 1)
        # "localapi" prefix means route through opencode's free models
        if provider == "localapi":
            provider = "opencode"
        return {"id": model_id, "providerID": provider}
    # Default: assume providerID is "opencode" and id is the name
    return {"id": model_name, "providerID": "opencode"}


def _extract_text(parts: list[dict]) -> str:
    """Extract text content from opencode response parts."""
    texts = []
    for part in parts:
        if part.get("type") == "text":
            texts.append(part.get("text", ""))
    return "\n".join(texts)


def _openai_response(content: str, model: str, request_id: str | None = None) -> dict:
    """Build an OpenAI-compatible chat completion response."""
    rid = request_id or f"chatcmpl-{uuid.uuid4().hex[:24]}"
    return {
        "id": rid,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _openai_error(status: int, message: str, error_type: str = "server_error") -> JSONResponse:
    """Build an OpenAI-compatible error response."""
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "message": message,
                "type": error_type,
                "code": status,
            }
        },
    )


def _messages_to_text(messages: list[dict]) -> str:
    """Convert OpenAI messages array to a single text prompt."""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            # Handle multimodal content blocks
            content = " ".join(
                block.get("text", "") for block in content if block.get("type") == "text"
            )
        if role == "system":
            parts.append(f"[System]: {content}")
        elif role == "user":
            parts.append(content)
        elif role == "assistant":
            parts.append(f"[Assistant]: {content}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models():
    """List available models in OpenAI format."""
    client = _client()
    try:
        resp = await client.get("/api/model")
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return _openai_error(502, f"Failed to reach opencode: {e}")

    models = []
    for m in data.get("data", []):
        model_id = f"{m['providerID']}/{m['id']}"
        models.append({
            "id": model_id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": m.get("providerID", "unknown"),
            "permission": [],
            "root": model_id,
            "parent": None,
        })

    return {"object": "list", "data": models}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Handle OpenAI chat completion requests."""
    try:
        body = await request.json()
    except Exception:
        return _openai_error(400, "Invalid JSON body")

    messages = body.get("messages", [])
    model_name = body.get("model", "gpt-4o")
    stream = body.get("stream", False)

    if not messages:
        return _openai_error(400, "messages is required")

    # Resolve model
    model_ref = _resolve_model(model_name)

    # Build opencode prompt
    prompt_text = _messages_to_text(messages)

    # Create session + send message
    client = _client()
    try:
        # Create a new session (uses ModelRef: {id, providerID})
        session_resp = await client.post(
            "/api/session",
            json={"model": model_ref},
        )
        session_resp.raise_for_status()
        session_id = session_resp.json()["data"]["id"]

        # Send the message (uses {providerID, modelID} — different schema!)
        msg_model = {"providerID": model_ref["providerID"], "modelID": model_ref["id"]}
        msg_resp = await client.post(
            f"/session/{session_id}/message",
            json={
                "parts": [{"type": "text", "text": prompt_text}],
                "model": msg_model,
            },
        )
        msg_resp.raise_for_status()
        result = msg_resp.json()
    except httpx.HTTPStatusError as e:
        return _openai_error(502, f"opencode returned {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        return _openai_error(502, f"Failed to reach opencode: {e}")

    # Extract text from response
    parts = result.get("parts", [])
    content = _extract_text(parts)

    # Handle opencode errors
    info = result.get("info", {})
    if info.get("error"):
        error_msg = info["error"].get("message", str(info["error"]))
        return _openai_error(500, f"Agent error: {error_msg}")

    if stream:
        # Streaming response (SSE)
        async def generate():
            yield f"data: {json.dumps(_openai_response(content, model_name))}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")

    return _openai_response(content, model_name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT)
