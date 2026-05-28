---
rfc_id: RFC-00XX
title: FastMCP URL-Mode Elicitation Support
status: DRAFT
author: FastMCP Team
reviewers: []
created: 2025-05-28
last_updated: 2025-05-28
decision_date:
---

# RFC-00XX: FastMCP URL-Mode Elicitation Support

## Overview

This RFC proposes adding URL-mode elicitation support to FastMCP. URL-mode elicitation is an official MCP client capability (SEP-1036, spec 2025-11-25) that allows servers to direct users to external URLs for out-of-band interactions such as OAuth authorization, payment confirmations, or sensitive data entry. Unlike form-mode elicitation (which collects structured input in-band), URL-mode sends an HTTPS URL to the client, which presents it to the user for manual navigation.

FastMCP currently supports form-mode elicitation via `ctx.elicit()` but provides no API for URL-mode elicitation. This forces users to call the underlying `mcp` SDK directly, which produces poor error messages (`MCP error -32602: Client does not support URL-mode elicitation requests`) and breaks FastMCP's abstraction layer. This RFC closes that gap with a clean, consistent API.

## Background & Context

### MCP Elicitation Overview

MCP Elicitation is a client capability with two mutually exclusive modes:

| Mode | Purpose | Data Flow | FastMCP Support |
|------|---------|-----------|-----------------|
| **Form** | Collect structured, non-sensitive data via schema-driven forms | In-band through MCP client | `ctx.elicit()` — ✅ Supported |
| **URL** | Direct users to external URLs for sensitive interactions | Out-of-band via browser | **Not supported** — ❌ |

### URL-Mode Elicitation Protocol

A URL-mode elicitation is sent as a JSON-RPC `elicitation/create` request:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "elicitation/create",
  "params": {
    "mode": "url",
    "elicitationId": "550e8400-e29b-41d4-a716-446655440000",
    "url": "https://github.com/login/oauth/authorize?client_id=abc123&state=xyz789",
    "message": "Please authorize access to your GitHub repositories to continue."
  }
}
```

**Client response:** `{ "action": "accept" | "decline" | "cancel" }`

**Completion notification:** `notifications/elicitation/complete` with the `elicitationId`

**Error code for required URL elicitation:** `-32042` (`UrlElicitationRequiredError`)

### Security Requirements (from MCP Spec)

- Only HTTPS URLs are allowed
- Clients MUST NOT auto-fetch or auto-open URLs
- Clients MUST show the full URL and obtain explicit user consent
- Servers MUST NOT include sensitive data in the URL itself
- Servers MUST verify the user completing the flow is the same user who initiated it
- `elicitationId` MUST be unique per request (UUID recommended)

### Current FastMCP State

**Server-side (`Context.elicit()`):**
- Only calls `self.session.elicit(message, requestedSchema=schema)` — form-mode
- No `ctx.elicit_url()` method exists
- Background task elicitation (`elicit_for_task`) also only supports form-mode

**Client-side (`create_elicitation_callback`):**
- The callback handler already receives `ElicitRequestURLParams` (line 47-54 of `client/elicitation.py`)
- When `params` is `ElicitRequestURLParams`, it sets `response_type = None`
- **But `response_type = None` is also used for deprecated empty-schema form mode** — this is ambiguous
- There is no explicit URL-mode handling path

**Proxy-side (`default_proxy_elicitation_handler`):**
- Falls back to empty schema for URL mode and calls `session.elicit()` (form mode)
- URL-mode elicitation from a proxied server is incorrectly forwarded as form-mode

**Missing pieces:**
- `ctx.elicit_url(url, message, elicitation_id)` API
- `UrlElicitationRequiredError` exception export (correct path: `mcp.shared.exceptions`)
- Background task URL elicitation support with mode discriminator
- Client-side URL elicitation handler with unambiguous mode detection
- Proxy forwarding for URL-mode elicitation
- Documentation

## Problem Statement

Users building FastMCP servers that require OAuth flows, payment confirmations, or any out-of-band user interaction cannot use FastMCP's high-level APIs. They must:

1. Call the underlying `mcp` SDK's `session.elicit_url()` directly, breaking FastMCP's abstraction
2. Handle the `-32602` error manually when clients don't support URL-mode elicitation
3. Lack `UrlElicitationRequiredError` for declarative "this tool requires URL elicitation" patterns
4. Have no background task support for URL elicitation in Docket workers
5. Cannot proxy URL-mode elicitation correctly

**Impact:** This forces users to write verbose, error-prone code that bypasses FastMCP's conveniences. It also means FastMCP is not standards-compliant with MCP 2025-11-25 for the elicitation capability.

## Goals & Non-Goals

### Goals

1. **Server API**: Add `ctx.elicit_url(url, message, elicitation_id)` to `Context` for URL-mode elicitation
2. **Error Type**: Export `UrlElicitationRequiredError` (code `-32042`) from `mcp.shared.exceptions`
3. **Client Handling**: Resolve the `response_type=None` ambiguity; URL mode is passed as `Literal["url"]`
4. **Background Tasks**: Support URL-mode elicitation in Docket background tasks with mode discriminator
5. **Proxy Support**: Update `default_proxy_elicitation_handler` to correctly forward URL-mode elicitation
6. **Security**: Enforce HTTPS-only URLs, validate with `pydantic.AnyHttpUrl`, reject `javascript:` / `data:` schemes
7. **Testing**: Full test coverage for all new functionality
8. **Documentation**: Update server and client elicitation docs

### Non-Goals

1. **Auto-open behavior**: We will not implement client-side auto-opening of URLs (violates MCP spec)
2. **URL shortening/verification**: We will not verify that URLs are reachable or safe (out of scope)
3. **OAuth helpers**: This RFC is about the elicitation transport, not OAuth-specific logic (that belongs in auth modules)
4. **Form-mode changes**: No changes to existing form-mode elicitation behavior
5. **Server discovery**: This is unrelated to `mcp://` URI schemes or `.well-known/mcp-server` discovery
6. **Session verification**: Verifying the returning user matches the session (e.g., OAuth state parameter validation) is the server's responsibility and out of scope

## Evaluation Criteria

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Standards Compliance** | Critical | Must follow MCP 2025-11-25 spec and SEP-1036 exactly |
| **API Consistency** | High | Must match existing `ctx.elicit()` patterns and FastMCP style |
| **Security** | Critical | Must enforce HTTPS, reject dangerous schemes, and follow spec security requirements |
| **Backward Compatibility** | High | Must not break existing form-mode elicitation or client handlers |
| **Test Coverage** | High | All new code paths must be tested |
| **Implementation Effort** | Medium | Should be achievable in a single focused PR |

## Options Analysis

### Option A: Extend `ctx.elicit()` with a `url` parameter

**Description**: Add an optional `url` parameter to the existing `ctx.elicit()` method. When `url` is provided, send URL-mode elicitation instead of form-mode.

```python
# URL mode
result = await ctx.elicit(
    "Please authorize GitHub access",
    url="https://github.com/login/oauth/authorize?..."
)

# Form mode (existing)
result = await ctx.elicit(
    "What is your name?",
    response_type=str
)
```

**Advantages**:
- Minimal API surface — one method for all elicitation
- Reuses existing overload infrastructure
- Users don't need to learn a new method name

**Disadvantages**:
- Overloading `elicit()` with mutually exclusive parameters (`url` vs `response_type`) is confusing
- Type signatures become complex and harder to understand
- Violates the principle that different modes should have different APIs (they have fundamentally different semantics)
- `url` and `response_type` together make no sense but the type system can't easily prevent it

**Evaluation Against Criteria**:

| Criterion | Score | Notes |
|-----------|-------|-------|
| Standards Compliance | ✅ | Same underlying protocol |
| API Consistency | ⚠️ | Overloading one method for two very different semantics |
| Security | ✅ | Same security model |
| Backward Compatibility | ✅ | Existing calls unchanged |
| Test Coverage | ⚠️ | More complex test matrix due to parameter interactions |
| Implementation Effort | Medium | Requires complex overload refactoring |

**Effort Estimate**: Medium — requires refactoring all `elicit()` overloads

**Risk Assessment**: Medium — overloading could confuse users about when to use which mode

---

### Option B: Add separate `ctx.elicit_url()` method (Recommended)

**Description**: Add a new `ctx.elicit_url(url, message, elicitation_id)` method dedicated to URL-mode elicitation. Keep `ctx.elicit()` for form-mode only.

```python
# URL mode (new)
result = await ctx.elicit_url(
    url="https://github.com/login/oauth/authorize?...",
    message="Please authorize GitHub access",
    elicitation_id="550e8400-e29b-41d4-a716-446655440000",  # optional
)

# Form mode (existing, unchanged)
result = await ctx.elicit(
    "What is your name?",
    response_type=str
)
```

**Advantages**:
- **Clear separation of concerns** — different methods for fundamentally different operations
- **Better discoverability** — users can find `elicit_url` via autocomplete/IDE
- **Simpler type signatures** — no complex overloads with mutually exclusive parameters
- **Follows MCP spec naming** — spec uses "url mode" and "form mode" as distinct concepts
- **Easier to document** — each method has one purpose
- **Easier to test** — independent test suites for each mode
- **Natural `elicitation_id` parameter** — URL mode requires it per spec; a dedicated method can expose it cleanly

**Disadvantages**:
- Slightly larger API surface (one additional method)
- Users need to learn two method names instead of one

**Evaluation Against Criteria**:

| Criterion | Score | Notes |
|-----------|-------|-------|
| Standards Compliance | ✅ | Matches spec's explicit mode separation |
| API Consistency | ✅ | FastMCP already separates concerns (e.g., `read_resource` vs `call_tool`) |
| Security | ✅ | Dedicated method can enforce URL validation more explicitly |
| Backward Compatibility | ✅ | Zero changes to existing `elicit()` |
| Test Coverage | ✅ | Independent, focused tests |
| Implementation Effort | Low | Clean addition without refactoring |

**Effort Estimate**: Low-Medium — straightforward addition

**Risk Assessment**: Low — clean separation reduces confusion

---

### Option C: Expose raw `session.elicit_url()` without wrapper

**Description**: Document that users should call `ctx.session.elicit_url()` directly and provide examples.

**Advantages**:
- Zero implementation effort
- Immediate workaround for users

**Disadvantages**:
- Breaks FastMCP's abstraction layer
- Users must understand underlying MCP SDK internals
- No background task support
- No `UrlElicitationRequiredError` integration
- Poor developer experience
- Not a real solution

**Evaluation Against Criteria**:

| Criterion | Score | Notes |
|-----------|-------|-------|
| Standards Compliance | ✅ | Uses underlying SDK |
| API Consistency | ❌ | Violates FastMCP's design philosophy |
| Security | ⚠️ | Relies on SDK validation |
| Backward Compatibility | ✅ | No changes |
| Test Coverage | ❌ | No FastMCP-level tests |
| Implementation Effort | None | Just documentation |

**Effort Estimate**: None

**Risk Assessment**: High — perpetuates the problem rather than solving it

---

## Recommendation

**Option B: Add separate `ctx.elicit_url()` method**

This option scores highest across all criteria. The separation of form-mode and URL-mode elicitation into distinct methods aligns with:

1. **The MCP specification** — which explicitly treats them as separate modes
2. **FastMCP's design philosophy** — clear, focused APIs over overloaded swiss-army methods
3. **Developer experience** — better autocomplete, clearer documentation, less confusion
4. **Maintainability** — independent code paths that can evolve separately

The slight increase in API surface is a worthwhile trade-off for clarity and correctness.

## Technical Design

### 1. Server-Side API

#### `Context.elicit_url()`

Add a new method to `Context` in `fastmcp/server/context.py`:

```python
import uuid
from urllib.parse import urlparse

from pydantic import AnyHttpUrl

async def elicit_url(
    self,
    url: str,
    message: str,
    elicitation_id: str | None = None,
) -> AcceptedUrlElicitation | DeclinedElicitation | CancelledElicitation:
    """
    Send a URL-mode elicitation request to the client and await the response.

    Use this method when you need the user to visit an external URL for
    out-of-band interactions such as OAuth authorization, payment confirmation,
    or sensitive data entry.

    The client must support URL-mode elicitation, or the request will error.
    Clients MUST show the full URL to the user and obtain explicit consent
    before opening the URL. Clients MUST NOT auto-fetch or auto-open URLs.

    Args:
        url: The HTTPS URL the user should navigate to. Must use HTTPS scheme.
            Dangerous schemes (javascript:, data:, etc.) are rejected.
        message: A human-readable message explaining why the user needs to
            visit the URL.
        elicitation_id: A unique identifier for this elicitation request.
            Auto-generated as a UUID if not provided. Used for tracking and
            completion notifications.

    Returns:
        AcceptedUrlElicitation if the user accepts,
        DeclinedElicitation if the user declines, or
        CancelledElicitation if the user cancels.

    Raises:
        ValueError: If the URL is not a valid HTTPS URL or uses a dangerous scheme.
        McpError: If the client does not support URL-mode elicitation (code -32602).

    Example:
        ```python
        @mcp.tool
        async def github_auth(ctx: Context) -> str:
            result = await ctx.elicit_url(
                url="https://github.com/login/oauth/authorize?client_id=...",
                message="Please authorize FastMCP to access your GitHub repositories.",
            )
            if isinstance(result, AcceptedUrlElicitation):
                return "Authorization initiated. Please complete the flow in your browser."
            return "Authorization was declined or cancelled."
        ```
    """
```

**Implementation details:**
- Validate URL with `pydantic.AnyHttpUrl` (FastMCP already depends on Pydantic; this provides stronger validation than `urllib.parse`)
- Explicitly reject `javascript:`, `data:`, `file:`, and other dangerous schemes
- Auto-generate `elicitation_id` as `uuid.uuid4().hex` if not provided
- Call `self.session.elicit_url()` from the underlying MCP SDK
- Handle the same return types as `ctx.elicit()` but use `AcceptedUrlElicitation` for URL mode
- Support background task mode via `_elicit_url_for_task()`
- Wrap the SDK's `-32602` error in a clearer FastMCP exception when possible

#### `UrlElicitationRequiredError`

Export from `fastmcp/server/elicitation.py`:

```python
from mcp.shared.exceptions import UrlElicitationRequiredError

__all__ = [
    # ... existing exports ...
    "UrlElicitationRequiredError",
]
```

Also re-export from `fastmcp/server/__init__.py` for easy imports.

**Usage pattern:**

```python
from fastmcp.server.elicitation import UrlElicitationRequiredError

@mcp.tool
async def sensitive_operation(ctx: Context) -> str:
    if not has_oauth_token(ctx):
        raise UrlElicitationRequiredError(
            "https://example.com/oauth/authorize?...",
            "Please authorize to access sensitive data."
        )
    return perform_operation()
```

### 2. Background Task Support

#### `elicit_url_for_task()`

Add to `fastmcp/server/tasks/elicitation.py`:

```python
async def elicit_url_for_task(
    task_id: str,
    session: ServerSession | None,
    url: str,
    message: str,
    elicitation_id: str,
    fastmcp: FastMCP,
) -> mcp.types.ElicitResult:
    """Send a URL-mode elicitation request from a background task."""
```

**Implementation approach:**
- Reuse the same Redis-based coordination as `elicit_for_task`
- Store a mode discriminator in the Redis request object:
  ```python
  elicit_request = {
      "request_id": request_id,
      "mode": "url",  # NEW: mode discriminator
      "message": message,
      "url": url,     # NEW: URL for URL mode
      "elicitation_id": elicitation_id,  # NEW: tracking ID
  }
  ```
- Send `notifications/tasks/status` with `input_required` and URL metadata
- Update `relay_elicitation()` to branch on `mode`:
  ```python
  if elicitation.get("mode") == "url":
      result = await session.elicit_url(
          message=elicitation["message"],
          url=elicitation["url"],
          elicitation_id=elicitation["elicitation_id"],
      )
  else:
      result = await session.elicit(
          message=elicitation["message"],
          requestedSchema=elicitation["requestedSchema"],
      )
  ```

### 3. Client-Side Handling

The client-side callback in `fastmcp/client/elicitation.py` currently passes `response_type = None` for both URL mode and deprecated empty-schema form mode. This ambiguity must be resolved.

**Proposed fix:**

```python
def create_elicitation_callback(
    elicitation_handler: ElicitationHandler,
) -> ElicitationFnT:
    async def _elicitation_handler(
        context: RequestContext[ClientSession, LifespanContextT],
        params: ElicitRequestParams,
    ) -> MCPElicitResult | mcp.types.ErrorData:
        try:
            if isinstance(params, ElicitRequestFormParams):
                if params.requestedSchema == {"type": "object", "properties": {}}:
                    response_type = None  # Deprecated empty-schema form mode
                else:
                    response_type = json_schema_to_type(params.requestedSchema)
            elif isinstance(params, ElicitRequestURLParams):
                response_type = "url"  # NEW: unambiguous URL mode marker
            else:
                response_type = None

            result = await elicitation_handler(
                params.message, response_type, params, context
            )
            # ... rest unchanged ...
```

Update the `ElicitationHandler` type alias:

```python
from typing import Literal

ElicitationHandler: TypeAlias = Callable[
    [
        str,                              # message
        type[T] | Literal["url"] | None,  # response_type or "url" marker
        ElicitRequestParams,
        RequestContext[ClientSession, LifespanContextT],
    ],
    Awaitable[T | dict[str, Any] | ElicitResult[T | dict[str, Any]]],
]
```

This is a **breaking type change** for existing handlers. To maintain backward compatibility:
- Existing handlers that check `response_type is None` will continue to work (both deprecated form mode and URL mode previously passed `None`)
- Handlers that want to support URL mode can add an `elif response_type == "url":` branch
- We do NOT break runtime behavior — only the type annotation becomes more precise

### 4. Proxy Support

Update `fastmcp/server/providers/proxy.py`:

```python
async def default_proxy_elicitation_handler(
    message: str,
    response_type: type | Literal["url"] | None,
    params: mcp.types.ElicitRequestParams,
    context: RequestContext[ClientSession, LifespanContextT],
) -> ElicitResult:
    """Forward elicitation request from remote server to proxy's connected clients."""
    ctx = get_context()
    if isinstance(params, ElicitRequestURLParams):
        result = await ctx.session.elicit_url(
            message=message,
            url=params.url,
            elicitation_id=params.elicitationId,
            related_request_id=ctx.request_id,
        )
    else:
        requested_schema = params.requestedSchema
        result = await ctx.session.elicit(
            message=message,
            requestedSchema=requested_schema,
            related_request_id=ctx.request_id,
        )
    return ElicitResult(action=result.action, content=result.content)
```

### 5. File Changes

| File | Changes |
|------|---------|
| `fastmcp/server/context.py` | Add `elicit_url()` method; add `_elicit_url_for_task()` helper |
| `fastmcp/server/elicitation.py` | Export `UrlElicitationRequiredError` from `mcp.shared.exceptions`; export `AcceptedUrlElicitation` |
| `fastmcp/server/tasks/elicitation.py` | Add `elicit_url_for_task()`, update `relay_elicitation()` to branch on `mode`, add `mode`/`url`/`elicitation_id` to Redis storage |
| `fastmcp/client/elicitation.py` | Update handler to pass `Literal["url"]` for URL mode, update type alias |
| `fastmcp/server/providers/proxy.py` | Update `default_proxy_elicitation_handler` to forward URL mode correctly |
| `fastmcp/server/__init__.py` | Export `UrlElicitationRequiredError` and `AcceptedUrlElicitation` |
| `tests/server/test_elicitation_url.py` | New test file for URL-mode server behavior |
| `tests/client/test_elicitation_url.py` | New test file for URL-mode client handling |
| `tests/server/tasks/test_task_elicitation_url.py` | New test file for background task URL elicitation |
| `tests/server/providers/proxy/test_proxy_url_elicitation.py` | New test file for proxy URL-mode forwarding |
| `docs/servers/elicitation.mdx` | Document `ctx.elicit_url()` and `UrlElicitationRequiredError` |
| `docs/clients/elicitation.mdx` | Document client-side URL elicitation handling |

### 6. Security Considerations

1. **URL Validation**: `elicit_url()` uses `pydantic.AnyHttpUrl` to validate URLs. This enforces:
   - HTTPS scheme only
   - Valid hostname parsing
   - IDNA encoding support
   - Rejection of `javascript:`, `data:`, `file:`, and other dangerous schemes

2. **No Auto-Open**: FastMCP client MUST NOT auto-open URLs (already true since we don't control clients, but our docs must emphasize this)

3. **No Sensitive Data in URL**: Document that servers must not put tokens, passwords, or PII in the URL query string

4. **Session Verification Warning**: Document that `AcceptedUrlElicitation` only means the user clicked "accept" — it does NOT mean the out-of-band flow (e.g., OAuth callback) completed. Servers must independently verify completion.

5. **Elicitation ID Uniqueness**: Auto-generated IDs use `uuid.uuid4().hex` to prevent prediction and session fixation attacks

6. **URL Length Limits**: No explicit limit enforced, but extremely long URLs (>4096 chars) may fail at the JSON-RPC or HTTP transport layer. Document this as a known constraint.

## Implementation Plan

### Phase 1: Core Server API (1-2 days)
1. Export `UrlElicitationRequiredError` from `mcp.shared.exceptions`
2. Export `AcceptedUrlElicitation` from the SDK
3. Implement `Context.elicit_url()` with `pydantic.AnyHttpUrl` validation
4. Add basic unit tests

### Phase 2: Background Tasks (1-2 days)
1. Update Redis storage format with `mode` discriminator
2. Implement `elicit_url_for_task()`
3. Update `relay_elicitation()` to handle URL mode
4. Add background task tests

### Phase 3: Client & Proxy (1-2 days)
1. Update `create_elicitation_callback()` for unambiguous URL mode detection (`Literal["url"]`)
2. Update `ElicitationHandler` type alias
3. Update `default_proxy_elicitation_handler` for URL mode forwarding
4. Add client and proxy integration tests

### Phase 4: Documentation (1 day)
1. Update server elicitation docs with `elicit_url()` examples
2. Update client elicitation docs with URL mode handler examples
3. Add security best practices section

### Total Estimated Effort: 5-7 days

## Open Questions

1. **Should `elicit_url()` accept `pydantic.AnyHttpUrl` directly in the type signature?**
   - `AnyHttpUrl` provides strong validation but the error messages may be cryptic for users
   - Accept `str` and validate internally with `AnyHttpUrl` for better error messages
   - **Resolution**: Accept `str` and validate with `AnyHttpUrl` internally

2. **Should `AcceptedUrlElicitation` be re-exported from `fastmcp` top-level?**
   - Current `fastmcp.__init__.py` doesn't export `AcceptedElicitation`
   - Adding it to top-level could cause import bloat
   - **Resolution**: Export from `fastmcp.server.elicitation` and `fastmcp.server` only

3. **Should we provide a `ctx.complete_elicitation(elicitation_id)` helper?**
   - The spec allows servers to send `notifications/elicitation/complete`
   - Useful for telling the client the out-of-band flow finished
   - **Resolution**: Yes, add as a follow-up enhancement after the core feature lands

4. **How should concurrent elicitations in the same task be handled?**
   - The current Redis key structure uses `{task_id}:elicit:*` which assumes one pending elicitation per task
   - Multiple concurrent elicitations would collide
   - **Resolution**: Document that only one elicitation can be pending per task at a time. This matches current behavior for form mode.

## Decision Record

**Decision**: Implement Option B — add `ctx.elicit_url()` as a separate method from `ctx.elicit()`.

**Rationale**:
- URL-mode and form-mode elicitation have fundamentally different semantics (out-of-band vs in-band, no schema vs structured schema)
- The MCP specification explicitly separates them as distinct modes
- A separate method provides better API clarity, discoverability, and maintainability
- This approach aligns with FastMCP's design philosophy of focused, single-purpose APIs

**Trade-offs accepted**:
- Slightly larger API surface (one additional method)
- Users must learn two method names
- Client handler type annotation becomes more complex (`Literal["url"]` marker)

**Conditions for approval**:
- All tests pass
- Documentation is complete
- Security validation (HTTPS-only, dangerous scheme rejection) is enforced
- Backward compatibility with form-mode elicitation is verified
- Proxy forwarding for URL mode is tested
- Background task URL elicitation relay is tested

---

## Appendix: Reference Implementation Sketch

### Server usage

```python
from fastmcp import FastMCP, Context
from fastmcp.server.elicitation import AcceptedUrlElicitation

mcp = FastMCP("OAuth Demo")

@mcp.tool
async def connect_github(ctx: Context) -> str:
    """Connect your GitHub account."""
    result = await ctx.elicit_url(
        url="https://github.com/login/oauth/authorize?client_id=...&state=...",
        message="Please authorize FastMCP to access your GitHub repositories.",
    )

    if isinstance(result, AcceptedUrlElicitation):
        return "Authorization started. Complete the flow in your browser."
    else:
        return "Authorization was cancelled."
```

### Declarative URL elicitation requirement

```python
from fastmcp.server.elicitation import UrlElicitationRequiredError

@mcp.tool
async def access_protected_data() -> str:
    """Access protected data (requires authorization)."""
    raise UrlElicitationRequiredError(
        url="https://example.com/oauth/authorize",
        message="Please authorize to access protected data.",
    )
```

### Client usage

```python
from fastmcp import Client

async def elicitation_handler(message, response_type, params, context):
    if response_type == "url":
        print(f"Please visit: {params.url}")
        print(f"Reason: {message}")
        # Wait for user to complete the flow...
        return {"action": "accept"}
    elif response_type is None:
        # Deprecated empty-schema form mode
        return {"action": "accept"}
    else:
        # Form mode with schema
        return {"action": "accept", "content": {"value": "user input"}}

client = Client(
    "https://example.com/mcp",
    elicitation_handler=elicitation_handler,
)
```

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-05-28 | Initial draft | FastMCP Team |
| 2025-05-28 | **Revised** based on Metis and Oracle reviews: fixed `elicitation_id` gap, corrected `UrlElicitationRequiredError` import path, added `mode` discriminator for background tasks, resolved client handler ambiguity with `Literal["url"]`, added proxy support, switched URL validation to `pydantic.AnyHttpUrl`, updated return type to `AcceptedUrlElicitation` | FastMCP Team |
