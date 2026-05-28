from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import mcp.types as mcp_types
import pytest
from mcp.shared.exceptions import McpError
from mcp.types import ElicitRequestURLParams

from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.server.elicitation import (
    AcceptedUrlElicitation,
    CancelledElicitation,
    DeclinedElicitation,
    UrlElicitationRequiredError,
)


class TestAcceptedUrlElicitation:
    def test_creation_with_default_action(self):
        elicitation = AcceptedUrlElicitation()
        assert elicitation.action == "accept"

    def test_creation_explicit_action(self):
        elicitation = AcceptedUrlElicitation(action="accept")
        assert elicitation.action == "accept"

    def test_serialization(self):
        elicitation = AcceptedUrlElicitation()
        assert elicitation.model_dump() == {"action": "accept"}

    def test_is_pydantic_base_model(self):
        from pydantic import BaseModel

        assert issubclass(AcceptedUrlElicitation, BaseModel)

    def test_no_data_field(self):
        assert "data" not in AcceptedUrlElicitation.model_fields


class TestUrlElicitationRequiredError:
    def test_is_importable_from_elicitation_module(self):
        assert UrlElicitationRequiredError is not None

    def test_is_exception(self):
        assert issubclass(UrlElicitationRequiredError, Exception)

    def test_can_be_raised_and_caught(self):
        params = ElicitRequestURLParams(message="test", url="https://example.com", elicitationId="id-1")
        with pytest.raises(UrlElicitationRequiredError):
            raise UrlElicitationRequiredError([params])


class TestServerModuleExports:
    def test_accepted_url_elicitation_importable_from_server(self):
        from fastmcp.server import AcceptedUrlElicitation

        assert AcceptedUrlElicitation is not None

    def test_url_elicitation_required_error_importable_from_server(self):
        from fastmcp.server import UrlElicitationRequiredError

        assert UrlElicitationRequiredError is not None


class TestNotExportedFromTopLevel:
    def test_accepted_url_elicitation_not_in_fastmcp_top_level(self):
        import fastmcp

        assert not hasattr(fastmcp, "AcceptedUrlElicitation")

    def test_url_elicitation_required_error_not_in_fastmcp_top_level(self):
        import fastmcp

        assert not hasattr(fastmcp, "UrlElicitationRequiredError")


# =============================================================================
# TDD tests for Context.elicit_url() and _elicit_url_for_task()
# =============================================================================


class TestContextElicitUrl:
    """Tests for Context.elicit_url() method."""

    async def test_valid_https_url_accepted(self):
        """Valid HTTPS URL should pass validation and call session."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(
            return_value=mcp_types.ElicitResult(action="accept", content=None)
        )
        ctx._session = mock_session

        with patch.object(type(ctx), "request_id", new_callable=PropertyMock, return_value="test-req-id"):
            result = await ctx.elicit_url(
                url="https://example.com/oauth",
                message="Please authorize",
            )

        assert isinstance(result, AcceptedUrlElicitation)
        mock_session.elicit_url.assert_awaited_once()

    async def test_javascript_scheme_rejected(self):
        """javascript: scheme should raise ValueError."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        with pytest.raises(ValueError, match="URL scheme should be"):
            await ctx.elicit_url(
                url="javascript:alert(1)",
                message="Bad URL",
            )

    async def test_data_scheme_rejected(self):
        """data: scheme should raise ValueError."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        with pytest.raises(ValueError, match="URL scheme should be"):
            await ctx.elicit_url(
                url="data:text/html,hello",
                message="Bad URL",
            )

    async def test_file_scheme_rejected(self):
        """file: scheme should raise ValueError."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        with pytest.raises(ValueError, match="URL scheme should be"):
            await ctx.elicit_url(
                url="file:///etc/passwd",
                message="Bad URL",
            )

    async def test_missing_scheme_rejected(self):
        """URL without scheme should raise ValueError."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        with pytest.raises(ValueError, match="valid URL"):
            await ctx.elicit_url(
                url="example.com/path",
                message="Bad URL",
            )

    async def test_auto_generates_elicitation_id(self):
        """When elicitation_id is not provided, a UUID should be generated."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(
            return_value=mcp_types.ElicitResult(action="accept", content=None)
        )
        ctx._session = mock_session

        with patch.object(type(ctx), "request_id", new_callable=PropertyMock, return_value="test-req-id"):
            await ctx.elicit_url(
                url="https://example.com",
                message="Test",
            )

        assert mock_session.elicit_url.await_args is not None
        call_kwargs = mock_session.elicit_url.await_args.kwargs
        generated_id = call_kwargs["elicitation_id"]
        assert generated_id is not None
        assert len(generated_id) == 32  # uuid4().hex length
        # Verify it's a valid hex string
        int(generated_id, 16)

    async def test_uses_provided_elicitation_id(self):
        """When elicitation_id is provided, it should be used as-is."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(
            return_value=mcp_types.ElicitResult(action="accept", content=None)
        )
        ctx._session = mock_session

        with patch.object(type(ctx), "request_id", new_callable=PropertyMock, return_value="test-req-id"):
            await ctx.elicit_url(
                url="https://example.com",
                message="Test",
                elicitation_id="my-custom-id",
            )

        assert mock_session.elicit_url.await_args is not None
        call_kwargs = mock_session.elicit_url.await_args.kwargs
        assert call_kwargs["elicitation_id"] == "my-custom-id"

    async def test_foreground_calls_session_elicit_url(self):
        """Foreground mode should call session.elicit_url with correct args."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(
            return_value=mcp_types.ElicitResult(action="accept", content=None)
        )
        ctx._session = mock_session

        with patch.object(type(ctx), "request_id", new_callable=PropertyMock, return_value="req-123"):
            await ctx.elicit_url(
                url="https://example.com/oauth",
                message="Please authorize",
                elicitation_id="elicitation-456",
            )

        mock_session.elicit_url.assert_awaited_once_with(
            message="Please authorize",
            url="https://example.com/oauth",
            elicitation_id="elicitation-456",
            related_request_id="req-123",
        )

    async def test_background_calls_elicit_url_for_task(self):
        """Background mode should delegate to _elicit_url_for_task."""
        mcp = FastMCP("test")
        ctx = Context(mcp, task_id="task-123")

        with patch.object(
            ctx,
            "_elicit_url_for_task",
            new=AsyncMock(
                return_value=mcp_types.ElicitResult(action="accept", content=None)
            ),
        ) as mock_elicit_url_for_task:
            result = await ctx.elicit_url(
                url="https://example.com",
                message="Test",
                elicitation_id="id-1",
            )

        mock_elicit_url_for_task.assert_awaited_once_with(
            message="Test",
            url="https://example.com",
            elicitation_id="id-1",
        )
        assert isinstance(result, AcceptedUrlElicitation)

    async def test_unsupported_client_raises_url_elicitation_required_error(self):
        """McpError with code -32602 should be converted to UrlElicitationRequiredError."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(
            side_effect=McpError(
                mcp_types.ErrorData(
                    code=-32602,
                    message="URL elicitation not supported",
                )
            )
        )
        ctx._session = mock_session

        with patch.object(type(ctx), "request_id", new_callable=PropertyMock, return_value="test-req-id"):
            with pytest.raises(UrlElicitationRequiredError):
                await ctx.elicit_url(
                    url="https://example.com",
                    message="Test",
                )

    async def test_result_mapping_accept(self):
        """accept action should return AcceptedUrlElicitation."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(
            return_value=mcp_types.ElicitResult(action="accept", content=None)
        )
        ctx._session = mock_session

        with patch.object(type(ctx), "request_id", new_callable=PropertyMock, return_value="test-req-id"):
            result = await ctx.elicit_url(
                url="https://example.com",
                message="Test",
            )

        assert isinstance(result, AcceptedUrlElicitation)
        assert result.action == "accept"

    async def test_result_mapping_decline(self):
        """decline action should return DeclinedElicitation."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(
            return_value=mcp_types.ElicitResult(action="decline", content=None)
        )
        ctx._session = mock_session

        with patch.object(type(ctx), "request_id", new_callable=PropertyMock, return_value="test-req-id"):
            result = await ctx.elicit_url(
                url="https://example.com",
                message="Test",
            )

        assert isinstance(result, DeclinedElicitation)

    async def test_result_mapping_cancel(self):
        """cancel action should return CancelledElicitation."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(
            return_value=mcp_types.ElicitResult(action="cancel", content=None)
        )
        ctx._session = mock_session

        with patch.object(type(ctx), "request_id", new_callable=PropertyMock, return_value="test-req-id"):
            result = await ctx.elicit_url(
                url="https://example.com",
                message="Test",
            )

        assert isinstance(result, CancelledElicitation)

    async def test_unexpected_action_raises_value_error(self):
        """Unexpected action should raise ValueError."""
        mcp = FastMCP("test")
        ctx = Context(mcp)

        mock_result = MagicMock()
        mock_result.action = "unknown"
        mock_result.content = None

        mock_session = MagicMock()
        mock_session.elicit_url = AsyncMock(return_value=mock_result)
        ctx._session = mock_session

        with patch.object(type(ctx), "request_id", new_callable=PropertyMock, return_value="test-req-id"):
            with pytest.raises(ValueError, match="Unexpected elicitation action"):
                await ctx.elicit_url(
                    url="https://example.com",
                    message="Test",
                )


class TestElicitUrlForTask:
    """Tests for Context._elicit_url_for_task() helper."""

    async def test_raises_when_not_background_task(self):
        """_elicit_url_for_task should raise when not in background task."""
        mcp = FastMCP("test")
        ctx = Context(mcp)  # No task_id

        with pytest.raises(RuntimeError, match="background task context"):
            await ctx._elicit_url_for_task(
                message="Test",
                url="https://example.com",
                elicitation_id="id-1",
            )
