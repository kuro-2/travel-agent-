-- ============================================================
-- Migration 002: User profiles table
-- Run this AFTER 001_create_tables.sql
-- Supabase Dashboard → SQL Editor → New query → paste → Run
-- ============================================================

-- ─── Profiles ────────────────────────────────────────────────
-- One row per auth.users entry. Stores display info and auth provider.
CREATE TABLE IF NOT EXISTS public.profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name   TEXT        NOT NULL DEFAULT '',
    avatar_url  TEXT        NOT NULL DEFAULT '',
    provider    TEXT        NOT NULL DEFAULT 'email',  -- 'email' | 'google'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Indexes ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_profiles_id ON public.profiles(id);

-- ─── Row Level Security ───────────────────────────────────────
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "own_profile_select" ON public.profiles;
DROP POLICY IF EXISTS "own_profile_update" ON public.profiles;

-- Users can read their own profile
CREATE POLICY "own_profile_select" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

-- Users can update their own profile (but not change id)
CREATE POLICY "own_profile_update" ON public.profiles
    FOR UPDATE USING (auth.uid() = id) WITH CHECK (auth.uid() = id);

-- ─── Auto-create profile on new user signup ───────────────────
-- This trigger fires for BOTH email/password AND Google OAuth signups.
-- It reads full_name and avatar_url out of raw_user_meta_data which
-- Supabase populates from the Google token automatically.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER          -- runs as the DB owner so it can INSERT into profiles
SET search_path = public  -- prevents search path injection
AS $$
BEGIN
    INSERT INTO public.profiles (id, full_name, avatar_url, provider)
    VALUES (
        NEW.id,
        COALESCE(
            NEW.raw_user_meta_data->>'full_name',
            NEW.raw_user_meta_data->>'name',
            ''
        ),
        COALESCE(NEW.raw_user_meta_data->>'avatar_url', ''),
        COALESCE(NEW.raw_app_meta_data->>'provider', 'email')
    )
    ON CONFLICT (id) DO UPDATE
        SET
            full_name  = COALESCE(EXCLUDED.full_name,  profiles.full_name),
            avatar_url = COALESCE(EXCLUDED.avatar_url, profiles.avatar_url),
            provider   = EXCLUDED.provider,
            updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ─── updated_at auto-stamp ────────────────────────────────────
DROP TRIGGER IF EXISTS trg_profiles_updated_at ON public.profiles;
CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
