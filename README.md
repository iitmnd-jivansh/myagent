# MyAgent

MyAgent is a local AI assistant application with a FastAPI backend, a browser frontend, a retrieval-augmented knowledge base, structured UI responses, official MCP tool support, and a LiveKit-powered real-time voice interface.

The project is built around a simple idea: every user request should travel through one clear backend surface, be routed to the right capability, and return both a natural-language answer and enough structured metadata for the UI or external tool clients to use it well.

The main capabilities are:

- Text chat with automatic routing to weather, news, RAG, search, UI generation, or knowledge-base tools.
- Speech-to-text input through the `/transcribe` endpoint.
- Text-to-speech output through the `/speak` endpoint.
- A local ChromaDB knowledge base with Ollama embeddings.
- Web fallback through the configured search integration when local knowledge is not enough.
- Structured GenUI responses for weather cards, news lists, UI previews, and answer panels.
- LLM-powered UI code generator that produces complete HTML pages from natural language prompts (via Groq API).
- Official MCP server support over Streamable HTTP and stdio-compatible transports.
- A LiveKit Cloud voice page and standalone LiveKit agent worker for real-time audio conversations.
- A 3D avatar frontend with speech playback visualization and lip-sync hooks.

## Current Architecture

The application has two main layers:

- `backend/`: FastAPI app, router, integrations, RAG, MCP, STT, TTS, LiveKit token generation, and LiveKit agent worker.
- `frontend/`: Browser UI, API client, GenUI renderers, avatar code, and LiveKit live voice page.

The primary backend entrypoint is:

```bash
backend/main.py
```

The frontend is served by the backend as static files from:

```bash
frontend/
```

The main browser app is available at `/`, while the LiveKit voice page is available at `/live`.

## Backend Overview

`backend/main.py` creates the FastAPI application and wires together the major subsystems:

- CORS setup for local browser access.
- Health and tools endpoints.
- Official MCP Streamable HTTP mount at `/mcp`.
- Chat, weather, news, search, and knowledge API routes.
- Speech endpoints for transcription and generated speech.
- Static frontend serving.
- LiveKit token generation for the `/live` page.

Important routes:

| Route | Method | Purpose |
| --- | --- | --- |
| `/` | GET | Main frontend application |
| `/api/health` | GET | Backend/service status |
| `/api/tools` | GET | Registered router tool list |
| `/api/chat` | POST | Main chat endpoint with automatic routing |
| `/api/weather` | GET | Direct weather lookup |
| `/api/news` | GET | Direct news lookup |
| `/api/search` | POST | Direct web search |
| `/api/knowledge` | POST | Direct knowledge-base query |
| `/transcribe` | POST | Audio upload to STT |
| `/speak` | POST | Text-to-speech MP3 response |
| `/mcp` | GET/POST/DELETE | Official MCP Streamable HTTP endpoint |
| `/mcp-status` | GET | MCP availability and advertised tools |
| `/api/generate-ui` | POST | Generate HTML UI from natural language prompt via Groq |
| `/uigen` | GET | Dedicated UI generator page |
| `/live` | GET | LiveKit voice frontend |
| `/livekit/token` | POST | LiveKit access-token generation |

The old MCP mock/testing routes and the old non-LiveKit live WebSocket implementation have been removed. The project now keeps only the official MCP path and the LiveKit live UI.

## The Integration Router

The new router lives in:

```bash
backend/integrations/router.py
```

It is the central coordination layer for all assistant tools. Instead of letting each API route call unrelated helper code directly, the router defines a small registry of available tools and gives each tool the same shape.

### Core Data Structures

The router uses three dataclasses:

```python
IntegrationResult
ToolDecision
ToolDefinition
```

`IntegrationResult` is the normalized result object returned by every tool execution. It contains:

- `integration`: the selected integration name, such as `weather`, `news`, `rag`, `search`, or `knowledge`.
- `response`: the natural-language text returned to the user.
- `metadata`: extra structured data used by GenUI and logging.

`ToolDecision` records how chat routing chose a tool. It contains:

- `tool_name`: selected tool.
- `params`: normalized parameters for that tool.
- `reason`: currently `keyword_match` or `default_tool`.
- `matched_keyword`: the keyword that caused a match, when applicable.

`ToolDefinition` describes one registered capability:

- `name`
- `description`
- `keywords`
- `build_params`
- `execute`
- `default_tool`

This registry pattern keeps routing, metadata, execution, and tool discovery in one consistent place.

### Registered Tools

The router currently registers six tools:

| Tool | Purpose | Trigger |
| --- | --- | --- |
| `ui_gen` | Generate a complete HTML UI from a natural language prompt via Groq LLM | Chat messages containing `create`, `build`, `make`, `generate`, or `design` |
| `weather` | Fetch current weather for a city | Chat messages containing `weather` |
| `news` | Fetch latest news for a topic | Chat messages containing `news` |
| `search` | Run direct SearXNG web search | Direct route or tool call |
| `knowledge` | Query the local ChromaDB knowledge base with web fallback | Direct route or tool call |
| `rag` | General assistant answer flow | Default chat route |

The `ui_gen` tool is checked first (before weather and news) so that prompts like "create a login page" are routed to the code generator rather than falling through to other tools. The chat router then intentionally checks weather before news. This preserves the previous priority where weather-specific questions should not be swallowed by broader general chat handling.

### Chat Routing Flow

When the frontend calls `/api/chat`, `backend/main.py` calls:

```python
execute_chat_request(req.message, req.language)
```

That function:

1. Trims the incoming message.
2. Logs the message and selected language.
3. Calls `decide_chat_tool()`.
4. Receives a `ToolDecision`.
5. Calls `execute_registered_tool()` with the selected tool and normalized params.
6. Returns an `IntegrationResult`.

The router chooses tools like this:

1. If the query contains `weather`, select `weather`.
2. If the query contains `news`, select `news`.
3. Otherwise, select the default `rag` tool.

Direct endpoints such as `/api/search`, `/api/weather`, and `/api/knowledge` bypass keyword detection but still use the same router execution functions. This means direct API routes and chat routing share the same integration result format.

### Why The Router Matters

The router is now the shared contract between:

- Normal REST API routes.
- The main chat endpoint.
- GenUI response generation.
- Official MCP tools.
- Future integrations.

Adding a new tool should mostly mean:

1. Add a new executor function returning `IntegrationResult`.
2. Add parameter normalization/building.
3. Register it in `get_tool_registry()`.
4. Add GenUI handling if it needs a custom visual card.
5. Optionally expose it through MCP.

That keeps the backend from turning into many one-off route handlers with different response shapes.

## GenUI

GenUI is the structured UI-response layer. It lives in:

```bash
backend/genui.py
frontend/script.js
```

The backend produces a structured `ui` object alongside the plain text response. The frontend then renders that object into a richer card.

### Backend GenUI Builder

The main function is:

```python
build_genui_response(integration, response, metadata)
```

It currently emits versioned payloads using:

```json
{
  "version": "genui.v1",
  "type": "..."
}
```

Supported UI types:

| GenUI type | Source integration | Frontend renderer |
| --- | --- | --- |
| `weather_card` | `weather` | `renderWeatherCard()` |
| `news_list` | `news` | `renderNewsList()` |
| `ui_preview` | `ui_gen` | `renderUIPreview()` |
| `search_card` | `search` | `renderSearchCard()` |
| `knowledge_card` | `knowledge` | `renderKnowledgeCard()` |
| `rag_card` | `rag` | `renderRagCard()` |
| `answer_panel` | all other integrations | `renderAnswerPanel()` |

### Weather Card

Weather responses are parsed into label/value fields by splitting response lines that contain `:`.

Example structure:

```json
{
  "version": "genui.v1",
  "type": "weather_card",
  "title": "Weather for Delhi",
  "subtitle": "Delhi",
  "fields": [
    { "label": "Temperature", "value": "31 C" },
    { "label": "Condition", "value": "Clear" }
  ]
}
```

The frontend renders this as a compact weather information card.

### News List

News responses are split by numbered items such as:

```text
1. First headline
Summary text...
2. Second headline
Summary text...
```

The backend extracts up to five items and sends:

```json
{
  "version": "genui.v1",
  "type": "news_list",
  "title": "Latest news: india",
  "items": [
    {
      "title": "Headline",
      "description": "Short description"
    }
  ]
}
```

The frontend renders each item inside a news list card.

### Answer Panel

All other integrations produce an answer panel:

```json
{
  "version": "genui.v1",
  "type": "answer_panel",
  "title": "Rag",
  "summary": "First 240 characters of the response..."
}
```

This gives search, knowledge, and general RAG answers a consistent visual fallback.

### Frontend Rendering

The main frontend logic is in:

```bash
frontend/script.js
```

After sending a message to `/api/chat`, the frontend:

1. Adds the plain response as an AI chat bubble.
2. Checks whether `data.ui` exists.
3. Calls `renderGenUICard(data.ui)`.
4. Selects the renderer based on `ui.type`.
5. Appends the generated card to the message stream.

The frontend also escapes rendered strings with `escapeHtml()` before inserting UI content, which prevents raw response text from becoming executable HTML.

## UI Generator (Codegen)

The UI generator lets you create complete, self-contained HTML pages from natural language descriptions using the Groq API (`llama-3.3-70b-versatile`). It operates through two parallel paths and supports both a dedicated page and inline chat previews.

### Backend Code Generator

The core generator lives in:

```bash
backend/codegen.py
```

The function `generate_ui(prompt)`:

1. Takes a natural language prompt like `"create a login page with purple theme"`.
2. Calls Groq's `llama-3.3-70b-versatile` model with a strict system prompt that instructs the LLM to output only raw HTML (no markdown fences, no commentary).
3. Sanitizes the output: strips any markdown code fences the LLM might have included.
4. Validates that the output starts with `<!DOCTYPE` or `<html`; wraps it in an error page otherwise.

### Dedicated Endpoint

```text
POST /api/generate-ui
Content-Type: application/json

{ "prompt": "a weather dashboard with temperature, humidity, and wind" }
```

Response:

```json
{
  "html": "<!DOCTYPE html>...",
  "title": "Weather Dashboard",
  "filename": "1784637783.html"
}
```

The endpoint also saves the generated HTML file to `frontend/generated/` with a timestamp-based filename so the file is accessible via the static file server at `generated/{filename}.html`.

### Integration Router Registration

The `ui_gen` tool is registered in the router registry (see [The Integration Router](#the-integration-router)) with these keywords: `create`, `build`, `make`, `generate`, `design`. It is checked before weather and news so that prompts like `"make a calculator"` are routed to the code generator.

When triggered through the chat router, `_execute_ui_gen_tool()` in `backend/integrations/router.py`:

1. Calls `generate_ui(prompt)` to produce the HTML.
2. Saves the file to `frontend/generated/`.
3. Extracts the `<title>` tag for display.
4. Returns an `IntegrationResult` with integration type `ui_gen` and metadata containing the HTML, title, and filename.

### GenUI Preview Card

The GenUI `ui_preview` type (`_build_ui_preview()` in `backend/genui.py`) constructs a payload with the full HTML and filename. The frontend `renderUIPreview()` function in `frontend/script.js` renders this as:

- An iframe showing the live generated UI.
- An "Open in new tab" link pointing to `generated/{filename}.html`.
- The iframe is created programmatically and `srcdoc` is set via a direct JavaScript property assignment (not HTML attribute injection), which avoids encoding issues with complex generated HTML.

### Dedicated UI Generator Page

A standalone page is available at:

```text
http://127.0.0.1:8000/uigen
```

Files:

```bash
frontend/uigen.html
frontend/uigen.js
```

Features:

- A textarea to enter prompts with Ctrl+Enter shortcut.
- An iframe preview showing the result.
- "Open in new tab" and "Copy HTML" buttons.
- History sidebar stored in `localStorage` (last 20 generations).
- Loads the most recently generated UI on page load.

### Two Ways To Generate

| Method | URL | How |
|--------|-----|-----|
| Main chat | `http://127.0.0.1:8000/` | Type `"create a login page"` — inline iframe preview in chat |
| Dedicated page | `http://127.0.0.1:8000/uigen` | Full page with history, copy, open-in-new-tab |

### Generated File Storage

All generated HTML files are saved to:

```bash
frontend/generated/{timestamp}.html
```

This directory is served by the FastAPI static file mount at `/`, so generated files are available at `http://127.0.0.1:8000/generated/{filename}.html`.

## Official MCP Support

The official MCP implementation lives in:

```bash
backend/mcp_runtime.py
backend/mcp_compatible_server.py
```

The old MCP-style mock/testing implementation was removed. The project now uses the official MCP SDK via `mcp.server.fastmcp.FastMCP`.

### MCP Runtime

`backend/mcp_runtime.py` attempts to import:

```python
from mcp.server.fastmcp import FastMCP
```

If the SDK is installed, the backend creates a stateless Streamable HTTP MCP server:

```python
FastMCP(
    "MyAgent",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)
```

The FastAPI app mounts this server at:

```text
/mcp
```

If the SDK is missing, `/mcp` returns a helpful missing-dependency response instead of failing silently.

### MCP Tools

The MCP server exposes the same five conceptual tools as the router:

- `weather(city: str = "Delhi")`
- `news(topic: str = "india")`
- `search(query: str)`
- `knowledge(query: str)`
- `rag(query: str, language: str = "en")`

Each MCP tool delegates into the router execution functions:

```python
execute_weather_lookup()
execute_news_lookup()
execute_search_query()
execute_knowledge_query()
execute_rag_chat()
```

This is important: MCP does not maintain a separate implementation. It reuses the same integration layer as the REST API and normal chat flow.

### MCP Logging

The runtime redirects integration stdout logs to stderr during MCP tool execution. That keeps tool responses clean while still preserving verbose server-side diagnostics.

### Running MCP Over HTTP

When the FastAPI server is running, MCP is mounted at:

```text
http://127.0.0.1:8000/mcp
```

The status endpoint is:

```text
http://127.0.0.1:8000/mcp-status
```

### Running MCP For Desktop Clients

`backend/mcp_compatible_server.py` is a small CLI wrapper around `run_mcp_server()`.

Use stdio transport for desktop/client integrations:

```bash
cd backend
python mcp_compatible_server.py --transport stdio
```

Use Streamable HTTP standalone mode for inspector/testing:

```bash
cd backend
python mcp_compatible_server.py --transport streamable-http
```

## RAG And Knowledge Base

The retrieval logic is in:

```bash
backend/rag.py
backend/ingest.py
backend/knowledge/
backend/chroma_db/
```

The project uses:

- ChromaDB as the persistent vector store.
- Ollama embeddings with `nomic-embed-text`.
- Ollama chat model `alibayram/smollm3` for RAG answers.
- SearXNG fallback when local knowledge is not sufficiently relevant.

### Knowledge Query Flow

`query_knowledge_base(query)`:

1. Generates an embedding for the query.
2. Queries the `knowledge_base` Chroma collection.
3. Reads the top 3 returned documents and distances.
4. Compares the best distance against `SIMILARITY_THRESHOLD`.
5. Returns local document text if the match is good.
6. Falls back to `search_web(query)` if the local match is too weak.

### RAG Chat Flow

`ask_question(query, language)`:

1. Embeds the user query.
2. Retrieves local ChromaDB context.
3. Decides between local knowledge and web fallback.
4. Builds a prompt with language instructions.
5. Sends the prompt plus chat history to Ollama.
6. Stores the user/assistant exchange in `chat_history`.
7. Keeps only the most recent 20 chat-history entries.

Hindi responses are supported by adding an explicit Hindi-only instruction before calling the RAG path.

## Search, Weather, And News Integrations

The small integration modules are:

```bash
backend/search.py
backend/weather.py
backend/news.py
```

They are intentionally thin modules. The router owns selection and response normalization; these files own the concrete fetch logic.

The router wraps their raw outputs in `IntegrationResult`, which lets the rest of the backend treat every integration uniformly.

## Speech Features

Speech support is split into STT and TTS modules:

```bash
backend/stt.py
backend/tts.py
```

The FastAPI routes are:

- `/transcribe`: accepts uploaded audio and returns text.
- `/speak`: accepts text and language, returns an MP3 response.

The main frontend uses these endpoints to support:

- Microphone recording.
- Transcription into the chat input.
- AI response playback.
- Audio visualizer animation during speech playback.
- Avatar speech/lip-sync state changes.

## Frontend Application

The main frontend files are:

```bash
frontend/index.html
frontend/script.js
frontend/api.js
frontend/styles.css
frontend/avatar/
frontend/models/
```

`frontend/api.js` centralizes browser-to-backend calls:

- `checkHealth()`
- `sendChatMessage()`
- `getWeather()`
- `getNews()`
- `searchWeb()`
- `queryKnowledgeBase()`
- `generateSpeech()`
- `transcribeAudio()`

`frontend/script.js` handles:

- Text chat submission.
- Language toggle between English and Hindi.
- Backend health check on startup.
- GenUI card rendering.
- Browser audio recording.
- TTS playback.
- Visualizer drawing.
- Avatar speaking/idle/listening state.

The avatar stack is in:

```bash
frontend/avatar/avatar.js
frontend/avatar/vrmController.js
frontend/avatar/animations.js
frontend/avatar/lipSync.js
```

It loads a VRM avatar model and uses browser-side Three.js imports through the import map in `index.html`.

## LiveKit Voice Mode

The LiveKit browser page is:

```bash
frontend/live.html
frontend/live.js
frontend/live.css
```

It is served at:

```text
http://127.0.0.1:8000/live
```

The frontend loads the LiveKit client SDK from CDN, requests a LiveKit token from `/livekit/token`, connects to a room, publishes microphone audio, subscribes to agent audio, and renders transcript messages when received.

### LiveKit Token Route

`/livekit/token` reads these environment variables:

```bash
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
LIVEKIT_URL
```

It creates an access token with room join permission and returns:

```json
{
  "token": "...",
  "url": "..."
}
```

### LiveKit Agent Worker

The standalone worker is:

```bash
backend/livekit_agent.py
```

Run it separately from FastAPI:

```bash
cd backend
python livekit_agent.py dev
```

The worker uses LiveKit Agents and configures:

- STT: Deepgram
- LLM: OpenAI-compatible Groq endpoint with `llama-3.3-70b-versatile`
- TTS: Deepgram `aura-asteria-en`
- Tools: weather, news, and knowledge-base lookup

The LiveKit agent reuses existing project functions:

- `get_weather()`
- `get_news()`
- `query_knowledge_base()`

So the real-time voice assistant is integrated with the same local knowledge and tool surface as the normal app.

## Running The Project

Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

Pull the required Ollama models:

```bash
ollama pull nomic-embed-text
ollama pull alibayram/smollm3
```

Start Ollama:

```bash
ollama serve
```

Start the backend:

```bash
cd backend
uvicorn main:app --reload
```

Open the main frontend:

```text
http://127.0.0.1:8000/
```

Open the LiveKit page:

```text
http://127.0.0.1:8000/live
```

Check MCP status:

```text
http://127.0.0.1:8000/mcp-status
```

## Environment Variables

The backend loads `.env` from `backend/.env`.

Common variables include:

```bash
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
LIVEKIT_URL=
GROQ_API_KEY=
```

Other integration modules may require their own provider-specific configuration depending on how `weather.py`, `news.py`, `search.py`, `stt.py`, and `tts.py` are configured.

## Project File Map

```text
backend/
  main.py                     FastAPI app and route wiring
  codegen.py                  LLM-powered HTML UI generator (via Groq API)
  integrations/router.py      Tool registry, chat routing, normalized integration execution
  genui.py                    Structured UI response builder
  mcp_runtime.py              Official MCP server registration/runtime
  mcp_compatible_server.py    CLI wrapper for MCP transports
  rag.py                      ChromaDB/Ollama RAG and knowledge lookup
  ingest.py                   Knowledge ingestion utility
  search.py                   Web search integration
  weather.py                  Weather integration
  news.py                     News integration
  stt.py                      Speech-to-text integration
  tts.py                      Text-to-speech integration
  livekit_agent.py            Standalone LiveKit voice agent worker
  knowledge/                  Source knowledge text files
  chroma_db/                  Persistent vector database

frontend/
  index.html                  Main assistant UI
  script.js                   Main chat, GenUI, audio, avatar behavior
  uigen.html                  Dedicated UI generator page
  uigen.js                    UI generator frontend logic
  generated/                  Generated HTML files from UI generator
  api.js                      Browser API client
  styles.css                  Main frontend styling
  live.html                   LiveKit voice UI
  live.js                     LiveKit browser logic
  live.css                    LiveKit page styling
  avatar/                     VRM avatar controller, animation, lip sync
  models/                     Frontend model assets
```

## Implementation Notes

- The router is the preferred place to add new assistant tools.
- The REST API, MCP runtime, and GenUI builder all depend on the router contract.
- MCP now uses the official SDK only; the old mock JSON-RPC testing implementation is intentionally gone.
- The LiveKit page has been renamed to the canonical `live.*` files.
- The old `/ws/live` Gemini WebSocket path is intentionally gone.
- GenUI payloads are versioned as `genui.v1` so the frontend contract can evolve without guessing payload shape.
- Direct API routes return both `response` and `ui`, so frontend features do not have to depend only on `/api/chat`.
- The LiveKit agent is a separate process from the FastAPI app. FastAPI creates room tokens; the worker joins rooms and provides the voice AI.

## Extension Guide

To add a new backend tool:

1. Implement the concrete integration function in a focused module.
2. Add an executor in `backend/integrations/router.py` that returns `IntegrationResult`.
3. Add a `ToolDefinition` to `get_tool_registry()`.
4. Add keyword routing if chat should auto-select the tool.
5. Add a custom GenUI type in `backend/genui.py` if the frontend should render a special card.
6. Add a renderer in `frontend/script.js`.
7. Expose the tool in `backend/mcp_runtime.py` if MCP clients should be able to call it.

This keeps each feature available through the same clean surfaces: REST, chat routing, GenUI, and MCP.

## Database Persistence

MyAgent now includes a built-in SQLite database (`backend/myagent.db`) for persistent storage — zero extra dependencies required.

### Database Tables

| Table | Purpose |
|-------|---------|
| `conversations` | Chat sessions with title & timestamps |
| `messages` | Individual messages linked to conversations |
| `generated_uis` | History of generated UIs (prompt, title, filename) |
| `api_cache` | Time-based cache for external API responses (5 min TTL) |
| `user_preferences` | Key-value store for user settings |

### Database API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/v2/chat` | Persistent chat with conversation tracking |
| GET | `/api/conversations` | List conversations (paginated) |
| GET | `/api/conversations/{id}` | Get messages for a conversation |
| DELETE | `/api/conversations/{id}` | Delete a conversation and its messages |
| GET | `/api/generated-uis` | List generated UI history |
| GET | `/api/preferences` | Get all user preferences |
| GET | `/api/preferences/{key}` | Get a specific preference |
| POST | `/api/preferences` | Set a preference |
| DELETE | `/api/cache/{service}` | Clear API cache for a service (weather/news/search) |

### Persistent Chat

The original `/api/chat` endpoint remains unchanged. A new endpoint `/api/v2/chat` adds conversation persistence:

```
POST /api/v2/chat  {"message": "Hello", "conversation_id": null}
→ Returns { "conversation_id": 1, "response": "...", "ui": {...} }

POST /api/v2/chat  {"message": "Follow up", "conversation_id": 1}
→ Continues conversation #1
```

If `conversation_id` is omitted, a new conversation is auto-created using the first message as the title.

### API Response Caching

The following endpoints now cache responses in the database with a 5-minute TTL:

- `GET /api/weather?city=...`
- `GET /api/news?topic=...`
- `POST /api/search`

They return `"cached": true` when serving from cache. The cache can be cleared per-service via `DELETE /api/cache/{service}`.

### UI Generation History

The `/api/generate-ui` endpoint now records each generation in the database (prompt, title, filename, hash). The history is accessible via `GET /api/generated-uis`.

### User Preferences

Preferences are stored as JSON values and managed through:

```
GET  /api/preferences        — Get all preferences
GET  /api/preferences/{key}  — Get a specific preference
POST /api/preferences        — Set a preference  {"key": "...", "value": ...}
```

Example: storing the user's language preference:

```bash
curl -X POST http://127.0.0.1:8000/api/preferences \
  -H "Content-Type: application/json" \
  -d '{"key": "language", "value": "hi"}'
```

### Related Files

```text
backend/database.py            Database module (models, queries, caching)
```
