# RFC-URL-Mode-Elicitation Issues

## Wave 1 — Foundation (COMPLETED)

### AcceptedUrlElicitation & UrlElicitationRequiredError
- **Status**: ✅ Completed
- **Files modified**:
  - `fastmcp_slim/fastmcp/server/elicitation.py` — added `AcceptedUrlElicitation` (Pydantic BaseModel, `action: Literal["accept"] = "accept"`, no generic, no data field) and re-exported `UrlElicitationRequiredError` from `mcp.shared.exceptions`
  - `fastmcp_slim/fastmcp/server/__init__.py` — updated `__all__` and `__getattr__` to lazy-import both
- **Tests**: `tests/server/test_elicitation_url.py` (12 tests, all passing)
  - `AcceptedUrlElicitation` creation, serialization, BaseModel subclass, no data field
  - `UrlElicitationRequiredError` importable, is Exception, can be raised/caught with proper `ElicitRequestURLParams`
  - Both importable from `fastmcp.server`
  - Neither exported from `fastmcp` top-level

## Wave 2 — Context.elicit_url() (COMPLETED)

### Context.elicit_url() & _elicit_url_for_task()
- **Status**: ✅ Completed
- **Files modified**:
  - `fastmcp_slim/fastmcp/server/context.py` — added `elicit_url()` method (lines ~1209-1303) and `_elicit_url_for_task()` helper (lines ~1320-1356)
    - Imports: `uuid`, `AnyHttpUrl` from `pydantic.networks`, `McpError` from `mcp.shared.exceptions`, `AcceptedUrlElicitation`, `UrlElicitationRequiredError` from `fastmcp.server.elicitation`
    - URL validation with `pydantic.AnyHttpUrl` — rejects `javascript:`, `data:`, `file:` and missing schemes
    - Auto-generates `elicitation_id` as `uuid.uuid4().hex` if not provided
    - Foreground mode: calls `self.session.elicit_url(message, url, elicitation_id, related_request_id)`
    - Background mode: delegates to `_elicit_url_for_task()` mirroring `_elicit_for_task` pattern
    - Maps SDK `ElicitResult` to FastMCP types (`AcceptedUrlElicitation`, `DeclinedElicitation`, `CancelledElicitation`)
    - Handles `McpError` with code `-32602` by raising `UrlElicitationRequiredError`
  - `fastmcp_slim/fastmcp/server/tasks/elicitation.py` — added stub `elicit_url_for_task()` (to be fully implemented in Task 5)
- **Tests**: `tests/server/test_elicitation_url.py` (27 tests total, all passing)
  - URL validation: valid HTTPS, invalid scheme (`javascript:`, `data:`, `file:`), missing scheme
  - Auto-generated `elicitation_id` (32-char hex UUID)
  - Provided `elicitation_id` used as-is
  - Foreground mode calls `session.elicit_url()` with correct args including `related_request_id`
  - Background mode calls `_elicit_url_for_task()`
  - Error handling: `McpError(-32602)` → `UrlElicitationRequiredError`
  - Result mapping: accept → `AcceptedUrlElicitation`, decline → `DeclinedElicitation`, cancel → `CancelledElicitation`
  - Unexpected action raises `ValueError`
  - `_elicit_url_for_task()` raises `RuntimeError` when not in background task
- **Lint/Type**: Ruff clean, ty clean on all modified files
- **Full server test suite**: 2790 passed, 0 failed
