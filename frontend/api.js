/**
 * MyAgent API Service
 * 
 * Centralized API layer for communicating with the MyAgent backend.
 * All API calls go through this module for consistent error handling,
 * base URL configuration, and logging.
 */

const API_BASE = "http://127.0.0.1:8000";

/**
 * Generic fetch wrapper with error handling.
 * @param {string} endpoint - API endpoint path (e.g., "/api/chat")
 * @param {object} options - Fetch options (method, headers, body, etc.)
 * @returns {Promise<object>} Parsed JSON response
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;

  const defaultHeaders = {
    "Content-Type": "application/json",
  };

  const config = {
    headers: { ...defaultHeaders, ...options.headers },
    ...options,
  };

  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (options.body instanceof FormData) {
    delete config.headers["Content-Type"];
  }

  const response = await fetch(url, config);

  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error");
    throw new Error(
      `API ${endpoint} failed (${response.status}): ${errorText}`
    );
  }

  // Check if response is JSON or binary (blob)
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response;
}

/**
 * Check backend health and service status.
 * @returns {Promise<object>} Health status response
 */
export async function checkHealth() {
  return request("/api/health");
}

/**
 * Send a chat message and get an AI response.
 * @param {string} message - User message text
 * @param {string} language - Language code ("en" or "hi")
 * @returns {Promise<object>} Response with `response` field
 */
export async function sendChatMessage(message, language = "en") {
  return request("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message, language }),
  });
}

/**
 * Get current weather for a city.
 * @param {string} city - City name
 * @returns {Promise<object>} Response with `city` and `response` fields
 */
export async function getWeather(city = "Delhi") {
  return request(`/api/weather?city=${encodeURIComponent(city)}`);
}

/**
 * Get latest news for a topic.
 * @param {string} topic - News topic (e.g., "technology", "india")
 * @returns {Promise<object>} Response with `topic` and `response` fields
 */
export async function getNews(topic = "india") {
  return request(`/api/news?topic=${encodeURIComponent(topic)}`);
}

/**
 * Search the web using SearXNG.
 * @param {string} query - Search query
 * @returns {Promise<object>} Response with `query` and `response` fields
 */
export async function searchWeb(query) {
  return request("/api/search", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

/**
 * Query the local knowledge base (ChromaDB + RAG).
 * @param {string} query - Search query for the knowledge base
 * @returns {Promise<object>} Response with `query` and `response` fields
 */
export async function queryKnowledgeBase(query) {
  return request("/api/knowledge", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

/**
 * Convert text to speech and get an audio blob.
 * @param {string} text - Text to speak
 * @param {string} language - Language code ("en" or "hi")
 * @returns {Promise<Blob>} Audio blob (MP3 format)
 */
export async function generateSpeech(text, language = "en") {
  const response = await request("/speak", {
    method: "POST",
    body: JSON.stringify({ message: text, language }),
  });
  return response.blob();
}

/**
 * Transcribe audio to text using STT.
 * @param {Blob} audioBlob - Audio recording blob (WAV format)
 * @param {string} language - Language code ("en" or "hi")
 * @returns {Promise<object>} Response with `text` field
 */
export async function transcribeAudio(audioBlob, language = "en") {
  const formData = new FormData();
  formData.append("file", audioBlob, "recording.wav");
  formData.append("language", language);
  return request("/transcribe", {
    method: "POST",
    body: formData,
  });
}