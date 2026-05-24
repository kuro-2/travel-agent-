-- ============================================================
-- Migration 003: Replace chat_messages with paired message rows
-- Each row now stores one full exchange: the user prompt and
-- the assistant reply together. This makes history retrieval
-- and display much simpler.
--
-- Run in: Supabase Dashboard → SQL Editor → New query
-- Run AFTER 001 and 002.
-- ============================================================

-- ─── New paired table ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.chat_exchanges (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    user_id         UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    user_message    TEXT        NOT NULL,
    assistant_reply TEXT        NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Indexes ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_exchanges_session   ON public.chat_exchanges(session_id);
CREATE INDEX IF NOT EXISTS idx_exchanges_user_id   ON public.chat_exchanges(user_id);
CREATE INDEX IF NOT EXISTS idx_exchanges_created   ON public.chat_exchanges(created_at);

-- ─── Row Level Security ───────────────────────────────────────
ALTER TABLE public.chat_exchanges ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "own_exchanges_select" ON public.chat_exchanges;
DROP POLICY IF EXISTS "own_exchanges_insert" ON public.chat_exchanges;
DROP POLICY IF EXISTS "own_exchanges_delete" ON public.chat_exchanges;

CREATE POLICY "own_exchanges_select" ON public.chat_exchanges
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "own_exchanges_insert" ON public.chat_exchanges
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "own_exchanges_delete" ON public.chat_exchanges
    FOR DELETE USING (auth.uid() = user_id);
