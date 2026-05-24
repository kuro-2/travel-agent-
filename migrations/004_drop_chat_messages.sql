-- ============================================================
-- Migration 004: Drop the old chat_messages table
-- The app now uses chat_exchanges (paired user+assistant rows).
-- chat_messages is unused — this cleans it up.
--
-- Run in: Supabase Dashboard → SQL Editor
-- ============================================================

DROP POLICY IF EXISTS "own_messages_select" ON public.chat_messages;
DROP POLICY IF EXISTS "own_messages_insert" ON public.chat_messages;
DROP POLICY IF EXISTS "own_messages_delete" ON public.chat_messages;

DROP TABLE IF EXISTS public.chat_messages;
