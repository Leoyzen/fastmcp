from unittest.mock import AsyncMock, MagicMock, patch

import mcp.types
import pytest
from mcp.types import ElicitRequestFormParams, ElicitRequestURLParams

from fastmcp.client.elicitation import ElicitResult
from fastmcp.server.providers.proxy import (
    StatefulProxyClient,
    _make_restoring_handler,
    default_proxy_elicitation_handler,
)


class TestDefaultProxyElicitationHandlerURLMode:
    """TDD tests for URL mode elicitation forwarding via proxy."""

    async def test_url_mode_calls_session_elicit_url(self):
        """When params is ElicitRequestURLParams, call ctx.session.elicit_url()."""
        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(
            return_value=mcp.types.ElicitResult(action="accept", content=None)
        )
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session
        mock_ctx.request_id = "proxy-req-123"

        with patch(
            "fastmcp.server.providers.proxy.get_context", return_value=mock_ctx
        ):
            params = ElicitRequestURLParams(
                message="Authorize at https://example.com",
                url="https://example.com/oauth",
                elicitationId="elicit-456",
            )
            result = await default_proxy_elicitation_handler(
                message="Authorize at https://example.com",
                response_type=str,
                params=params,
                context=MagicMock(),
            )

        mock_session.elicit_url.assert_awaited_once_with(
            message="Authorize at https://example.com",
            url="https://example.com/oauth",
            elicitation_id="elicit-456",
            related_request_id="proxy-req-123",
        )
        assert isinstance(result, ElicitResult)
        assert result.action == "accept"

    async def test_url_mode_returns_decline(self):
        """Decline responses from elicit_url are forwarded correctly."""
        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(
            return_value=mcp.types.ElicitResult(action="decline", content=None)
        )
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session
        mock_ctx.request_id = "proxy-req-decline"

        with patch(
            "fastmcp.server.providers.proxy.get_context", return_value=mock_ctx
        ):
            params = ElicitRequestURLParams(
                message="Visit this URL",
                url="https://example.com",
                elicitationId="elicit-decline",
            )
            result = await default_proxy_elicitation_handler(
                message="Visit this URL",
                response_type=str,
                params=params,
                context=MagicMock(),
            )

        assert isinstance(result, ElicitResult)
        assert result.action == "decline"


class TestDefaultProxyElicitationHandlerFormMode:
    """Regression tests for form mode elicitation forwarding via proxy."""

    async def test_form_mode_calls_session_elicit(self):
        """When params is ElicitRequestFormParams, call ctx.session.elicit()."""
        mock_session = MagicMock()
        mock_session.elicit = AsyncMock(
            return_value=mcp.types.ElicitResult(
                action="accept", content={"name": "Alice"}
            )
        )
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session
        mock_ctx.request_id = "proxy-req-789"

        with patch(
            "fastmcp.server.providers.proxy.get_context", return_value=mock_ctx
        ):
            params = ElicitRequestFormParams(
                message="What is your name?",
                requestedSchema={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            )
            result = await default_proxy_elicitation_handler(
                message="What is your name?",
                response_type=dict,
                params=params,
                context=MagicMock(),
            )

        mock_session.elicit.assert_awaited_once_with(
            message="What is your name?",
            requestedSchema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            related_request_id="proxy-req-789",
        )
        assert isinstance(result, ElicitResult)
        assert result.action == "accept"
        assert result.content == {"name": "Alice"}

    async def test_form_mode_passes_related_request_id(self):
        """related_request_id from ctx.request_id is forwarded for form mode."""
        mock_session = MagicMock()
        mock_session.elicit = AsyncMock(
            return_value=mcp.types.ElicitResult(action="accept", content=None)
        )
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session
        mock_ctx.request_id = "req-id-form-mode"

        with patch(
            "fastmcp.server.providers.proxy.get_context", return_value=mock_ctx
        ):
            params = ElicitRequestFormParams(
                message="Confirm?",
                requestedSchema={"type": "object", "properties": {}},
            )
            await default_proxy_elicitation_handler(
                message="Confirm?",
                response_type=dict,
                params=params,
                context=MagicMock(),
            )

        call_kwargs = mock_session.elicit.await_args.kwargs  # type: ignore[union-attr]  # ty:ignore[unresolved-attribute]
        assert call_kwargs["related_request_id"] == "req-id-form-mode"


class TestStatefulProxyClientRestoringHandler:
    """Tests that StatefulProxyClient restoring wrapper works with URL mode."""

    async def test_restoring_handler_routes_url_mode(self):
        """Wrapped handler via _make_restoring_handler routes URL params to elicit_url."""
        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(
            return_value=mcp.types.ElicitResult(action="accept", content=None)
        )
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session
        mock_ctx.request_id = "proxy-req-abc"

        rc_ref = [MagicMock()]

        with patch(
            "fastmcp.server.providers.proxy.get_context", return_value=mock_ctx
        ):
            with patch(
                "fastmcp.server.providers.proxy._restore_request_context"
            ) as mock_restore:
                wrapped = _make_restoring_handler(
                    default_proxy_elicitation_handler, rc_ref
                )
                params = ElicitRequestURLParams(
                    message="Visit this URL",
                    url="https://example.com",
                    elicitationId="elicit-xyz",
                )
                result = await wrapped(
                    message="Visit this URL",
                    response_type=str,
                    params=params,
                    context=MagicMock(),
                )

        mock_restore.assert_called_once_with(rc_ref)
        mock_session.elicit_url.assert_awaited_once_with(
            message="Visit this URL",
            url="https://example.com",
            elicitation_id="elicit-xyz",
            related_request_id="proxy-req-abc",
        )
        assert isinstance(result, ElicitResult)
        assert result.action == "accept"

    async def test_stateful_proxy_client_wraps_elicitation_handler(self):
        """StatefulProxyClient wraps default_proxy_elicitation_handler on init."""
        # Use a simple FastMCP server as transport so StatefulProxyClient
        # can initialize without network setup.
        from fastmcp import FastMCP

        backend = FastMCP("backend")
        client = StatefulProxyClient(backend)

        assert "elicitation_handler" in client._proxy_restoring_handler_keys
        assert client._session_kwargs["elicitation_callback"] is not None
