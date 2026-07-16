import contextlib
import sys
from collections.abc import Callable
from typing import Any, TypeVar

from integrations.router import (
    execute_knowledge_query,
    execute_news_lookup,
    execute_rag_chat,
    execute_search_query,
    execute_weather_lookup,
)


T = TypeVar("T")


try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _run_with_stderr_logs(action: Callable[[], T]) -> T:
    with contextlib.redirect_stdout(sys.stderr):
        return action()


def _register_tools(mcp: Any) -> None:
    @mcp.tool()
    def weather(city: str = "Delhi") -> str:
        """Get current weather for a city."""
        _log("=" * 60)
        _log("[MCP-OFFICIAL] Tool called: weather")
        _log(f"[MCP-OFFICIAL]   city='{city}'")
        _log("=" * 60)
        result = _run_with_stderr_logs(lambda: execute_weather_lookup(city))
        return result.response

    @mcp.tool()
    def news(topic: str = "india") -> str:
        """Get latest news for a topic."""
        _log("=" * 60)
        _log("[MCP-OFFICIAL] Tool called: news")
        _log(f"[MCP-OFFICIAL]   topic='{topic}'")
        _log("=" * 60)
        result = _run_with_stderr_logs(lambda: execute_news_lookup(topic))
        return result.response

    @mcp.tool()
    def search(query: str) -> str:
        """Search the web using the configured SearXNG integration."""
        _log("=" * 60)
        _log("[MCP-OFFICIAL] Tool called: search")
        _log(f"[MCP-OFFICIAL]   query='{query}'")
        _log("=" * 60)
        result = _run_with_stderr_logs(lambda: execute_search_query(query))
        return result.response

    @mcp.tool()
    def knowledge(query: str) -> str:
        """Query the local knowledge base, with web fallback."""
        _log("=" * 60)
        _log("[MCP-OFFICIAL] Tool called: knowledge")
        _log(f"[MCP-OFFICIAL]   query='{query}'")
        _log("=" * 60)
        result = _run_with_stderr_logs(lambda: execute_knowledge_query(query))
        return result.response

    @mcp.tool()
    def rag(query: str, language: str = "en") -> str:
        """Ask the full RAG chat assistant."""
        _log("=" * 60)
        _log("[MCP-OFFICIAL] Tool called: rag")
        _log(f"[MCP-OFFICIAL]   query='{query}'")
        _log(f"[MCP-OFFICIAL]   language='{language}'")
        _log("=" * 60)
        result = _run_with_stderr_logs(lambda: execute_rag_chat(query, language))
        return result.response


def create_mcp_server() -> Any | None:
    if FastMCP is None:
        return None

    mcp = FastMCP(
        "MyAgent",
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    )
    _register_tools(mcp)
    return mcp


def create_streamable_http_app() -> Any | None:
    mcp = create_mcp_server()
    if mcp is None:
        return None
    return mcp.streamable_http_app()


def run_mcp_server(transport: str = "stdio") -> None:
    mcp = create_mcp_server()
    if mcp is None:
        raise SystemExit(
            "The official MCP SDK is not installed. "
            "Install backend requirements first: pip install -r requirements.txt"
        )

    _log("=" * 60)
    _log("[MCP-OFFICIAL] Starting MyAgent MCP server")
    _log(f"[MCP-OFFICIAL]   transport={transport}")
    _log("[MCP-OFFICIAL]   tools=weather, news, search, knowledge, rag")
    _log("=" * 60)
    mcp.run(transport=transport)
