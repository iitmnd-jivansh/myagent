"""
Database module for MyAgent.

Provides persistent storage for:
  - Chat conversations & messages
  - Generated UI metadata
  - External API response cache (weather, news, search)
  - User preferences

Dual-mode architecture:
  - When SUPABASE_URL and SUPABASE_SERVICE_KEY are set in .env, uses Supabase (PostgreSQL).
  - Otherwise falls back to local SQLite via Python's built-in sqlite3 module.
"""

import os
import sqlite3
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv

from supabase_client import get_supabase, is_supabase_enabled

load_dotenv()

# ── SQLite Configuration (fallback) ──────────────────────────────
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


def _utcnow():
    """Return current UTC timestamp as ISO string for Supabase."""
    return datetime.now(timezone.utc).isoformat()


# ────────────────────────────────────────────────────────────────
# Initialization
# ────────────────────────────────────────────────────────────────


def init_db():
    """Initialize the database.

    Creates the local SQLite tables (always — for SQLite fallback mode).
    When Supabase is enabled, users and sessions are stored in PostgreSQL
    via the Supabase client, but local SQLite tables are still created
    as a fallback in case Supabase is temporarily unavailable.
    """
    if is_supabase_enabled():
        print("[DB] Using Supabase PostgreSQL backend for conversations/messages")
        print("[DB] (users table is always local SQLite — initializing it too)")

    # Local SQLite is always initialized — required for auth regardless of
    # whether Supabase is used for conversations/messages/etc.
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

            -- ── Sessions ────────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token           TEXT    NOT NULL UNIQUE,
                created_at      REAL    NOT NULL DEFAULT (unixepoch()),
                expires_at      REAL    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_token
                ON sessions(token);

            CREATE INDEX IF NOT EXISTS idx_sessions_user_id
                ON sessions(user_id);

            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at
                ON sessions(expires_at);

            -- ── Users ─────────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT    NOT NULL UNIQUE,
                display_name    TEXT    NOT NULL DEFAULT '',
                password_hash   TEXT    NOT NULL,
                created_at      REAL    NOT NULL DEFAULT (unixepoch())
            );

            -- ── User Preferences ──────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS user_preferences (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        # Safe migration: add user_id to conversations if it doesn't exist
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
            print("[DB] Migration: added user_id column to conversations")
        except Exception:
            # Column already exists — ignore
            pass

        print(f"[DB] SQLite database initialized at {DB_PATH}")
        _log_table_counts(conn)


def _log_table_counts(conn: sqlite3.Connection):
    """Log row counts for each table (debug helper)."""
    tables = ["conversations", "messages", "generated_uis", "api_cache", "user_preferences"]
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"[DB]   {table}: {count} rows")


# ────────────────────────────────────────────────────────────────
# Conversations
# ────────────────────────────────────────────────────────────────


def create_conversation(title: str = "New Conversation") -> int:
    """Create a new conversation and return its ID."""
    if is_supabase_enabled():
        supabase = get_supabase()
        now = _utcnow()
        result = supabase.table("conversations").insert({
            "title": title,
            "created_at": now,
            "updated_at": now,
        }).execute()
        conv_id = result.data[0]["id"]
        print(f"[DB] Created Supabase conversation #{conv_id}: '{title}'")
        return conv_id

    # SQLite fallback
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
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("conversations") \
            .select("*, messages(count)") \
            .order("updated_at", desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()
        convs = []
        for row in result.data:
            convs.append({
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "message_count": row.get("messages", [{}])[0].get("count", 0) if isinstance(row.get("messages"), list) else 0,
            })
        return convs

    # SQLite fallback
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
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("conversations") \
            .select("*") \
            .eq("id", conversation_id) \
            .execute()
        if result.data:
            return result.data[0]
        return None

    # SQLite fallback
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        return dict(row) if row else None


def delete_conversation(conversation_id: int) -> bool:
    """Delete a conversation and all its messages. Returns True if deleted."""
    if is_supabase_enabled():
        supabase = get_supabase()
        # First delete messages (CASCADE should handle this, but do explicitly)
        supabase.table("messages").delete().eq("conversation_id", conversation_id).execute()
        result = supabase.table("conversations").delete().eq("id", conversation_id).execute()
        deleted = len(result.data) > 0
        if deleted:
            print(f"[DB] Deleted Supabase conversation #{conversation_id}")
        return deleted

    # SQLite fallback
    with get_db() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        deleted = cur.rowcount > 0
        if deleted:
            print(f"[DB] Deleted conversation #{conversation_id}")
        return deleted


# ────────────────────────────────────────────────────────────────
# Messages
# ────────────────────────────────────────────────────────────────


def add_message(
    conversation_id: int,
    role: str,
    content: str,
    language: str = "en",
    tool_used: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> int:
    """Add a message to a conversation. Returns the message ID."""
    if is_supabase_enabled():
        supabase = get_supabase()
        now = _utcnow()
        result = supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "language": language,
            "tool_used": tool_used,
            "metadata_json": json.dumps(metadata) if metadata else None,
            "created_at": now,
        }).execute()
        msg_id = result.data[0]["id"]
        # Update conversation's updated_at
        supabase.table("conversations").update({"updated_at": now}).eq("id", conversation_id).execute()
        print(f"[DB] Added Supabase message #{msg_id} ({role}) to conversation #{conversation_id}")
        return msg_id

    # SQLite fallback
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
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("messages") \
            .select("*") \
            .eq("conversation_id", conversation_id) \
            .order("created_at", desc=False) \
            .range(offset, offset + limit - 1) \
            .execute()
        msgs = []
        for r in result.data:
            d = dict(r)
            if d.get("metadata_json"):
                try:
                    d["metadata"] = json.loads(d["metadata_json"])
                except (json.JSONDecodeError, TypeError):
                    d["metadata"] = None
            else:
                d["metadata"] = None
            del d["metadata_json"]
            msgs.append(d)
        return msgs

    # SQLite fallback
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


# ────────────────────────────────────────────────────────────────
# Generated UIs
# ────────────────────────────────────────────────────────────────


def add_generated_ui(prompt: str, title: str, filename: str, html_hash: Optional[str] = None) -> int:
    """Record a generated UI in the database."""
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("generated_uis").insert({
            "prompt": prompt,
            "title": title,
            "filename": filename,
            "html_hash": html_hash,
            "created_at": _utcnow(),
        }).execute()
        uid = result.data[0]["id"]
        print(f"[DB] Recorded Supabase generated UI #{uid}: '{title}' -> {filename}")
        return uid

    # SQLite fallback
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
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("generated_uis") \
            .select("*") \
            .order("created_at", desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()
        return [dict(r) for r in result.data]

    # SQLite fallback
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM generated_uis ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


# ────────────────────────────────────────────────────────────────
# API Cache
# ────────────────────────────────────────────────────────────────


def get_cached_response(service: str, cache_key: str) -> Optional[str]:
    """Get a cached API response if it exists and hasn't expired."""
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("api_cache") \
            .select("response") \
            .eq("service", service) \
            .eq("cache_key", cache_key) \
            .gt("expires_at", _utcnow()) \
            .execute()
        if result.data:
            print(f"[DB-CACHE] Cache HIT for {service}/{cache_key}")
            return result.data[0]["response"]
        print(f"[DB-CACHE] Cache MISS for {service}/{cache_key}")
        return None

    # SQLite fallback
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
    if is_supabase_enabled():
        supabase = get_supabase()
        now = _utcnow()
        expires_at = datetime.now(timezone.utc).timestamp() + ttl
        expires_at_iso = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
        supabase.table("api_cache").upsert({
            "cache_key": cache_key,
            "service": service,
            "response": response,
            "metadata_json": json.dumps(metadata) if metadata else None,
            "created_at": now,
            "expires_at": expires_at_iso,
        }, on_conflict="cache_key").execute()
        print(f"[DB-CACHE] Cached {service}/{cache_key} (TTL: {ttl}s)")
        return

    # SQLite fallback
    now = time.time()
    with get_db() as conn:
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
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("api_cache").delete().lt("expires_at", _utcnow()).execute()
        if result.data:
            print(f"[DB-CACHE] Cleared {len(result.data)} expired cache entries")
        return

    # SQLite fallback
    with get_db() as conn:
        cur = conn.execute("DELETE FROM api_cache WHERE expires_at <= unixepoch()")
        if cur.rowcount:
            print(f"[DB-CACHE] Cleared {cur.rowcount} expired cache entries")


def clear_cache_for_service(service: str):
    """Clear all cached entries for a specific service."""
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("api_cache").delete().eq("service", service).execute()
        print(f"[DB-CACHE] Cleared {len(result.data)} entries for service '{service}'")
        return

    # SQLite fallback
    with get_db() as conn:
        cur = conn.execute("DELETE FROM api_cache WHERE service = ?", (service,))
        print(f"[DB-CACHE] Cleared {cur.rowcount} entries for service '{service}'")


# ────────────────────────────────────────────────────────────────
# User Preferences
# ────────────────────────────────────────────────────────────────


def get_preference(key: str, default: Any = None) -> Any:
    """Get a user preference value."""
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("user_preferences") \
            .select("value") \
            .eq("key", key) \
            .execute()
        if not result.data:
            return default
        value = result.data[0]["value"]
        # value is already parsed from JSONB
        return value

    # SQLite fallback
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
    if is_supabase_enabled():
        supabase = get_supabase()
        supabase.table("user_preferences").upsert({
            "key": key,
            "value": value,  # supabase-py handles JSONB serialization
        }, on_conflict="key").execute()
        print(f"[DB] Set Supabase preference '{key}' = {json.dumps(value)}")
        return

    # SQLite fallback
    with get_db() as conn:
        conn.execute(
            "INSERT INTO user_preferences (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, json.dumps(value), json.dumps(value)),
        )
        print(f"[DB] Set preference '{key}' = {json.dumps(value)}")


def get_all_preferences() -> dict[str, Any]:
    """Get all user preferences as a dict."""
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("user_preferences").select("key, value").execute()
        return {r["key"]: r["value"] for r in result.data}

    # SQLite fallback
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM user_preferences").fetchall()
        result = {}
        for r in rows:
            try:
                result[r["key"]] = json.loads(r["value"])
            except (json.JSONDecodeError, TypeError):
                result[r["key"]] = r["value"]
        return result


# ────────────────────────────────────────────────────────────────
# Users (SQLite fallback + Supabase)
# ────────────────────────────────────────────────────────────────


def create_user(username: str, password_hash: str, display_name: str = "") -> int:
    """Create a new user. Returns the user ID. Raises ValueError if username exists."""
    if is_supabase_enabled():
        supabase = get_supabase()
        # Check if username already exists
        existing = supabase.table("users").select("id").eq("username", username).execute()
        if existing.data:
            raise ValueError(f"Username '{username}' already exists")
        result = supabase.table("users").insert({
            "username": username,
            "display_name": display_name,
            "password_hash": password_hash,
        }).execute()
        user_id = result.data[0]["id"]
        print(f"[DB] Created Supabase user #{user_id}: '{username}'")
        return user_id

    # SQLite fallback
    with get_db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, display_name, password_hash) VALUES (?, ?, ?)",
                (username, display_name, password_hash),
            )
            user_id = cur.lastrowid
            print(f"[DB] Created SQLite user #{user_id}: '{username}'")
            return user_id
        except sqlite3.IntegrityError:
            raise ValueError(f"Username '{username}' already exists")


def get_user_by_username(username: str) -> Optional[dict[str, Any]]:
    """Get a user by username."""
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("users").select("*").eq("username", username).execute()
        if result.data:
            return result.data[0]
        return None

    # SQLite fallback
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict[str, Any]]:
    """Get a user by ID."""
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("users").select("*").eq("id", user_id).execute()
        if result.data:
            return result.data[0]
        return None

    # SQLite fallback
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


# ────────────────────────────────────────────────────────────────
# Sessions (Supabase + SQLite fallback)
# ────────────────────────────────────────────────────────────────


def create_session(user_id: int, token: str, expires_at: float) -> int:
    """
    Create a new session for a user.
    
    Args:
        user_id: The user's ID
        token: The JWT token string
        expires_at: Unix timestamp when the session expires
    
    Returns:
        The session ID
    """
    if is_supabase_enabled():
        supabase = get_supabase()
        from datetime import datetime, timezone
        expires_at_iso = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
        result = supabase.table("sessions").insert({
            "user_id": user_id,
            "token": token,
            "expires_at": expires_at_iso,
        }).execute()
        session_id = result.data[0]["id"]
        print(f"[DB] Created Supabase session #{session_id} for user #{user_id}")
        return session_id

    # SQLite fallback
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at),
        )
        session_id = cur.lastrowid
        print(f"[DB] Created SQLite session #{session_id} for user #{user_id}")
        return session_id


def get_session_by_token(token: str) -> Optional[dict[str, Any]]:
    """
    Get a valid (non-expired) session by its token.
    
    Returns:
        Session dict with user info, or None if not found/expired
    """
    import time
    now = time.time()

    if is_supabase_enabled():
        supabase = get_supabase()
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        result = supabase.table("sessions") \
            .select("*, users!inner(id, username, display_name)") \
            .eq("token", token) \
            .gt("expires_at", now_iso) \
            .execute()
        if result.data:
            row = result.data[0]
            return {
                "id": row["id"],
                "user_id": row["user_id"],
                "token": row["token"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "user": {
                    "id": row["users"]["id"],
                    "username": row["users"]["username"],
                    "display_name": row["users"]["display_name"],
                },
            }
        return None

    # SQLite fallback
    with get_db() as conn:
        row = conn.execute(
            """SELECT s.*, u.id AS user_id, u.username, u.display_name
               FROM sessions s
               JOIN users u ON s.user_id = u.id
               WHERE s.token = ? AND s.expires_at > ?""",
            (token, now),
        ).fetchone()
        if row:
            d = dict(row)
            return {
                "id": d["id"],
                "user_id": d["user_id"],
                "token": d["token"],
                "created_at": d["created_at"],
                "expires_at": d["expires_at"],
                "user": {
                    "id": d["user_id"],
                    "username": d["username"],
                    "display_name": d["display_name"],
                },
            }
        return None


def delete_session(token: str) -> bool:
    """Delete a session by its token. Returns True if deleted."""
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("sessions").delete().eq("token", token).execute()
        deleted = len(result.data) > 0
        if deleted:
            print(f"[DB] Deleted Supabase session for token")
        return deleted

    # SQLite fallback
    with get_db() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        deleted = cur.rowcount > 0
        if deleted:
            print(f"[DB] Deleted SQLite session")
        return deleted


def delete_expired_sessions() -> int:
    """Delete all expired sessions. Returns the number deleted."""
    import time
    now = time.time()

    if is_supabase_enabled():
        supabase = get_supabase()
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        result = supabase.table("sessions").delete().lt("expires_at", now_iso).execute()
        deleted = len(result.data)
        if deleted:
            print(f"[DB] Cleaned up {deleted} expired Supabase sessions")
        return deleted

    # SQLite fallback
    with get_db() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        deleted = cur.rowcount
        if deleted:
            print(f"[DB] Cleaned up {deleted} expired SQLite sessions")
        return deleted


def create_conversation_for_user(user_id: int, title: str = "New Conversation") -> int:
    """Create a new conversation linked to a user. Returns the conversation ID."""
    if is_supabase_enabled():
        supabase = get_supabase()
        now = _utcnow()
        result = supabase.table("conversations").insert({
            "title": title,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
        }).execute()
        conv_id = result.data[0]["id"]
        print(f"[DB] Created Supabase conversation #{conv_id} for user #{user_id}: '{title}'")
        return conv_id

    # SQLite fallback
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (title, user_id) VALUES (?, ?)",
            (title, user_id),
        )
        conv_id = cur.lastrowid
        print(f"[DB] Created conversation #{conv_id} for user #{user_id}: '{title}'")
        return conv_id


def list_conversations_for_user(user_id: int, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    """List conversations for a specific user, most recent first."""
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("conversations") \
            .select("*, messages(count)") \
            .eq("user_id", user_id) \
            .order("updated_at", desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()
        convs = []
        for row in result.data:
            convs.append({
                "id": row["id"],
                "title": row["title"],
                "user_id": row.get("user_id"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "message_count": row.get("messages", [{}])[0].get("count", 0) if isinstance(row.get("messages"), list) else 0,
                "last_preview": None,  # Supabase doesn't easily support subquery previews
            })
        return convs

    # SQLite fallback
    with get_db() as conn:
        rows = conn.execute(
            """SELECT c.*,
                      (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) AS message_count,
                      (SELECT SUBSTR(content, 1, 100) FROM messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) AS last_preview
               FROM conversations c
               WHERE c.user_id = ?
               ORDER BY c.updated_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, limit, offset),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("last_preview") and len(d["last_preview"]) >= 100:
                d["last_preview"] = d["last_preview"][:100] + "..."
            result.append(d)
        return result


def update_conversation_title(conversation_id: int, title: str) -> bool:
    """Update the title of a conversation. Returns True if updated."""
    if is_supabase_enabled():
        supabase = get_supabase()
        now = _utcnow()
        result = supabase.table("conversations").update({
            "title": title,
            "updated_at": now,
        }).eq("id", conversation_id).execute()
        updated = len(result.data) > 0
        if updated:
            print(f"[DB] Updated Supabase conversation #{conversation_id} title to '{title}'")
        return updated

    # SQLite fallback
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE conversations SET title = ?, updated_at = unixepoch() WHERE id = ?",
            (title, conversation_id),
        )
        updated = cur.rowcount > 0
        if updated:
            print(f"[DB] Updated conversation #{conversation_id} title to '{title}'")
        return updated


def get_last_message_preview(conversation_id: int) -> Optional[str]:
    """Get the last message content preview (first 100 chars) for a conversation."""
    if is_supabase_enabled():
        supabase = get_supabase()
        result = supabase.table("messages") \
            .select("content") \
            .eq("conversation_id", conversation_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        if result.data:
            text = result.data[0]["content"][:100]
            if len(result.data[0]["content"]) > 100:
                text += "..."
            return text
        return None

    # SQLite fallback
    with get_db() as conn:
        row = conn.execute(
            "SELECT content FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 1",
            (conversation_id,),
        ).fetchone()
        if row:
            text = row["content"][:100]
            if len(row["content"]) > 100:
                text += "..."
            return text
        return None
