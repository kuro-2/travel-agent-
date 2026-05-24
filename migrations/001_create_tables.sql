-- ============================================================
-- Migration 001: Initial schema for Travel Agent
-- Run this in: Supabase Dashboard → SQL Editor → New query
-- ============================================================

-- ─── Chat Sessions ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Chat Messages ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Indexes for fast lookups ─────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id  ON public.chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session  ON public.chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id  ON public.chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created  ON public.chat_messages(created_at);

-- ─── Row Level Security ───────────────────────────────────────
-- Users can only see and modify their own data.
-- The Flask backend uses the service-role key which bypasses RLS,
-- but RLS still protects against any direct client-side access.

ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

-- chat_sessions policies
DROP POLICY IF EXISTS "own_sessions_select" ON public.chat_sessions;
DROP POLICY IF EXISTS "own_sessions_insert" ON public.chat_sessions;
DROP POLICY IF EXISTS "own_sessions_delete" ON public.chat_sessions;

CREATE POLICY "own_sessions_select" ON public.chat_sessions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "own_sessions_insert" ON public.chat_sessions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "own_sessions_delete" ON public.chat_sessions
    FOR DELETE USING (auth.uid() = user_id);

-- chat_messages policies
DROP POLICY IF EXISTS "own_messages_select" ON public.chat_messages;
DROP POLICY IF EXISTS "own_messages_insert" ON public.chat_messages;
DROP POLICY IF EXISTS "own_messages_delete" ON public.chat_messages;

CREATE POLICY "own_messages_select" ON public.chat_messages
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "own_messages_insert" ON public.chat_messages
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "own_messages_delete" ON public.chat_messages
    FOR DELETE USING (auth.uid() = user_id);

-- ─── Auto-update updated_at ──────────────────────────────────
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sessions_updated_at ON public.chat_sessions;
CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON public.chat_sessions
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
