"""
Database module for MyAgent.

Provides persistent storage for:
  - Chat conversations & messages
  - Generated UI metadata
  - External API response cache (weather, news, search)
  - User preferences

Uses SQLite via Python's built-in sqlite3 module — zero extra dependencies.
"""

import os
import sqlite3
import json
import time
from contextlib import contextmanager
from typing import Any, Optional

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "myagent.db")


def get_connection() -> sqlite3.Connection:
    """Get a new SQLite connection with row-factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    """Context manager that yields a database connection and commits on success."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            -- ── Conversations ──────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL DEFAULT 'New Conversation',
                created_at  REAL    NOT NULL DEFAULT (unixepoch()),
                updated_at  REAL    NOT NULL DEFAULT (unixepoch())
            );

            -- ── Messages ───────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                content         TEXT    NOT NULL,
                language        TEXT    NOT NULL DEFAULT 'en',
                tool_used       TEXT,
                metadata_json   TEXT,
                created_at      REAL    NOT NULL DEFAULT (unixepoch())
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, created_at);

            -- ── Generated UIs ─────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS generated_uis (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt      TEXT    NOT NULL,
                title       TEXT    NOT NULL DEFAULT 'Generated UI',
                filename    TEXT    NOT NULL,
                html_hash   TEXT,
                created_at  REAL    NOT NULL DEFAULT (unixepoch())
            );

            -- ── API Cache ──────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS api_cache (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key   TEXT    NOT NULL UNIQUE,
                service     TEXT    NOT NULL,
                response    TEXT    NOT NULL,
                metadata_json TEXT,
                created_at  REAL    NOT NULL DEFAULT (unixepoch()),
                expires_at  REAL    NOT NULL DEFAULT (unixepoch() + 300)
            );

            CREATE INDEX IF NOT EXISTS idx_api_cache_key
                ON api_cache(cache_key);

            CREATE INDEX IF NOT EXISTS idx_api_cache_expires
                ON api_cache(expires_at);

            -- ── User Preferences ──────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS user_preferences (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        print(f"[DB] Database initialized at {DB_PATH}")
        _log_table_counts(conn)


def _log_table_counts(conn: sqlite3.Connection):
    """Log row counts for each table (debug helper)."""
    tables = ["conversations", "messages", "generated_uis", "api_cache", "user_preferences"]
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"[DB]   {table}: {count} rows")


# ────────────────────────────────────────────────────────────────────────────
# Conversations
# ────────────────────────────────────────────────────────────────────────────

def create_conversation(title: str = "New Conversation") -> int:
    """Create a new conversation and return its ID."""
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (title) VALUES (?)",
            (title,),
        )
        conv_id = cur.lastrowid
        print(f"[DB] Created conversation #{conv_id}: '{title}'")
        return conv_id


def list_conversations(limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    """List conversations, most recent first."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT c.*, (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) AS message_count
               FROM conversations c
               ORDER BY c.updated_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def get_conversation(conversation_id: int) -> Optional[dict[str, Any]]:
    """Get a single conversation by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        return dict(row) if row else None


def delete_conversation(conversation_id: int) -> bool:
    """Delete a conversation and all its messages. Returns True if deleted."""
    with get_db() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        deleted = cur.rowcount > 0
        if deleted:
            print(f"[DB] Deleted conversation #{conversation_id}")
        return deleted


# ────────────────────────────────────────────────────────────────────────────
# Messages
# ────────────────────────────────────────────────────────────────────────────

def add_message(
    conversation_id: int,
    role: str,
    content: str,
    language: str = "en",
    tool_used: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> int:
    """Add a message to a conversation. Returns the message ID."""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO messages (conversation_id, role, content, language, tool_used, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (conversation_id, role, content, language, tool_used,
             json.dumps(metadata) if metadata else None),
        )
        msg_id = cur.lastrowid
        conn.execute(
            "UPDATE conversations SET updated_at = unixepoch() WHERE id = ?",
            (conversation_id,),
        )
        print(f"[DB] Added message #{msg_id} ({role}) to conversation #{conversation_id}")
        return msg_id


def get_messages(conversation_id: int, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Get messages for a conversation, oldest first."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM messages
               WHERE conversation_id = ?
               ORDER BY created_at ASC
               LIMIT ? OFFSET ?""",
            (conversation_id, limit, offset),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d["metadata_json"]:
                d["metadata"] = json.loads(d["metadata_json"])
            else:
                d["metadata"] = None
            del d["metadata_json"]
            result.append(d)
        return result


def get_conversation_context(conversation_id: int, max_messages: int = 10) -> list[dict]:
    """Get recent messages formatted as LLM chat context (role/content dicts)."""
    messages = get_messages(conversation_id, limit=max_messages)
    return [
        {"role": m["role"], "content": m["content"]}
        for m in messages
    ]


# ────────────────────────────────────────────────────────────────────────────
# Generated UIs
# ────────────────────────────────────────────────────────────────────────────

def add_generated_ui(prompt: str, title: str, filename: str, html_hash: Optional[str] = None) -> int:
    """Record a generated UI in the database."""
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO generated_uis (prompt, title, filename, html_hash) VALUES (?, ?, ?, ?)",
            (prompt, title, filename, html_hash),
        )
        uid = cur.lastrowid
        print(f"[DB] Recorded generated UI #{uid}: '{title}' -> {filename}")
        return uid


def list_generated_uis(limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    """List generated UIs, most recent first."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM generated_uis ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


# ────────────────────────────────────────────────────────────────────────────
# API Cache
# ────────────────────────────────────────────────────────────────────────────

def get_cached_response(service: str, cache_key: str) -> Optional[str]:
    """Get a cached API response if it exists and hasn't expired."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT response FROM api_cache
               WHERE service = ? AND cache_key = ? AND expires_at > unixepoch()""",
            (service, cache_key),
        ).fetchone()
        if row:
            print(f"[DB-CACHE] Cache HIT for {service}/{cache_key}")
            return row["response"]
        print(f"[DB-CACHE] Cache MISS for {service}/{cache_key}")
        return None


def set_cached_response(
    service: str,
    cache_key: str,
    response: str,
    ttl: int = 300,
    metadata: Optional[dict] = None,
):
    """Cache an API response with a TTL (default 5 minutes)."""
    with get_db() as conn:
        now = time.time()
        conn.execute(
            """INSERT INTO api_cache (cache_key, service, response, metadata_json, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(cache_key) DO UPDATE SET
                   response = excluded.response,
                   metadata_json = excluded.metadata_json,
                   created_at = excluded.created_at,
                   expires_at = excluded.expires_at""",
            (cache_key, service, response, json.dumps(metadata) if metadata else None,
             now, now + ttl),
        )
        print(f"[DB-CACHE] Cached {service}/{cache_key} (TTL: {ttl}s)")


def clear_expired_cache():
    """Remove expired cache entries."""
    with get_db() as conn:
        cur = conn.execute("DELETE FROM api_cache WHERE expires_at <= unixepoch()")
        if cur.rowcount:
            print(f"[DB-CACHE] Cleared {cur.rowcount} expired cache entries")


def clear_cache_for_service(service: str):
    """Clear all cached entries for a specific service."""
    with get_db() as conn:
        cur = conn.execute("DELETE FROM api_cache WHERE service = ?", (service,))
        print(f"[DB-CACHE] Cleared {cur.rowcount} entries for service '{service}'")


# ────────────────────────────────────────────────────────────────────────────
# User Preferences
# ────────────────────────────────────────────────────────────────────────────

def get_preference(key: str, default: Any = None) -> Any:
    """Get a user preference value."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM user_preferences WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]


def set_preference(key: str, value: Any):
    """Set a user preference value."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO user_preferences (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, json.dumps(value), json.dumps(value)),
        )
        print(f"[DB] Set preference '{key}' = {json.dumps(value)}")


def get_all_preferences() -> dict[str, Any]:
    """Get all user preferences as a dict."""
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM user_preferences").fetchall()
        result = {}
        for r in rows:
            try:
                result[r["key"]] = json.loads(r["value"])
            except (json.JSONDecodeError, TypeError):
                result[r["key"]] = r["value"]
        return result