import re
from typing import Any


def _parse_key_value_lines(text: str) -> list[dict[str, str]]:
    fields = []
    for line in text.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label = label.strip()
        value = value.strip()
        if label and value:
            fields.append({
                "label": label,
                "value": value,
            })
    return fields


def _build_weather_card(response: str, metadata: dict[str, Any]) -> dict[str, Any]:
    title = "Weather"
    for line in response.splitlines():
        if line.strip().lower().startswith("weather for"):
            title = line.strip()
            break

    return {
        "version": "genui.v1",
        "type": "weather_card",
        "title": title,
        "subtitle": metadata.get("city"),
        "fields": _parse_key_value_lines(response),
    }


def _build_news_list(response: str, metadata: dict[str, Any]) -> dict[str, Any]:
    items = []
    chunks = re.split(r"\n(?=\d+\.\s)", response)

    for chunk in chunks:
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if not lines or not re.match(r"^\d+\.", lines[0]):
            continue

        title = re.sub(r"^\d+\.\s*", "", lines[0]).strip()
        description = " ".join(lines[1:]).strip()
        items.append({
            "title": title,
            "description": description,
        })

    return {
        "version": "genui.v1",
        "type": "news_list",
        "title": f"Latest news: {metadata.get('topic', 'news')}",
        "items": items[:5],
    }


def _build_search_card(response: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Build a rich search result card with query context and full response."""
    return {
        "version": "genui.v1",
        "type": "search_card",
        "title": "Web Search",
        "subtitle": metadata.get("query", ""),
        "response": response,
        "summary": response[:300],
    }


def _build_knowledge_card(response: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Build a knowledge base card showing source (KB vs web fallback) and full response."""
    return {
        "version": "genui.v1",
        "type": "knowledge_card",
        "title": "Knowledge Base",
        "subtitle": metadata.get("query", ""),
        "response": response,
        "summary": response[:300],
    }


def _build_rag_card(response: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Build a rich RAG assistant card with full response and language context."""
    return {
        "version": "genui.v1",
        "type": "rag_card",
        "title": "Assistant",
        "response": response,
        "summary": response[:300],
        "language": metadata.get("language", "en"),
    }


def _build_ui_preview(response: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Build a UI preview card with an iframe showing the generated HTML."""
    return {
        "version": "genui.v1",
        "type": "ui_preview",
        "title": metadata.get("title", "Generated UI"),
        "html": metadata.get("html", ""),
        "filename": metadata.get("filename", ""),
        "summary": response,
    }


def build_genui_response(
    integration: str,
    response: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = metadata or {}

    print("=" * 60)
    print("[GENUI] Building UI response")
    print(f"[GENUI]   Integration: {integration}")
    print(f"[GENUI]   Metadata: {metadata}")

    if integration == "weather":
        ui = _build_weather_card(response, metadata)
    elif integration == "news":
        ui = _build_news_list(response, metadata)
    elif integration == "search":
        ui = _build_search_card(response, metadata)
    elif integration == "knowledge":
        ui = _build_knowledge_card(response, metadata)
    elif integration == "rag":
        ui = _build_rag_card(response, metadata)
    elif integration == "ui_gen":
        ui = _build_ui_preview(response, metadata)
    else:
        # Fallback for unknown integrations
        ui = {
            "version": "genui.v1",
            "type": "answer_panel",
            "title": integration.replace("_", " ").title(),
            "summary": response[:240],
        }

    print(f"[GENUI]   UI type: {ui['type']}")
    print("=" * 60)
    return ui
