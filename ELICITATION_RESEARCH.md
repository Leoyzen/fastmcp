# MCP Elicitation / Discovery URL Research Report

> Research conducted: 2026-05-28
> Scope: Official MCP specification, SDKs, GitHub issues/PRs, and SEPs

---

## Executive Summary

The Model Context Protocol (MCP) defines **Elicitation** as a client capability that allows servers to request additional information from users during interactions. Elicitation supports two modes:

1. **Form mode** (`mode: "form"`) — In-band structured data collection with JSON Schema validation. Used for non-sensitive data.
2. **URL mode** (`mode: "url"`) — Out-of-band interaction via external URL navigation. Used for sensitive operations (OAuth, payments, credentials).

**URL mode elicitation** was introduced in the `2025-11-25` MCP specification via **SEP-1036**. It is the MCP-standard mechanism for "discovery" or "elicitation" URLs — directing users to external URLs for secure interactions that must not pass through the MCP client.

There is **no separate "discovery URL" concept** in MCP. URL-mode elicitation serves this purpose.

---

## 1. Official MCP Specification

### 1.1 Protocol Version

URL mode elicitation is specified in:
- **MCP Specification 2025-11-25** (latest)
- **SEP-1036**: "URL Mode Elicitation for secure out-of-band interactions" (Final, Standards Track)

Form mode elicitation existed in the 2025-06-18 specification. URL mode was added in 2025-11-25.

### 1.2 Capability Declaration

Clients declare elicitation support during `initialize`:

```json
{
  "capabilities": {
    "elicitation": {
      "form": {},
      "url": {}
    }
  }
}
```

For backwards compatibility, an empty object `{}` is equivalent to `{ "form": {} }`.

Clients MUST support at least one mode. Servers MUST NOT send requests with unsupported modes.

### 1.3 Elicitation Request Format

**Method:** `elicitation/create`

**Common parameters (both modes):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | string | Yes* | `"form"` or `"url"`. Optional for form mode (defaults to `"form"`). |
| `message` | string | Yes | Human-readable explanation of why input is needed. |

**Form mode additional parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `requestedSchema` | object | Yes | JSON Schema defining the expected response structure. |

**URL mode additional parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | The URL the user should navigate to. MUST be a valid URL. |
| `elicitationId` | string | Yes | Unique identifier for tracking this elicitation. |

**URL mode request example:**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "elicitation/create",
  "params": {
    "mode": "url",
    "elicitationId": "550e8400-e29b-41d4-a716-446655440000",
    "url": "https://github.com/login/oauth/authorize?client_id=abc123&state=xyz789&scope=repo",
    "message": "Please authorize access to your GitHub repositories to continue."
  }
}
```

### 1.4 Response Format

Both modes use a three-action response model:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "action": "accept"  // or "decline" or "cancel"
  }
}
```

- **`accept`**: User explicitly approved. For URL mode, this means user consented to navigate to the URL. The interaction occurs out-of-band.
- **`decline`**: User explicitly declined.
- **`cancel`**: User dismissed without making a choice (closed dialog, pressed Escape, etc.).

For form mode, `accept` includes `content` with the submitted data. For URL mode, `content` is omitted.

### 1.5 Completion Notification

Servers MAY send a notification when URL-mode elicitation completes:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/elicitation/complete",
  "params": {
    "elicitationId": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

- MUST only be sent to the client that initiated the request.
- Clients MUST ignore notifications with unknown/completed IDs.
- Clients MAY use this to auto-retry failed requests or update UI.

### 1.6 URL Elicitation Required Error

When a request cannot proceed without URL elicitation, servers MAY return error code `-32042`:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32042,
    "message": "This request requires more information.",
    "data": {
      "elicitations": [
        {
          "mode": "url",
          "elicitationId": "550e8400-e29b-41d4-a716-446655440000",
          "url": "https://oauth.example.com/authorize?client_id=abc123&response_type=code&...",
          "message": "Authorization is required to access your Example Co files."
        }
      ]
    }
  }
}
```

This is equivalent to sending an `elicitation/create` request and is an affordance to tie the elicitation directly to a failed request.

### 1.7 Security Requirements for URL Mode

**Servers MUST NOT:**
- Include sensitive user information (credentials, PII) in the URL.
- Provide a pre-authenticated URL that could be used to impersonate the user.
- Include clickable URLs in form mode requests.

**Clients MUST:**
- NOT automatically pre-fetch the URL or its metadata.
- NOT open the URL without explicit user consent.
- Show the full URL to the user before consent.
- Open the URL in a secure browser context (e.g., SFSafariViewController on iOS, NOT WKWebView).
- Highlight the domain to mitigate subdomain spoofing.
- Warn about ambiguous/suspicious URIs (Punycode, etc.).

**Servers MUST:**
- Bind elicitation state to authenticated user identity (not just session IDs).
- Verify the user completing the URL flow is the same user who initiated it.
- Use HTTPS URLs for non-development environments.

### 1.8 Key Distinction: URL Elicitation vs. MCP Authorization

URL mode elicitation is **NOT** for authorizing the MCP client's access to the MCP server. That is handled by the separate [MCP Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) specification.

URL mode elicitation is for:
- Obtaining sensitive information on behalf of the user (API keys, credentials).
- Performing OAuth flows with **third-party** resource servers.
- Handling payments or subscriptions.

The MCP client's bearer token remains unchanged. The client is only responsible for showing the user the URL and getting consent to open it.

---

## 2. TypeScript SDK Implementation

The official `@modelcontextprotocol/sdk` (v2) implements full elicitation support.

### 2.1 Core Types

**`packages/core/src/types/spec.types.ts`**
- `URL_ELICITATION_REQUIRED = -32042`
- `ElicitRequest` interface with `method: 'elicitation/create'`

**`packages/core/src/types/errors.ts`**
- `UrlElicitationRequiredError` extends `ProtocolError`
  - Constructor: `(elicitations: ElicitRequestURLParams[], message?: string)`
  - Default message: `` `URL elicitation${elicitations.length > 1 ? 's' : ''} required` ``

**`packages/core/src/types/enums.ts`**
- `ProtocolErrorCode.UrlElicitationRequired = -32_042`

**`packages/core/src/types/schemas.ts`**
- `ElicitRequestSchema = RequestSchema.extend({ method: z.literal('elicitation/create'), params: ElicitRequestParamsSchema })`

### 2.2 Client Implementation

**`packages/client/src/client/client.ts`**
- `getSupportedElicitationModes()` — public helper
- Elicitation default application helper — applies defaults to `data` based on `schema`
- Capability check: throws `SdkError` if client does not support elicitation

**Client capability declaration:**
```typescript
const client = new Client(
  { name: 'my-client', version: '1.0.0' },
  {
    capabilities: {
      sampling: {},
      elicitation: { form: {} }
    }
  }
);
```

**Client handler registration:**
```typescript
client.setRequestHandler('elicitation/create', async request => {
  if (request.params.mode === 'url') {
    // Show URL to user, get consent, open in browser
    return { action: 'accept' };
  }
  // ... form mode handling
});
```

### 2.3 Server Implementation

**`packages/server/src/server/server.ts`**
- JSON Schema validator for elicitation response validation
- Capability check for `elicitation/create`

**`packages/server/src/server/mcp.ts`**
- Tool call handler propagates `UrlElicitationRequired` errors without wrapping:
```typescript
if (error instanceof ProtocolError && error.code === ProtocolErrorCode.UrlElicitationRequired) {
  throw error;
}
```

**Server-side elicitation in tool handler:**
```typescript
server.registerTool('collect-feedback', {
  description: 'Collect user feedback via a form',
  inputSchema: z.object({})
}, async (_args, ctx) => {
  const result = await ctx.mcpReq.elicitInput({
    mode: 'url',
    message: 'Please authorize this app:',
    url: 'https://example.com/oauth/authorize?...',
    elicitationId: 'auth-001'
  });
  // ...
});
```

### 2.4 Examples

- `examples/server/src/elicitationFormExample.ts` — Form mode for non-sensitive input
- `examples/server/src/elicitationUrlExample.ts` — URL mode for sensitive/OAuth flows
- `examples/client/src/elicitationUrlExample.ts` — Client handling URL mode with OAuth redirect

---

## 3. Python SDK Implementation

The official `mcp` Python SDK (v2, separate from FastMCP) implements full elicitation support.

### 3.1 Core Types

**`src/mcp/server/elicitation.py`**
```python
class AcceptedElicitation(BaseModel, Generic[ElicitSchemaModelT]):
    action: Literal["accept"] = "accept"
    data: ElicitSchemaModelT

class DeclinedElicitation(BaseModel):
    action: Literal["decline"] = "decline"

class CancelledElicitation(BaseModel):
    action: Literal["cancel"] = "cancel"

class AcceptedUrlElicitation(BaseModel):
    action: Literal["accept"] = "accept"

ElicitationResult = AcceptedElicitation[ElicitSchemaModelT] | DeclinedElicitation | CancelledElicitation
UrlElicitationResult = AcceptedUrlElicitation | DeclinedElicitation | CancelledElicitation
```

**`src/mcp/types/jsonrpc.py`**
```python
URL_ELICITATION_REQUIRED = -32042
"""Error code indicating that a URL mode elicitation is required."""
```

**`src/mcp/shared/exceptions.py`**
```python
class UrlElicitationRequiredError(MCPError):
    """Raised when a URL mode elicitation is required."""
```

### 3.2 Server API

**Form mode:**
```python
async def elicit_with_validation(
    session: ServerSession,
    message: str,
    schema: type[ElicitSchemaModelT],
    related_request_id: RequestId | None = None,
) -> ElicitationResult[ElicitSchemaModelT]:
```

**URL mode:**
```python
async def elicit_url(
    session: ServerSession,
    message: str,
    url: str,
    elicitation_id: str,
    related_request_id: RequestId | None = None,
) -> UrlElicitationResult:
```

### 3.3 Client API

**`src/mcp/client/client.py`**
```python
client = Client(
    mcp_server,
    elicitation_callback=elicitation_callback
)
```

**`src/mcp/client/session.py`**
Client sessions declare elicitation capabilities:
```python
elicitation = types.ElicitationCapability(
    form=types.FormElicitationCapability(),
    url=types.UrlElicitationCapability()
)
```

### 3.4 Examples

- `examples/snippets/servers/elicitation.py` — Form and URL mode examples
- `examples/snippets/clients/url_elicitation_client.py` — URL mode client
- `examples/servers/simple-task-interactive/` — Task-augmented elicitation

---

## 4. Other SDKs

| SDK | URL Mode Support | Notes |
|-----|------------------|-------|
| **C#** | Yes | `ElicitationCapability` with mode validation; `ElicitationCompleteNotificationParams` |
| **Java** | Yes (PR #939 open) | `McpClient.elicitation()` handler; `ElicitRequest` schema builder |
| **Kotlin** | Yes | `elicitation.kt` types + DSL builder; `elicitation.dsl.kt` |
| **Go** | Yes | `ElicitationHandler` in client; security note about never using for sensitive data |
| **Rust** | Yes | `elicit_safe!` macro; enum inference with `schemars` |
| **PHP** | Yes | Full schema definition classes (`ElicitationSchema`, `EnumSchemaDefinition`, etc.) |
| **Swift** | Yes | `Elicitation.RequestSchema` and `Elicitation.Form` capability structs |
| **Ruby** | Yes | `ELICITATION_CREATE = "elicitation/create"` constant |

---

## 5. Active GitHub Issues & PRs

### 5.1 Specification (modelcontextprotocol repo)

| # | Title | Status | Key Detail |
|---|-------|--------|------------|
| #774 | Add Elicitation starting guidance in the User Guide | open | Request for practical implementation examples |
| #2006 | Elicitation client side timeout coordination | open | Tool calls timeout while user fills forms |
| #2188 (PR) | SEP-2188: Add elicitation timeout coordination | open | New `ElicitationPendingNotification` for timeout coordination |
| #2343 (PR) | SEP-2343: Clarify that elicitation requires authorization for remote servers | open | Remote servers MUST implement MCP auth for elicitation |
| #2356 (PR) | SEP-2356: File input support for tools and elicitation | open | Adds `requestedFiles` field to elicitation forms |
| #2651 | `ElicitationCompleteNotification`: intentional omission of `NotificationParams`? | open | Schema inconsistency question |

### 5.2 TypeScript SDK

| # | Title | Status | Key Detail |
|---|-------|--------|------------|
| #662 | Support Zod schema with Elicitation? | open | Feature request for Zod-native elicitation schemas |
| #932 | Elicitation with custom input [SEP-1456] | open | Allow free-form input alongside enums |
| #963 | Simplify attribution of elicitation to a tool call | open | Typed `elicitInput` helper with `relatedRequestId` |
| #1949 (PR) | Allow extra JSON Schema keywords on elicitation primitive schemas | open | Bug fix for `pattern`, `exclusiveMinimum`, `const` |
| #1999 (PR) | Preserve elicit string pattern constraints | open | Ensures `pattern` constraints are preserved |
| #1633 (PR) | [SEP-2356] File input support for tools and elicitation | open | File picker inputs for elicitation |

### 5.3 Python SDK

| # | Title | Status | Key Detail |
|---|-------|--------|------------|
| #1671 | ServerSession methods don't expose progress_callback | open | `elicit_form`, `elicit_url` lack progress callbacks |
| #2041 (PR) | Expose progress_callback in ServerSession methods | open | Fixes #1671 |
| #2217 (PR) | [SEP-2356] File input support for tools and elicitation | open | File picker inputs |
| #2555 (PR) | Make UrlElicitationRequiredError pickle-safe | open | Bug fix for unpickling failure |
| #2322 (PR) | MRTR lowlevel plumbing | open | Multi-round-trip requests with embedded elicitation |

### 5.4 Cross-SDK Themes

1. **SEP-1036 URL Elicitation** — Implemented or in progress across all Tier-1 SDKs.
2. **SEP-2356 File Input** — Active work in spec, TS SDK, Python SDK, C# SDK.
3. **SEP-2188 Timeout Coordination** — Spec-level fix for client-side timeouts during elicitation.
4. **SEP-1686 Tasks + Elicitation** — Task-augmented elicitation patterns in Java, Rust, Python SDKs.
5. **MRTR (Multi Round-Trip Requests)** — csharp-sdk, python-sdk, typescript-sdk — elicitation as part of tool call retry loops.

---

## 6. Implications for FastMCP

### 6.1 What FastMCP Needs to Support

To be standards-compliant with MCP elicitation (2025-11-25 spec):

1. **Capability Declaration**: Server must check if client declared `elicitation` capability (form and/or url modes).
2. **`elicitation/create` Request**: Server must be able to send `elicitation/create` requests with either `mode: "form"` or `mode: "url"`.
3. **Form Mode**: Support `requestedSchema` (JSON Schema) for structured user input.
4. **URL Mode**: Support `url` + `elicitationId` parameters for out-of-band interactions.
5. **Response Handling**: Handle three actions: `accept`, `decline`, `cancel`.
6. **Completion Notification**: Support `notifications/elicitation/complete` for URL mode.
7. **Error Code `-32042`**: Support `URLElicitationRequiredError` for indicating URL elicitation is required before retrying a request.
8. **Security**: Do not request sensitive data via form mode. Always use URL mode for credentials, OAuth, payments.

### 6.2 FastMCP-Specific Considerations

- **Server-side only?** FastMCP is primarily a server framework. It needs to *send* `elicitation/create` requests and handle responses. Client-side handling of `elicitation/create` is less relevant unless FastMCP builds a client component.
- **URL Elicitation Error**: FastMCP tools should be able to raise `UrlElicitationRequiredError` (code `-32042`) so clients know to prompt the user.
- **Schema Validation**: For form mode, FastMCP should validate that schemas only contain primitive types (string, number, boolean, enum) and not nested objects or arrays of objects.
- **State Management**: URL mode requires server-side state to track `elicitationId` and bind it to user identity.
- **Task Integration**: The spec allows elicitation within tasks (experimental). FastMCP may want to support task-augmented elicitation for long-running operations.

### 6.3 Design Recommendations

1. **Two APIs for Server Developers**:
   - `ctx.elicit_form(message, schema)` — For non-sensitive structured input.
   - `ctx.elicit_url(message, url, elicitation_id)` — For sensitive out-of-band interactions.

2. **Error Raising**:
   - Provide `raise UrlElicitationRequiredError(elicitations=[...])` for tools to signal that URL elicitation is required.

3. **Completion Notification Helper**:
   - Provide a helper to send `notifications/elicitation/complete` when the out-of-band flow finishes.

4. **Capability Check**:
   - Auto-check client capabilities before sending elicitation requests and raise a clear error if unsupported.

5. **Schema Helpers**:
   - Provide Pydantic-based schema builders for form mode (similar to Python SDK's `elicit_with_validation`).

---

## 7. References

1. **MCP Specification 2025-11-25 — Elicitation**: https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation
2. **SEP-1036 — URL Mode Elicitation**: https://modelcontextprotocol.io/seps/1036-url-mode-elicitation-for-secure-out-of-band-intera
3. **MCP TypeScript SDK**: https://github.com/modelcontextprotocol/typescript-sdk
4. **MCP Python SDK**: https://github.com/modelcontextprotocol/python-sdk
5. **MCP C# SDK Elicitation Docs**: https://github.com/modelcontextprotocol/csharp-sdk/blob/main/docs/concepts/elicitation/elicitation.md
6. **TypeScript SDK Server Docs**: https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/server.md
7. **TypeScript SDK Client Docs**: https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/client.md
