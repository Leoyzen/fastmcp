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
