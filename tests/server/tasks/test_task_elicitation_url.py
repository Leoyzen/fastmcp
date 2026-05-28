"""Tests for background task URL-mode elicitation (SEP-1686).

TDD tests covering:
- elicit_url_for_task() stores correct Redis format with mode discriminator
- elicit_for_task() stores mode: "form" in Redis
- relay_elicitation() branches correctly on mode
- Old Redis keys (no mode) still work for form mode (backward compatibility)
- Full background task URL elicitation E2E
"""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import mcp.types as mcp_types
import pytest

from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.elicitation import ElicitResult
from fastmcp.server.context import Context
from fastmcp.server.elicitation import (
    AcceptedUrlElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)
from fastmcp.server.tasks.elicitation import (
    _elicit_keys,
    elicit_for_task,
    elicit_url_for_task,
    relay_elicitation,
)

# =============================================================================
# Unit tests: Redis storage format
# =============================================================================


class TestElicitForTaskStorageFormat:
    """Unit tests for elicit_for_task() Redis storage format."""

    async def test_stores_mode_form_in_redis(self):
        """elicit_for_task should store mode: 'form' in the Redis request dict."""
        mcp = FastMCP("storage-form")
        mcp._docket = MagicMock()
        mock_redis = AsyncMock()
        mcp._docket.redis = MagicMock()
        mcp._docket.redis.return_value.__aenter__ = AsyncMock(
            return_value=mock_redis
        )
        mcp._docket.redis.return_value.__aexit__ = AsyncMock(return_value=False)
        mcp._docket.key = lambda k: k

        schema = {"type": "object", "properties": {"name": {"type": "string"}}}

        with patch(
            "fastmcp.server.tasks.elicitation.get_task_context"
        ) as mock_get_ctx:
            mock_ctx = MagicMock()
            mock_ctx.task_scope = "test-scope"
            mock_get_ctx.return_value = mock_ctx

            with patch(
                "fastmcp.server.tasks.elicitation.get_task_session_id",
                return_value="session-123",
            ):
                with patch(
                    "fastmcp.server.tasks.elicitation.push_notification",
                    new_callable=AsyncMock,
                ):
                    # Cancel immediately to avoid blocking on BLPOP
                    with patch.object(
                        mock_redis,
                        "blpop",
                        new_callable=AsyncMock,
                        return_value=None,
                    ):
                        result = await elicit_for_task(
                            task_id="task-123",
                            session=None,
                            message="Enter name",
                            schema=schema,
                            fastmcp=mcp,
                        )

        # Verify the stored request includes mode: "form"
        set_calls = [
            call
            for call in mock_redis.set.call_args_list
            if call.args[0].endswith(":request")
        ]
        assert len(set_calls) == 1
        stored_data = json.loads(set_calls[0].args[1])
        assert stored_data["mode"] == "form"
        assert stored_data["message"] == "Enter name"
        assert stored_data["schema"] == schema
        assert "request_id" in stored_data
        # Should NOT have url or elicitation_id keys
        assert "url" not in stored_data
        assert "elicitation_id" not in stored_data


class TestElicitUrlForTaskStorageFormat:
    """Unit tests for elicit_url_for_task() Redis storage format."""

    async def test_stores_mode_url_in_redis(self):
        """elicit_url_for_task should store mode: 'url' and url/elicitation_id."""
        mcp = FastMCP("storage-url")
        mcp._docket = MagicMock()
        mock_redis = AsyncMock()
        mcp._docket.redis = MagicMock()
        mcp._docket.redis.return_value.__aenter__ = AsyncMock(
            return_value=mock_redis
        )
        mcp._docket.redis.return_value.__aexit__ = AsyncMock(return_value=False)
        mcp._docket.key = lambda k: k

        with patch(
            "fastmcp.server.tasks.elicitation.get_task_context"
        ) as mock_get_ctx:
            mock_ctx = MagicMock()
            mock_ctx.task_scope = "test-scope"
            mock_get_ctx.return_value = mock_ctx

            with patch(
                "fastmcp.server.tasks.elicitation.get_task_session_id",
                return_value="session-123",
            ):
                with patch(
                    "fastmcp.server.tasks.elicitation.push_notification",
                    new_callable=AsyncMock,
                ):
                    with patch.object(
                        mock_redis,
                        "blpop",
                        new_callable=AsyncMock,
                        return_value=None,
                    ):
                        result = await elicit_url_for_task(
                            task_id="task-123",
                            session=None,
                            url="https://example.com/form",
                            message="Please fill out the form",
                            elicitation_id="abc123",
                            fastmcp=mcp,
                        )

        # Verify the stored request includes mode: "url"
        set_calls = [
            call
            for call in mock_redis.set.call_args_list
            if call.args[0].endswith(":request")
        ]
        assert len(set_calls) == 1
        stored_data = json.loads(set_calls[0].args[1])
        assert stored_data["mode"] == "url"
        assert stored_data["message"] == "Please fill out the form"
        assert stored_data["url"] == "https://example.com/form"
        assert stored_data["elicitation_id"] == "abc123"
        assert "request_id" in stored_data
        # Should NOT have schema key
        assert "schema" not in stored_data

    async def test_notification_includes_url_metadata(self):
        """elicit_url_for_task notification should include url mode metadata."""
        mcp = FastMCP("notification-url")
        mcp._docket = MagicMock()
        mock_redis = AsyncMock()
        mcp._docket.redis = MagicMock()
        mcp._docket.redis.return_value.__aenter__ = AsyncMock(
            return_value=mock_redis
        )
        mcp._docket.redis.return_value.__aexit__ = AsyncMock(return_value=False)
        mcp._docket.key = lambda k: k

        captured_notification: dict[str, Any] | None = None

        async def capture_notification(session_id, notification, docket):
            nonlocal captured_notification
            captured_notification = notification

        with patch(
            "fastmcp.server.tasks.elicitation.get_task_context"
        ) as mock_get_ctx:
            mock_ctx = MagicMock()
            mock_ctx.task_scope = "test-scope"
            mock_get_ctx.return_value = mock_ctx

            with patch(
                "fastmcp.server.tasks.elicitation.get_task_session_id",
                return_value="session-123",
            ):
                with patch(
                    "fastmcp.server.tasks.elicitation.push_notification",
                    side_effect=capture_notification,
                ):
                    with patch.object(
                        mock_redis,
                        "blpop",
                        new_callable=AsyncMock,
                        return_value=None,
                    ):
                        await elicit_url_for_task(
                            task_id="task-123",
                            session=None,
                            url="https://example.com/form",
                            message="Please fill out the form",
                            elicitation_id="abc123",
                            fastmcp=mcp,
                        )

        assert captured_notification is not None
        meta = captured_notification.get("_meta", {})
        related_task = meta.get("io.modelcontextprotocol/related-task", {})
        elicitation = related_task.get("elicitation")
        assert isinstance(elicitation, dict)
        assert elicitation.get("mode") == "url"
        assert elicitation.get("url") == "https://example.com/form"
        assert elicitation.get("elicitationId") == "abc123"
        assert elicitation.get("message") == "Please fill out the form"
        assert "requestId" in elicitation

    async def test_raises_when_no_docket(self):
        """elicit_url_for_task should raise RuntimeError when Docket is unavailable."""
        mcp = FastMCP("no-docket")
        mcp._docket = None

        with pytest.raises(RuntimeError, match="Docket"):
            await elicit_url_for_task(
                task_id="task-123",
                session=None,
                url="https://example.com",
                message="Test",
                elicitation_id="abc",
                fastmcp=mcp,
            )

    async def test_raises_when_no_task_context(self):
        """elicit_url_for_task should raise RuntimeError outside task context."""
        mcp = FastMCP("no-context")
        mcp._docket = MagicMock()

        with patch(
            "fastmcp.server.tasks.elicitation.get_task_context",
            return_value=None,
        ):
            with pytest.raises(RuntimeError, match="task scope"):
                await elicit_url_for_task(
                    task_id="task-123",
                    session=None,
                    url="https://example.com",
                    message="Test",
                    elicitation_id="abc",
                    fastmcp=mcp,
                )


# =============================================================================
# Unit tests: relay_elicitation() mode branching
# =============================================================================


class TestRelayElicitationModeBranching:
    """Unit tests for relay_elicitation() branching on mode discriminator."""

    async def test_relay_url_mode_calls_elicit_url(self):
        """relay_elicitation should call session.elicit_url() for mode: 'url'."""
        mcp = FastMCP("relay-url")
        captured_calls: list[dict[str, Any]] = []

        class MockSession:
            async def elicit_url(self, **kwargs: Any) -> mcp_types.ElicitResult:
                captured_calls.append(kwargs)
                return mcp_types.ElicitResult(action="accept", content=None)

        mock_session = MockSession()

        elicitation = {
            "mode": "url",
            "message": "Please fill out the form",
            "url": "https://example.com/form",
            "elicitationId": "abc123",
        }

        mcp._docket = MagicMock()

        class MockRedis:
            async def get(self, key: str) -> bytes | None:
                return b"waiting"

            async def lpush(self, key: str, value: str) -> None:
                pass

            async def expire(self, key: str, seconds: int) -> None:
                pass

            async def set(self, key: str, value: str, **kwargs: Any) -> None:
                pass

        mock_redis = MockRedis()
        mcp._docket.redis = MagicMock()
        mcp._docket.redis.return_value.__aenter__ = AsyncMock(
            return_value=mock_redis
        )
        mcp._docket.redis.return_value.__aexit__ = AsyncMock(return_value=False)
        mcp._docket.key = lambda k: k

        await relay_elicitation(
            session=mock_session,  # type: ignore
            task_scope="test-scope",
            task_id="task-123",
            elicitation=elicitation,
            fastmcp=mcp,
        )

        assert len(captured_calls) == 1
        assert captured_calls[0] == {
            "message": "Please fill out the form",
            "url": "https://example.com/form",
            "elicitation_id": "abc123",
        }

    async def test_relay_form_mode_calls_elicit(self):
        """relay_elicitation should call session.elicit() for mode: 'form'."""
        mcp = FastMCP("relay-form")
        captured_calls: list[dict[str, Any]] = []

        class MockSession:
            async def elicit(self, **kwargs: Any) -> mcp_types.ElicitResult:
                captured_calls.append(kwargs)
                return mcp_types.ElicitResult(action="accept", content=None)

        mock_session = MockSession()

        elicitation = {
            "mode": "form",
            "message": "Enter value",
            "requestedSchema": {"type": "string"},
        }

        mcp._docket = MagicMock()

        class MockRedis:
            async def get(self, key: str) -> bytes | None:
                return b"waiting"

            async def lpush(self, key: str, value: str) -> None:
                pass

            async def expire(self, key: str, seconds: int) -> None:
                pass

            async def set(self, key: str, value: str, **kwargs: Any) -> None:
                pass

        mock_redis = MockRedis()
        mcp._docket.redis = MagicMock()
        mcp._docket.redis.return_value.__aenter__ = AsyncMock(
            return_value=mock_redis
        )
        mcp._docket.redis.return_value.__aexit__ = AsyncMock(return_value=False)
        mcp._docket.key = lambda k: k

        await relay_elicitation(
            session=mock_session,  # type: ignore
            task_scope="test-scope",
            task_id="task-123",
            elicitation=elicitation,
            fastmcp=mcp,
        )

        assert len(captured_calls) == 1
        assert captured_calls[0] == {
            "message": "Enter value",
            "requestedSchema": {"type": "string"},
        }

    async def test_relay_no_mode_falls_through_to_form_mode(self):
        """Old Redis keys without mode should fall through to form mode."""
        mcp = FastMCP("relay-compat")
        captured_calls: list[dict[str, Any]] = []

        class MockSession:
            async def elicit(self, **kwargs: Any) -> mcp_types.ElicitResult:
                captured_calls.append(kwargs)
                return mcp_types.ElicitResult(action="accept", content=None)

        mock_session = MockSession()

        # Old format: no "mode" key, only "message" and "requestedSchema"
        elicitation = {
            "message": "Enter value",
            "requestedSchema": {"type": "string"},
        }

        mcp._docket = MagicMock()

        class MockRedis:
            async def get(self, key: str) -> bytes | None:
                return b"waiting"

            async def lpush(self, key: str, value: str) -> None:
                pass

            async def expire(self, key: str, seconds: int) -> None:
                pass

            async def set(self, key: str, value: str, **kwargs: Any) -> None:
                pass

        mock_redis = MockRedis()
        mcp._docket.redis = MagicMock()
        mcp._docket.redis.return_value.__aenter__ = AsyncMock(
            return_value=mock_redis
        )
        mcp._docket.redis.return_value.__aexit__ = AsyncMock(return_value=False)
        mcp._docket.key = lambda k: k

        await relay_elicitation(
            session=mock_session,  # type: ignore
            task_scope="test-scope",
            task_id="task-123",
            elicitation=elicitation,
            fastmcp=mcp,
        )

        assert len(captured_calls) == 1
        assert captured_calls[0] == {
            "message": "Enter value",
            "requestedSchema": {"type": "string"},
        }

    async def test_relay_url_mode_pushes_cancel_on_error(self):
        """relay_elicitation should push cancel when elicit_url raises."""
        mcp = FastMCP("relay-url-error")

        class MockSession:
            pass

        mock_session = MockSession()
        mock_elicit_url = AsyncMock(
            side_effect=ConnectionError("Client disconnected")
        )
        mock_session.elicit_url = mock_elicit_url  # type: ignore

        elicitation = {
            "mode": "url",
            "message": "Form",
            "url": "https://example.com",
            "elicitationId": "abc",
        }

        mcp._docket = MagicMock()
        mock_redis = AsyncMock()
        # Status must be "waiting" for handle_task_input to accept the response
        mock_redis.get = AsyncMock(return_value=b"waiting")
        mcp._docket.redis = MagicMock()
        mcp._docket.redis.return_value.__aenter__ = AsyncMock(
            return_value=mock_redis
        )
        mcp._docket.redis.return_value.__aexit__ = AsyncMock(return_value=False)
        mcp._docket.key = lambda k: k

        await relay_elicitation(
            session=mock_session,  # type: ignore
            task_scope="test-scope",
            task_id="task-123",
            elicitation=elicitation,
            fastmcp=mcp,
        )

        # Should have pushed cancel response
        lpush_calls = mock_redis.lpush.call_args_list
        assert len(lpush_calls) == 1
        response = json.loads(lpush_calls[0].args[1])
        assert response["action"] == "cancel"
        assert response["content"] is None


# =============================================================================
# E2E tests: Full background task URL elicitation
# =============================================================================


class TestUrlElicitationRelayE2E:
    """E2E tests for URL-mode elicitation flowing through the standard MCP protocol."""

    async def test_accept_via_elicitation_handler_url_mode(self):
        """Tool elicits URL, client handler accepts, tool gets AcceptedUrlElicitation."""
        mcp = FastMCP("relay-url-accept")

        @mcp.tool(task=True)
        async def ask_form(ctx: Context) -> str:
            result = await ctx.elicit_url(
                "https://example.com/form", "Please fill out the form"
            )
            if isinstance(result, AcceptedUrlElicitation):
                return "Form completed"
            return "Not completed"

        async def handler(message, response_type, params, ctx):
            assert message == "Please fill out the form"
            return ElicitResult(action="accept")

        async with Client(mcp, elicitation_handler=handler) as client:
            task = await client.call_tool("ask_form", {}, task=True)
            result = await task.result()
            assert result.data == "Form completed"

    async def test_decline_via_elicitation_handler_url_mode(self):
        """Tool elicits URL, client handler declines, tool gets DeclinedElicitation."""
        mcp = FastMCP("relay-url-decline")

        @mcp.tool(task=True)
        async def optional_form(ctx: Context) -> str:
            result = await ctx.elicit_url(
                "https://example.com/optional", "Optional form?"
            )
            if isinstance(result, DeclinedElicitation):
                return "User declined"
            if isinstance(result, AcceptedUrlElicitation):
                return "Accepted"
            return "Other"

        async def handler(message, response_type, params, ctx):
            return ElicitResult(action="decline")

        async with Client(mcp, elicitation_handler=handler) as client:
            task = await client.call_tool("optional_form", {}, task=True)
            result = await task.result()
            assert result.data == "User declined"

    async def test_cancel_via_elicitation_handler_url_mode(self):
        """Tool elicits URL, client handler cancels, tool gets CancelledElicitation."""
        mcp = FastMCP("relay-url-cancel")

        @mcp.tool(task=True)
        async def cancellable_form(ctx: Context) -> str:
            result = await ctx.elicit_url(
                "https://example.com/form", "Fill form?"
            )
            if isinstance(result, CancelledElicitation):
                return "Cancelled"
            return "Not cancelled"

        async def handler(message, response_type, params, ctx):
            return ElicitResult(action="cancel")

        async with Client(mcp, elicitation_handler=handler) as client:
            task = await client.call_tool("cancellable_form", {}, task=True)
            result = await task.result()
            assert result.data == "Cancelled"

    async def test_no_elicitation_handler_returns_cancel_url_mode(self):
        """Without elicitation_handler, URL relay fails and task gets cancel."""
        mcp = FastMCP("relay-url-no-handler")

        @mcp.tool(task=True)
        async def needs_url(ctx: Context) -> str:
            result = await ctx.elicit_url(
                "https://example.com/form", "Open form?"
            )
            if isinstance(result, CancelledElicitation):
                return "Cancelled as expected"
            if isinstance(result, AcceptedUrlElicitation):
                return "Accepted"
            return "Other"

        async with Client(mcp) as client:
            task = await client.call_tool("needs_url", {}, task=True)
            result = await asyncio.wait_for(task.result(), timeout=15.0)
            assert result.data == "Cancelled as expected"

    async def test_notification_metadata_includes_url_mode(self):
        """URL elicitation notification metadata includes mode discriminator."""
        from fastmcp.client.messages import MessageHandler

        class NotificationCaptureHandler(MessageHandler):
            """Capture server notifications for test assertions."""

            def __init__(self) -> None:
                super().__init__()
                self.notifications: list[mcp_types.ServerNotification] = []

            async def on_notification(
                self, message: mcp_types.ServerNotification
            ) -> None:
                self.notifications.append(message)

            def for_method(
                self, method: str
            ) -> list[mcp_types.ServerNotification]:
                return [
                    notification
                    for notification in self.notifications
                    if notification.root.method == method
                ]

        mcp = FastMCP("url-notification-metadata")
        notification_handler = NotificationCaptureHandler()

        @mcp.tool(task=True)
        async def url_tool(ctx: Context) -> str:
            result = await ctx.elicit_url(
                "https://example.com/survey", "Open this URL"
            )
            if isinstance(result, AcceptedUrlElicitation):
                return "Done"
            return "Not done"

        async def elicitation_handler(message, response_type, params, ctx):
            return ElicitResult(action="accept")

        async with Client(
            mcp,
            message_handler=notification_handler,
            elicitation_handler=elicitation_handler,
        ) as client:
            task = await client.call_tool("url_tool", {}, task=True)
            await task.wait(timeout=10.0)
            result = await task.result()
            assert result.data == "Done"

            # Find the input_required notification
            notification: mcp_types.ServerNotification | None = None
            candidates = notification_handler.for_method(
                "notifications/tasks/status"
            )
            for candidate in reversed(candidates):
                candidate_meta = getattr(candidate.root, "_meta", None)
                related_task = (
                    candidate_meta.get("io.modelcontextprotocol/related-task")
                    if isinstance(candidate_meta, dict)
                    else None
                )
                if (
                    isinstance(related_task, dict)
                    and related_task.get("status") == "input_required"
                ):
                    notification = candidate
                    break

            assert notification is not None
            task_meta = getattr(notification.root, "_meta", None)
            assert isinstance(task_meta, dict)

            related_task = task_meta.get("io.modelcontextprotocol/related-task")
            assert isinstance(related_task, dict)

            elicitation = related_task.get("elicitation")
            assert isinstance(elicitation, dict)
            assert elicitation.get("mode") == "url"
            assert elicitation.get("url") == "https://example.com/survey"
            assert isinstance(elicitation.get("elicitationId"), str)
            assert elicitation.get("message") == "Open this URL"
