# RFC-URL-Mode-Elicitation Issues

## Wave 6 — Client Elicitation Documentation (COMPLETED)

### `docs/clients/elicitation.mdx` URL mode documentation
- **Status**: ✅ Completed
- **Changes made**:
  - Updated Handler Template: added `from typing import Literal` and `ElicitRequestURLParams` import; updated `response_type` signature to `type | Literal["url"] | None`; added three-branch `if/elif/else` showing URL mode, deprecated empty-schema form mode, and normal form mode
  - Updated How It Works `response_type` description to explain `Literal["url"]` vs `None`
  - Added new "URL Mode" section with `<VersionBadge version="3.4.0" />`
  - Explained distinction between URL mode (`response_type == "url"`) and deprecated empty-schema form mode (`response_type is None`)
  - Added "URL Mode Security Requirements" subsection with `<Warning>` callout documenting:
    - Clients MUST NOT auto-open URLs
    - Clients MUST show full URL and obtain explicit consent
    - Clients MUST NOT auto-fetch or pre-fetch URLs
  - Added focused URL mode handler example with explicit consent flow
  - Verified `grep -c "url" docs/clients/elicitation.mdx` returns 11
- **Lint/Type**: N/A (documentation file)

## Wave 3 — Client Callback URL Mode Detection (COMPLETED)

### `create_elicitation_callback()` & `ElicitationHandler` type alias
- **Status**: ✅ Completed
- **Files modified**:
  - `fastmcp_slim/fastmcp/client/elicitation.py`:
    - Added `Literal` import from `typing`
    - Added `ElicitRequestURLParams` import from `mcp.types`
    - Updated `ElicitationHandler` type alias: `type[T] | Literal["url"] | None` (line 31-32)
    - Updated `create_elicitation_callback()`: branches on `isinstance(params, ElicitRequestURLParams)` first → `response_type = "url"`, then `ElicitRequestFormParams` with existing empty-schema and parsed-type logic (lines 48-53)
- **Files created**:
  - `tests/client/test_elicitation_url.py` — 5 TDD tests covering:
    - `test_url_mode_passes_url_marker`: URL params → handler receives `"url"`
    - `test_deprecated_empty_schema_form_passes_none`: empty schema form → handler receives `None`
    - `test_normal_form_mode_passes_parsed_type`: non-empty schema form → handler receives parsed type
    - `test_handler_receives_url_params`: verifies all positional args for URL mode
    - `test_handler_receives_form_params`: verifies all positional args for form mode
- **Test results**: 5 new tests pass, 33 existing `tests/client/test_elicitation.py` tests still pass
- **Lint/Type**: Ruff clean, ty clean on all modified files
- **Key fix**: Resolves ambiguity where `response_type = None` was used for both URL mode and deprecated empty-schema form mode. Now URL mode is explicitly marked with `Literal["url"]` so handlers can distinguish.

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

## Wave 6 — Server Documentation for URL-Mode Elicitation (COMPLETED)

### docs/servers/elicitation.mdx updated
- **Status**: ✅ Completed
- **Files modified**:
  - `docs/servers/elicitation.mdx` — added new H2 section "URL-Mode Elicitation" after "Default Values"
    - Includes `<VersionBadge version="3.4.0" />` for the new feature
    - Comparison table: form mode (`ctx.elicit()`) vs URL mode (`ctx.elicit_url()`)
    - Complete runnable OAuth example with imports (`FastMCP`, `Context`, `AcceptedUrlElicitation`)
    - Security `<Warning>` callout covering HTTPS-only, no sensitive data in URL, no auto-open
    - `<Warning>` callout clarifying `AcceptedUrlElicitation` only means consent, not flow completion
    - `UrlElicitationRequiredError` documented with fallback-to-form-mode example
    - Optional `elicitation_id` parameter documented with tracking example
    - `elicit_url` appears 7 times in the document (verified via `grep -c`)
- **Lint/Type**: Prek checks clean on modified file
- **Cross-reference**: Client docs at `docs/clients/elicitation.mdx` reviewed for consistency

## Wave 5 — Background Task Elicitation with Mode Discriminator (COMPLETED)

### `elicit_url_for_task()`, `elicit_for_task()` mode field, `relay_elicitation()` branching
- **Status**: ✅ Completed
- **Files modified**:
  - `fastmcp_slim/fastmcp/server/tasks/elicitation.py`:
    - Updated `elicit_for_task()`: added `"mode": "form"` to the `elicit_request` dict stored in Redis (lines ~100-104)
    - Implemented `elicit_url_for_task()`: mirrors `elicit_for_task()` exactly with URL-mode fields
      - Stores `{request_id, mode: "url", message, url, elicitation_id}` in Redis
      - Pushes notification with `_meta.elicitation` containing `mode: "url"`, `url`, `elicitationId`
      - Uses same BLPOP wait pattern, fail-fast on notification push failure, TTL cleanup
    - Updated `relay_elicitation()`: branches on `elicitation.get("mode")`
      - `"url"` → `session.elicit_url(message, url, elicitation_id)`
      - `"form"` or missing → `session.elicit(message, requestedSchema)` (backward compatible)
- **Files created**:
  - `tests/server/tasks/test_task_elicitation_url.py` — 14 TDD tests covering:
    - `test_stores_mode_form_in_redis`: `elicit_for_task()` stores `"mode": "form"`
    - `test_stores_mode_url_in_redis`: `elicit_url_for_task()` stores `"mode": "url"` with `url` and `elicitation_id`
    - `test_notification_includes_url_metadata`: notification `_meta` includes `mode`, `url`, `elicitationId`
    - `test_raises_when_no_docket` / `test_raises_when_no_task_context`: error cases for `elicit_url_for_task()`
    - `test_relay_url_mode_calls_elicit_url`: relay branches to `session.elicit_url()`
    - `test_relay_form_mode_calls_elicit`: relay branches to `session.elicit()`
    - `test_relay_no_mode_falls_through_to_form_mode`: old Redis keys without `mode` fall through to form mode
    - `test_relay_url_mode_pushes_cancel_on_error`: relay pushes cancel when `elicit_url()` raises
    - E2E tests: accept/decline/cancel/no-handler for URL mode through full Client(mcp) pipeline
    - `test_notification_metadata_includes_url_mode`: notification metadata verification end-to-end
- **Test results**: 14 new tests pass, 7 existing relay tests still pass, 354 total server/tasks tests pass (0 failures)
- **Backward compatibility**: Old Redis keys without `"mode"` fall through to form mode; existing form-mode E2E tests unchanged
- **Key design decision**: Notification uses camelCase `elicitationId` (matching existing `requestId`/`requestedSchema` pattern), but `relay_elicitation()` receives this from the notification dict and passes snake_case `elicitation_id` to `session.elicit_url()` — this is the correct mapping because the SDK method signature uses snake_case.
