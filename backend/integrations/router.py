from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class IntegrationResult:
    integration: str
    response: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolDecision:
    tool_name: str
    params: dict[str, str]
    reason: str
    matched_keyword: str | None = None


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    keywords: tuple[str, ...]
    build_params: Callable[[str, str], dict[str, str]]
    execute: Callable[[dict[str, str]], IntegrationResult]
    default_tool: bool = False


def _print_header(title: str) -> None:
    print("=" * 60)
    print(f"[INTEGRATION] {title}")
    print("=" * 60)


def _print_footer(title: str, result: str) -> None:
    print(f"[INTEGRATION] {title} completed")
    print(f"[INTEGRATION]   Response length: {len(result) if result else 0} chars")
    print(f"[INTEGRATION]   Response preview: {result[:120] if result else 'None'}...")
    print("=" * 60)


def _extract_weather_city(query: str) -> str:
    city = (
        query.lower()
        .replace("weather", "")
        .replace("in", "")
        .strip()
    )
    return city or "Delhi"


def _extract_news_topic(query: str) -> str:
    topic = (
        query.lower()
        .replace("latest", "")
        .replace("news", "")
        .replace("about", "")
        .strip()
    )
    return topic or "india"


def _weather_params(query: str, language: str) -> dict[str, str]:
    return {
        "city": _extract_weather_city(query),
        "language": language,
    }


def _news_params(query: str, language: str) -> dict[str, str]:
    return {
        "topic": _extract_news_topic(query),
        "language": language,
    }


def _rag_params(query: str, language: str) -> dict[str, str]:
    return {
        "query": query,
        "language": language,
    }


def _search_params(query: str, language: str) -> dict[str, str]:
    return {
        "query": query,
        "language": language,
    }


def _knowledge_params(query: str, language: str) -> dict[str, str]:
    return {
        "query": query,
        "language": language,
    }


def _execute_weather_tool(params: dict[str, str]) -> IntegrationResult:
    return execute_weather_lookup(params.get("city", "Delhi"))


def _execute_news_tool(params: dict[str, str]) -> IntegrationResult:
    return execute_news_lookup(params.get("topic", "india"))


def _execute_rag_tool(params: dict[str, str]) -> IntegrationResult:
    return execute_rag_chat(
        params.get("query", ""),
        params.get("language", "en"),
    )


def _execute_search_tool(params: dict[str, str]) -> IntegrationResult:
    return execute_search_query(params.get("query", ""))


def _execute_knowledge_tool(params: dict[str, str]) -> IntegrationResult:
    return execute_knowledge_query(params.get("query", ""))


def get_tool_registry() -> dict[str, ToolDefinition]:
    return {
        "weather": ToolDefinition(
            name="weather",
            description="Fetch current weather for a city through the weather REST integration.",
            keywords=("weather",),
            build_params=_weather_params,
            execute=_execute_weather_tool,
        ),
        "news": ToolDefinition(
            name="news",
            description="Fetch latest news for a topic through the news REST integration.",
            keywords=("news",),
            build_params=_news_params,
            execute=_execute_news_tool,
        ),
        "search": ToolDefinition(
            name="search",
            description="Search the web through the SearXNG REST integration.",
            keywords=("search", "web search"),
            build_params=_search_params,
            execute=_execute_search_tool,
        ),
        "knowledge": ToolDefinition(
            name="knowledge",
            description="Query the local ChromaDB knowledge base with web fallback.",
            keywords=("knowledge", "knowledge base", "kb"),
            build_params=_knowledge_params,
            execute=_execute_knowledge_tool,
        ),
        "rag": ToolDefinition(
            name="rag",
            description="Default RAG chat flow for general assistant questions.",
            keywords=(),
            build_params=_rag_params,
            execute=_execute_rag_tool,
            default_tool=True,
        ),
    }


def list_tools() -> list[dict[str, Any]]:
    tools = []
    for tool in get_tool_registry().values():
        tools.append({
            "name": tool.name,
            "description": tool.description,
            "keywords": list(tool.keywords),
            "default": tool.default_tool,
        })
    return tools


def decide_chat_tool(query: str, language: str = "en") -> ToolDecision:
    registry = get_tool_registry()
    query_lower = query.lower()

    print("=" * 60)
    print("[AGENT-ROUTER] Selecting tool for chat request")
    print(f"[AGENT-ROUTER]   Query: '{query}'")
    print(f"[AGENT-ROUTER]   Language: '{language}'")
    print(f"[AGENT-ROUTER]   Candidate tools: {list(registry.keys())}")

    # Keep weather before news to preserve the old chat routing priority.
    for tool_name in ("weather", "news"):
        tool = registry[tool_name]
        for keyword in tool.keywords:
            if keyword in query_lower:
                params = tool.build_params(query, language)
                print(f"[AGENT-ROUTER]   Matched keyword: '{keyword}'")
                print(f"[AGENT-ROUTER]   Selected tool: {tool.name}")
                print(f"[AGENT-ROUTER]   Params: {params}")
                print("=" * 60)
                return ToolDecision(
                    tool_name=tool.name,
                    params=params,
                    reason="keyword_match",
                    matched_keyword=keyword,
                )

    default_tool = registry["rag"]
    params = default_tool.build_params(query, language)
    print("[AGENT-ROUTER]   No keyword match found")
    print(f"[AGENT-ROUTER]   Selected default tool: {default_tool.name}")
    print(f"[AGENT-ROUTER]   Params: {params}")
    print("=" * 60)
    return ToolDecision(
        tool_name=default_tool.name,
        params=params,
        reason="default_tool",
    )


def detect_chat_integration(query: str) -> tuple[str, dict[str, str]]:
    decision = decide_chat_tool(query)

    if decision.tool_name == "weather":
        return decision.tool_name, {"city": decision.params["city"]}

    if decision.tool_name == "news":
        return decision.tool_name, {"topic": decision.params["topic"]}

    return decision.tool_name, {"query": decision.params["query"]}


def execute_registered_tool(tool_name: str, params: dict[str, str]) -> IntegrationResult:
    registry = get_tool_registry()

    print("=" * 60)
    print("[TOOL-ROUTER] Executing registered tool")
    print(f"[TOOL-ROUTER]   Tool requested: {tool_name}")
    print(f"[TOOL-ROUTER]   Params: {params}")

    tool = registry.get(tool_name)
    if not tool:
        print(f"[TOOL-ROUTER]   Unknown tool '{tool_name}', falling back to rag")
        tool = registry["rag"]
        params = {
            "query": params.get("query", ""),
            "language": params.get("language", "en"),
        }

    print(f"[TOOL-ROUTER]   Tool description: {tool.description}")
    print("=" * 60)
    result = tool.execute(params)
    print("=" * 60)
    print("[TOOL-ROUTER] Tool execution completed")
    print(f"[TOOL-ROUTER]   Tool: {tool.name}")
    print(f"[TOOL-ROUTER]   Integration result: {result.integration}")
    print("=" * 60)
    return result


def execute_weather_lookup(city: str) -> IntegrationResult:
    from weather import get_weather

    city = city.strip() or "Delhi"
    _print_header("REST weather integration selected")
    print(f"[INTEGRATION]   Tool: get_weather")
    print(f"[INTEGRATION]   Input city: '{city}'")

    response = get_weather(city)

    _print_footer("REST weather integration", response)
    return IntegrationResult(
        integration="weather",
        response=response,
        metadata={"city": city},
    )


def execute_news_lookup(topic: str) -> IntegrationResult:
    from news import get_news

    topic = topic.strip() or "india"
    _print_header("REST news integration selected")
    print(f"[INTEGRATION]   Tool: get_news")
    print(f"[INTEGRATION]   Input topic: '{topic}'")

    response = get_news(topic)

    _print_footer("REST news integration", response)
    return IntegrationResult(
        integration="news",
        response=response,
        metadata={"topic": topic},
    )


def execute_search_query(query: str) -> IntegrationResult:
    from search import search_web

    query = query.strip()
    _print_header("REST web search integration selected")
    print(f"[INTEGRATION]   Tool: search_web")
    print(f"[INTEGRATION]   Input query: '{query}'")

    response = search_web(query) or "No search results found."

    _print_footer("REST web search integration", response)
    return IntegrationResult(
        integration="search",
        response=response,
        metadata={"query": query},
    )


def execute_knowledge_query(query: str) -> IntegrationResult:
    from rag import query_knowledge_base

    query = query.strip()
    _print_header("REST knowledge integration selected")
    print(f"[INTEGRATION]   Tool: query_knowledge_base")
    print(f"[INTEGRATION]   Input query: '{query}'")

    response = query_knowledge_base(query)

    _print_footer("REST knowledge integration", response)
    return IntegrationResult(
        integration="knowledge",
        response=response,
        metadata={"query": query},
    )


def execute_rag_chat(query: str, language: str = "en") -> IntegrationResult:
    from rag import ask_question

    _print_header("RAG chat integration selected")
    print(f"[INTEGRATION]   Tool: ask_question")
    print(f"[INTEGRATION]   Input query: '{query}'")
    print(f"[INTEGRATION]   Language: '{language}'")

    rag_query = query
    if language == "hi":
        rag_query = "उत्तर केवल हिन्दी में दें.\n\n" + query
        print("[INTEGRATION]   Applied Hindi response instruction")

    response = ask_question(rag_query, language)

    _print_footer("RAG chat integration", response)
    return IntegrationResult(
        integration="rag",
        response=response,
        metadata={"query": query, "language": language},
    )


def execute_chat_request(message: str, language: str = "en") -> IntegrationResult:
    query = message.strip()
    _print_header("Chat integration router")
    print(f"[INTEGRATION]   Incoming message: '{query}'")
    print(f"[INTEGRATION]   Language: '{language}'")

    decision = decide_chat_tool(query, language)
    print(f"[INTEGRATION]   Agent router selected tool: {decision.tool_name}")
    print(f"[INTEGRATION]   Selection reason: {decision.reason}")
    print(f"[INTEGRATION]   Matched keyword: {decision.matched_keyword}")
    print(f"[INTEGRATION]   Params: {decision.params}")
    print("=" * 60)

    return execute_registered_tool(
        decision.tool_name,
        decision.params,
    )
