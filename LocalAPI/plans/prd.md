
## System Architecture

The core workflow translates standard API HTTP requests into local terminal commands, returning the output in the expected JSON format.

1. **The Client:** Any application requiring an API key.
2. **The Local Server:** A lightweight web server running on your laptop that intercepts requests.
3. **The Validator:** A custom module within the server that generates or blindly accepts local API keys to satisfy the client's authentication checks.
4. **The Execution Engine:** The server translates the payload into a CLI command and executes it locally.
5. **The Response Formatter:** The CLI's standard output is captured, structured into the expected API JSON schema, and returned to the client.

## Implementation Plan

### Phase 1: Server Setup & Routing

Using FastAPI is the most efficient approach for this, as its asynchronous capabilities handle I/O-bound subprocess routing perfectly.

* **Initialize the Server:** Spin up a basic FastAPI application locally (e.g., on `localhost:8000`).
* **Define Endpoints:** Recreate the standard endpoint paths expected by most client applications, such as `/v1/chat/completions`.
* **Request Models:** Create Pydantic models to parse incoming JSON payloads so the server knows how to extract the prompt, temperature, and system messages.

### Phase 2: API Key Management

The handwritten note specifies that the server itself will generate the API key, which can be put into "any API key place."

* **Key Generator Endpoint:** Create a simple endpoint (e.g., `/generate-key`) that outputs a randomized string formatted like a standard API key (e.g., `sk-local-...`).
* **Authentication Middleware:** Configure the FastAPI server to intercept the `Authorization: Bearer <key>` header. Since this is a local proxy, you can program the middleware to validate *any* key that begins with your custom prefix, allowing immediate integration with third-party tools without complex database lookups.

### Phase 3: CLI Subprocess Integration

This is the core execution layer where the web request meets your local hardware.

* **Subprocess Execution:** Use Python's built-in `subprocess` or `asyncio.create_subprocess_shell` to pass the extracted prompts directly to your local models.
* **Routing to Local Engines:** This layer can pipe commands directly into Ollama or route them through your existing `arc_engine` loop to leverage your local GPU acceleration.
* **Streaming Support:** If the client applications expect streaming responses (like a typing effect), implement a generator function that yields stdout from the CLI process chunk by chunk.

### Phase 4: Response Formatting

To ensure the client applications do not break, the output from your local CLI must be heavily sanitized and repackaged.

* **Schema Mapping:** Capture the raw text output from the CLI and map it back into the standard response JSON format (including fake token usage statistics and standard object IDs).
* **Error Handling:** If the local CLI fails to generate a response or crashes, the server should return standard HTTP error codes (like 500 or 503) formatted in the expected API error schema, rather than letting the subprocess failure crash the server.
