-- =============================================================
-- Supabase Schema for MyAgent
-- Run this SQL in your Supabase project's SQL Editor
-- =============================================================

-- ── Migration: Add user_id to conversations (safe to re-run) ──
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'conversations' AND column_name = 'user_id'
  ) THEN
    ALTER TABLE conversations ADD COLUMN user_id BIGINT;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);

-- ── Conversations ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id          BIGSERIAL PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT 'New Conversation',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE conversations DISABLE ROW LEVEL SECURITY;

-- ── Messages ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    language        TEXT NOT NULL DEFAULT 'en',
    tool_used       TEXT,
    metadata_json   JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);
ALTER TABLE messages DISABLE ROW LEVEL SECURITY;

-- ── Generated UIs ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS generated_uis (
    id          BIGSERIAL PRIMARY KEY,
    prompt      TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT 'Generated UI',
    filename    TEXT NOT NULL,
    html_hash   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE generated_uis DISABLE ROW LEVEL SECURITY;

-- ── API Cache ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_cache (
    id            BIGSERIAL PRIMARY KEY,
    cache_key     TEXT NOT NULL UNIQUE,
    service       TEXT NOT NULL,
    response      TEXT NOT NULL,
    metadata_json JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '5 minutes')
);

CREATE INDEX IF NOT EXISTS idx_api_cache_key
    ON api_cache(cache_key);

CREATE INDEX IF NOT EXISTS idx_api_cache_expires
    ON api_cache(expires_at);
ALTER TABLE api_cache DISABLE ROW LEVEL SECURITY;

-- ── User Preferences ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_preferences (
    key   TEXT PRIMARY KEY,
    value JSONB NOT NULL
);
ALTER TABLE user_preferences DISABLE ROW LEVEL SECURITY;

-- ── Enable realtime for messages (for frontend subscriptions) ──
-- This publishes INSERT events on the messages table via Realtime
-- Uses IF NOT EXISTS so it's safe to re-run
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'messages'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE ONLY messages;
  END IF;
END
$$;