# RFC-URL-Mode-Elicitation Decisions

## Branch: feat/url-mode-elicitation

## Architecture Decisions
- Option B (separate `elicit_url()` method) confirmed as approach
- `AcceptedUrlElicitation` is simple BaseModel with `action: Literal["accept"] = "accept"` — no generic type, no data field
- `UrlElicitationRequiredError` re-exported from `mcp.shared.exceptions`
- Client handler passes `Literal["url"]` for URL mode to resolve `None` ambiguity
- Background task stores `mode: "url" | "form"` discriminator in Redis
- Proxy branches on param type (`ElicitRequestURLParams` vs `ElicitRequestFormParams`)
