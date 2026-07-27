/**
 * MyAgent Frontend Authentication Module
 *
 * Provides username/password authentication with JWT token management.
 * Stores auth state in localStorage for persistence across page reloads.
 * Also persists the last active conversation ID for session continuity.
 *
 * API endpoints (backend/main.py):
 *   POST /api/auth/signup  — Register a new user
 *   POST /api/auth/signin  — Sign in with username/password
 *   GET  /api/auth/me     — Get current user profile (validates token)
 *
 * Storage format (localStorage key: "myagent_auth"):
 *   { "token": "<jwt>", "user": { id, username, display_name } }
 *
 * Conversation ID stored under key: "myagent_last_conversation"
 */

import { API_BASE } from "./config.js";

const AUTH_STORAGE_KEY = "myagent_auth";
const CONVERSATION_STORAGE_KEY = "myagent_last_conversation";

/**
 * Read and parse the stored auth data from localStorage.
 * @returns {{token: string, user: object}|null}
 */
function _getStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (raw) {
      const auth = JSON.parse(raw);
      if (auth && auth.token) {
        return auth;
      }
    }
  } catch (e) {
    // Ignore parse errors — treat as no auth
  }
  return null;
}

/**
 * Persist auth data to localStorage.
 * @param {string} token - JWT token
 * @param {object} user - User profile object
 */
function _setStoredAuth(token, user) {
  const auth = { token, user };
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
}

/**
 * Remove auth data from localStorage.
 */
function _clearStoredAuth() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
  // Also clear the stored conversation ID on sign out
  localStorage.removeItem(CONVERSATION_STORAGE_KEY);
}

/**
 * Get the stored JWT token.
 * @returns {string|null}
 */
export function getToken() {
  const auth = _getStoredAuth();
  return auth ? auth.token : null;
}

/**
 * Get the stored user object.
 * @returns {{id: number, username: string, display_name: string}|null}
 */
export function getUser() {
  const auth = _getStoredAuth();
  return auth ? auth.user : null;
}

/**
 * Check whether the user is authenticated (has a stored token).
 * @returns {boolean}
 */
export function isAuthenticated() {
  const auth = _getStoredAuth();
  return !!(auth && auth.token);
}

/**
 * Get the last active conversation ID from localStorage.
 * @returns {number|null}
 */
export function getLastConversationId() {
  try {
    const raw = localStorage.getItem(CONVERSATION_STORAGE_KEY);
    if (raw) {
      const id = parseInt(raw, 10);
      return isNaN(id) ? null : id;
    }
  } catch (e) {
    // Ignore
  }
  return null;
}

/**
 * Store the last active conversation ID in localStorage.
 * @param {number|null} conversationId
 */
export function setLastConversationId(conversationId) {
  if (conversationId === null || conversationId === undefined) {
    localStorage.removeItem(CONVERSATION_STORAGE_KEY);
  } else {
    localStorage.setItem(CONVERSATION_STORAGE_KEY, String(conversationId));
  }
}

/**
 * Initialize auth state on app startup.
 * Validates the stored token against the backend /api/auth/me endpoint.
 * If the backend is unreachable, falls back to the stored token so the
 * app remains usable offline.
 * @returns {Promise<boolean>} True if authenticated
 */
export async function initAuth() {
  const stored = _getStoredAuth();
  if (!stored || !stored.token) {
    return false;
  }

  // Try to validate the token with the backend
  try {
    const response = await fetch(`${API_BASE}/api/auth/me`, {
      headers: {
        Authorization: `Bearer ${stored.token}`,
      },
    });

    if (response.ok) {
      const data = await response.json();
      if (data.authenticated && data.user) {
        // Refresh stored user data from backend
        _setStoredAuth(stored.token, data.user);
        return true;
      }
    }

    // Token is invalid or expired — clear stored auth
    _clearStoredAuth();
    return false;
  } catch (e) {
    // Backend unreachable — fall back to stored token
    console.warn("[Auth] Backend unreachable during init", e);
    return false;
  }
}

/**
 * Sign in with username and password.
 * Calls POST /api/auth/signin, stores the returned token and user.
 * @param {string} username
 * @param {string} password
 * @returns {Promise<{user: object, token: string}>}
 * @throws {Error} If sign-in fails (invalid credentials, network error, etc.)
 */
export async function signIn(username, password) {
  const data = await submitAuth("/api/auth/signin", { username, password }, "Sign in failed");

  _setStoredAuth(data.token, data.user);
  return data;
}

/**
 * Sign up with username, password, and optional display name.
 * Calls POST /api/auth/signup, stores the returned token and user.
 * @param {string} username
 * @param {string} password
 * @param {string} [displayName] - Optional display name (defaults to username)
 * @returns {Promise<{user: object, token: string}>}
 * @throws {Error} If sign-up fails (username taken, validation error, etc.)
 */
export async function signUp(username, password, displayName = "") {
  const data = await submitAuth(
    "/api/auth/signup",
    {
      username,
      password,
      display_name: displayName,
    },
    "Sign up failed"
  );

  _setStoredAuth(data.token, data.user);
  return data;
}

async function submitAuth(endpoint, payload, fallbackError) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || data.error || fallbackError);
  }

  if (!data.token || !data.user) {
    throw new Error(fallbackError);
  }

  return data;
}

/**
 * Sign out the current user.
 * Attempts to delete the session from the backend, then clears local storage.
 */
export async function signOut() {
  // Try to notify the backend to delete the session
  const token = getToken();
  if (token) {
    try {
      await fetch(`${API_BASE}/api/auth/signout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    } catch (e) {
      // Ignore network errors — just clear locally
      console.warn("[Auth] Backend sign-out request failed:", e);
    }
  }
  _clearStoredAuth();
}
