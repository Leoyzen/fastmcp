# Draft: RFC-URL-Mode-Elicitation Implementation Plan

## Core Objective
Add URL-mode elicitation support to FastMCP, enabling servers to direct users to external URLs for out-of-band interactions (OAuth, payments, etc.) via `ctx.elicit_url()`, while maintaining backward compatibility with existing form-mode elicitation.

## Scope

### IN Scope
- Server API: `ctx.elicit_url()` method on `Context`
- Error type: Export `UrlElicitationRequiredError` from `mcp.shared.exceptions`
- Client handling: Resolve `response_type=None` ambiguity with `Literal["url"]` marker
- Background tasks: URL-mode elicitation in Docket workers with mode discriminator
- Proxy support: Correct forwarding of URL-mode elicitation
- Security: HTTPS enforcement, dangerous scheme rejection via `AnyHttpUrl`
- Tests: Full TDD coverage for all new code paths
- Documentation: Server and client elicitation docs

### OUT of Scope
- Client-side auto-opening of URLs (violates MCP spec)
- URL reachability verification
- OAuth-specific helpers or state parameter validation
- Changes to existing form-mode elicitation behavior
- `ctx.complete_elicitation()` helper (follow-up enhancement)
- Server discovery (`mcp://` URI schemes, `.well-known`)

## File Paths (CRITICAL - use these exact paths)
- Add `ctx.elicit_url()` as a separate method from `ctx.elicit()` (Option B recommended)
- Export `UrlElicitationRequiredError` (code -32042) from `mcp.shared.exceptions`
- Resolve client-side `response_type=None` ambiguity; URL mode → `Literal["url"]`
- Support URL-mode elicitation in Docket background tasks with mode discriminator
- Update proxy forwarding for URL-mode elicitation
- Security: enforce HTTPS-only URLs, validate with `pydantic.AnyHttpUrl`, reject dangerous schemes
- Full test coverage + documentation

## File Paths (CRITICAL - use these exact paths)
All source code lives under `fastmcp_slim/fastmcp/`:
- `fastmcp_slim/fastmcp/server/context.py`
- `fastmcp_slim/fastmcp/server/elicitation.py`
- `fastmcp_slim/fastmcp/client/elicitation.py`
- `fastmcp_slim/fastmcp/server/tasks/elicitation.py`
- `fastmcp_slim/fastmcp/server/providers/proxy.py`
- `fastmcp_slim/fastmcp/server/__init__.py`
- `fastmcp_slim/fastmcp/server/tasks/notifications.py`

Tests live under `tests/`:
- `tests/server/test_elicitation_url.py` (new)
- `tests/client/test_elicitation_url.py` (new)
- `tests/server/tasks/test_task_elicitation_url.py` (new)
- `tests/server/providers/proxy/test_proxy_url_elicitation.py` (new)

Docs live under `docs/`:
- `docs/servers/elicitation.mdx`
- `docs/clients/elicitation.mdx`

## Decisions Already Made (from RFC)
- **Option B**: Separate `elicit_url()` method (not overload `elicit()`)
- **URL validation**: Accept `str`, validate internally with `AnyHttpUrl`
- **Exports**: `UrlElicitationRequiredError` and `AcceptedUrlElicitation` from `fastmcp.server.elicitation` and `fastmcp.server` only (not top-level)
- **Background task**: Add `mode` discriminator to Redis storage
- **Client handler**: Breaking type change only; runtime backward compatible
- **Concurrent elicitations**: Document single-pending-per-task limitation

## Research Findings (from explore agent)

### mcp SDK Types Availability
- `mcp.shared.exceptions.UrlElicitationRequiredError` - **EXISTS**
- `mcp.types.ElicitRequestURLParams` - **EXISTS** (fields: task, meta, mode, message, url, elicitationId)
- `mcp.types.URL_ELICITATION_REQUIRED` (-32042) - **EXISTS**
- `mcp.types.UrlElicitationCapability` - **EXISTS**
- `mcp.types.ElicitCompleteNotification` - **EXISTS**
- `mcp.types.AcceptedUrlElicitation` - **DOES NOT EXIST** → FastMCP must define its own

### Current Implementation State

**Server (`fastmcp/server/context.py`)**:
- `Context.elicit()` already handles foreground (direct `session.elicit()`) and background (`_elicit_for_task()`) modes
- Background mode delegates to `fastmcp.server.tasks.elicitation.elicit_for_task`

**Server Types (`fastmcp_slim/fastmcp/server/elicitation.py`)**:
- `AcceptedElicitation(BaseModel, Generic[T])` is FastMCP's own wrapper (Pydantic BaseModel)
- `DeclinedElicitation`, `CancelledElicitation` re-exported from `mcp.server.elicitation` (also BaseModels)
- No `AcceptedUrlElicitation` yet → MUST be a Pydantic BaseModel to match codebase pattern

**Background Tasks (`fastmcp_slim/fastmcp/server/tasks/elicitation.py`)**:
- Redis storage format: `{request_id, message, schema}` (NOT `requestedSchema`)
- No `mode` discriminator
- `relay_elicitation()` calls `session.elicit()` always (form mode)

**Proxy (`fastmcp/server/providers/proxy.py`)**:
- `default_proxy_elicitation_handler` already branches on param type but falls back to empty schema for URL mode
- Calls `ctx.session.elicit()` for both modes

**Exports (`fastmcp/server/__init__.py`)**:
- `__all__ = ["Context", "FastMCP", "create_proxy"]`
- Elicitation types NOT exported from `fastmcp.server` (users import from submodules)

### Test Infrastructure
- **Framework**: pytest + pytest-asyncio + pytest-xdist (parallel)
- **Existing tests**:
  - `tests/client/test_elicitation.py` (803 lines) - core flow
  - `tests/client/test_elicitation_enums.py` (516 lines) - enums
  - `tests/server/tasks/test_task_elicitation_relay.py` (191 lines) - background relay E2E
  - `tests/deprecated/test_elicitation.py` (29 lines) - deprecation
- **Patterns**: `fastmcp_server` fixture, `Client(mcp, elicitation_handler=handler)`

### Current Branch
- `main` (commit `53b20168`)

## User-Confirmed Decisions
- **Branch name**: `feat/url-mode-elicitation`
- **Test strategy**: TDD (write failing tests first, then implement to make them pass)
- **Additional docs**: None (RFC file list is complete)

### Key Verification Results

**SDK `session.elicit_url()` signature**:
```python
(self, message: str, url: str, elicitation_id: str, related_request_id: Union[int, str, None] = None) -> mcp.types.ElicitResult
```
- `elicitation_id` is **required** (no default) at SDK level
- FastMCP layer will auto-generate UUID if user doesn't provide

**`AnyHttpUrl` scheme validation**:
- ✅ Correctly rejects: `javascript:`, `data:`, `file:`, `ftp:`, `blob:`
- ✅ Allows: `https://`, `http://`
- ⚠️ Allows: `https://user:pass@example.com` (embedded credentials)
- Decision: `AnyHttpUrl` is sufficient; no additional scheme whitelist needed

**Notification subscriber routing** (`notifications.py` lines 200-229):
- Extracts `elicitation` from `_meta.io.modelcontextprotocol/related-task.elicitation`
- Passes full `elicitation` dict to `relay_elicitation(session, task_scope, task_id, elicitation, fastmcp)`
- Current dict format: `{request_id, message, requestedSchema}`
- New format needs: `{request_id, mode, message, url, elicitation_id}` or `{request_id, mode, message, requestedSchema}`

## Metis Review Findings

### Critical Gaps Addressed
1. **SDK signature verified**: `session.elicit_url()` exists with expected signature
2. **URL validation verified**: `AnyHttpUrl` rejects dangerous schemes
3. **Notification routing verified**: `relay_elicitation` receives full dict, mode discriminator will work

### Guardrails to Apply
1. **Export discipline**: `UrlElicitationRequiredError` and `AcceptedUrlElicitation` intentionally NOT exported from `fastmcp` top-level (per AGENTS.md)
2. **No auto-open**: Document explicitly that clients MUST NOT auto-open URLs
3. **URL userinfo**: Allow but document as security smell; MCP spec doesn't forbid
4. **Concurrent elicitations**: Document single-pending-per-task limitation (current behavior for form mode)

### Open Questions Resolved
- **AcceptedUrlElicitation structure**: Pydantic BaseModel (matching codebase pattern), with `action: Literal["accept"] = "accept"` (no data field for URL mode)
- **Background task backward compatibility**: Old Redis keys without `mode` will return `None`, fall through to form mode branch - safe
- **Client handler compatibility**: Existing handlers checking `response_type is None` will no longer match URL mode (this is the intended behavior change to resolve ambiguity)
- **Redis storage format**: `{request_id, message, schema}` (confirmed from code)
- **New Redis format for URL mode**: `{request_id, mode: "url", message, url, elicitation_id}`
- **New Redis format for form mode**: `{request_id, mode: "form", message, schema}`

## Final Decisions Before Plan Generation
- **Branch**: `feat/url-mode-elicitation`
- **Test strategy**: TDD (failing test → minimal impl → refactor)
- **AcceptedUrlElicitation**: Standalone class, not inheriting from `AcceptedElicitation`
- **URL validation**: `AnyHttpUrl` only (sufficient)
- **Embedded credentials**: Allow, document as security consideration
- **Concurrent elicitations**: Document limitation, no guard code
- **complete_elicitation()**: Out of scope (follow-up enhancement)