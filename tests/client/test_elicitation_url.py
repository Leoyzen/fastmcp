from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.types import ElicitRequestFormParams, ElicitRequestURLParams

from fastmcp.client.elicitation import ElicitResult, create_elicitation_callback


@pytest.fixture
def mock_context() -> Any:
    """Create a mock RequestContext."""
    return MagicMock()


class TestURLModeElicitation:
    async def test_url_mode_passes_url_marker(self, mock_context: Any) -> None:
        """URL mode passes 'url' as response_type."""
        handler = AsyncMock(return_value=ElicitResult(action="accept"))
        callback = create_elicitation_callback(handler)

        params = ElicitRequestURLParams(
            message="Visit this URL",
            url="https://example.com",
            elicitationId="test-elicit-1",
        )

        await callback(mock_context, params)

        assert handler.call_count == 1
        call_args = handler.call_args
        assert call_args[0][1] == "url"  # response_type is second positional arg

    async def test_deprecated_empty_schema_form_passes_none(
        self, mock_context: Any
    ) -> None:
        """Deprecated empty-schema form mode passes None."""
        handler = AsyncMock(return_value=ElicitResult(action="accept"))
        callback = create_elicitation_callback(handler)

        params = ElicitRequestFormParams(
            message="Confirm?",
            requestedSchema={"type": "object", "properties": {}},
        )

        await callback(mock_context, params)

        assert handler.call_count == 1
        call_args = handler.call_args
        assert call_args[0][1] is None

    async def test_normal_form_mode_passes_parsed_type(self, mock_context: Any) -> None:
        """Normal form mode passes parsed type from json_schema_to_type."""
        handler = AsyncMock(
            return_value=ElicitResult(action="accept", content={"value": 42})
        )
        callback = create_elicitation_callback(handler)

        params = ElicitRequestFormParams(
            message="What's your age?",
            requestedSchema={
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
            },
        )

        await callback(mock_context, params)

        assert handler.call_count == 1
        call_args = handler.call_args
        response_type = call_args[0][1]
        # response_type should be a dynamically generated type, not "url" or None
        assert response_type is not None
        assert response_type != "url"
        assert isinstance(response_type, type)

    async def test_handler_receives_url_params(self, mock_context: Any) -> None:
        """Handler receives correct param types for URL mode."""
        handler = AsyncMock(return_value=ElicitResult(action="accept"))
        callback = create_elicitation_callback(handler)

        params = ElicitRequestURLParams(
            message="Visit https://example.com",
            url="https://example.com",
            elicitationId="test-elicit-2",
        )

        await callback(mock_context, params)

        call_args = handler.call_args
        assert call_args[0][0] == "Visit https://example.com"  # message
        assert call_args[0][1] == "url"  # response_type
        assert isinstance(call_args[0][2], ElicitRequestURLParams)  # params
        assert call_args[0][3] is mock_context  # context

    async def test_handler_receives_form_params(self, mock_context: Any) -> None:
        """Handler receives correct param types for form mode."""
        handler = AsyncMock(return_value=ElicitResult(action="accept"))
        callback = create_elicitation_callback(handler)

        params = ElicitRequestFormParams(
            message="Confirm?",
            requestedSchema={"type": "object", "properties": {}},
        )

        await callback(mock_context, params)

        call_args = handler.call_args
        assert call_args[0][0] == "Confirm?"  # message
        assert call_args[0][1] is None  # response_type
        assert isinstance(call_args[0][2], ElicitRequestFormParams)  # params
        assert call_args[0][3] is mock_context  # context
