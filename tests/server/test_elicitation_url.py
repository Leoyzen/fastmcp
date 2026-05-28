import pytest
from mcp.types import ElicitRequestURLParams

from fastmcp.server.elicitation import (
    AcceptedUrlElicitation,
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
