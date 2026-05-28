import importlib

from fastmcp import _install_hints

try:
    from .context import Context
    from .server import FastMCP, create_proxy
except ImportError as exc:
    raise ImportError(_install_hints.SERVER_SUPPORT) from exc


def __getattr__(name: str) -> object:
    if name == "dependencies":
        return importlib.import_module("fastmcp.server.dependencies")
    if name in ("AcceptedUrlElicitation", "UrlElicitationRequiredError"):
        mod = importlib.import_module("fastmcp.server.elicitation")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AcceptedUrlElicitation",
    "Context",
    "FastMCP",
    "UrlElicitationRequiredError",
    "create_proxy",
]
