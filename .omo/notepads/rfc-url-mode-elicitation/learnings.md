# RFC-URL-Mode-Elicitation Learnings

## Conventions
- `AcceptedElicitation(BaseModel, Generic[T])` pattern at `fastmcp_slim/fastmcp/server/elicitation.py:105`
- `DeclinedElicitation`, `CancelledElicitation` re-exported from `mcp.server.elicitation` at lines 7-10
- `__all__` in `fastmcp_slim/fastmcp/server/__init__.py` currently `["Context", "FastMCP", "create_proxy"]`
- `Context.elicit()` at `context.py:1107-1203` with `_elicit_for_task()` at `1205-1243`
- Client `create_elicitation_callback()` at `client/elicitation.py:38-87` — currently ambiguous `response_type = None` for URL mode
- Proxy `default_proxy_elicitation_handler()` at `proxy.py:970-989` — currently falls back to empty schema for URL mode
- Background task `elicit_for_task()` at `tasks/elicitation.py:47-233`, `relay_elicitation()` at `236-289`
- Redis storage format currently `{request_id, message, schema}` (line 100-104)
- Notification subscriber passes full `elicitation` dict to `relay_elicitation()` (line 143-148)

## Key Patterns
- SDK `session.elicit_url()` signature: `(message, url, elicitation_id, related_request_id=None) -> ElicitResult`
- `AnyHttpUrl` correctly rejects dangerous schemes (`javascript:`, `data:`, `file:`)
- `AcceptedUrlElicitation` must be Pydantic BaseModel (matching `AcceptedElicitation` pattern)
- No top-level exports from `fastmcp.__init__` (per AGENTS.md)
- Background task mode discriminator uses `schema` key for form mode (not `requestedSchema`)

## Gotchas
- `ElicitRequestURLParams` vs `ElicitRequestFormParams` — URL params don't have `requestedSchema`
- Current client callback sets `response_type = None` for URL mode (ambiguous with deprecated empty-schema form mode)
- Proxy currently falls back to `{"type": "object", "properties": {}}` for URL mode (broken)
- Old Redis keys without `mode` must fall through to form mode for backward compatibility
