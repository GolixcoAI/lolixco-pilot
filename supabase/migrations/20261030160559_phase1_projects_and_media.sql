-- LolixCopilot — Phase 1 Database Schema and Row Level Security
-- Tables: projects, media, analyses
-- Applies cleanly to Supabase PostgreSQL (fhfkjviishfvfyawfckh) and local test environments.

-- Ensure required extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Ensure core roles and auth schema exist (idempotent fallback for non-Supabase PostgreSQL test harnesses)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_namespace WHERE nspname = 'auth') THEN
        CREATE SCHEMA auth;
        CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID AS $func$
            SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::UUID;
        $func$ LANGUAGE sql STABLE;
    END IF;
END
$$;

-- 1. Projects Table
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name TEXT NOT NULL DEFAULT 'Untitled Cut',
    aspect_ratio TEXT NOT NULL DEFAULT '9:16',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Media Table
CREATE TABLE IF NOT EXISTS media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    original_filename TEXT NOT NULL,
    s3_object_key TEXT NOT NULL UNIQUE,
    content_type TEXT NOT NULL,
    declared_size_bytes BIGINT NOT NULL,
    verified_size_bytes BIGINT,
    duration_seconds DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'uploaded', 'verified', 'failed', 'expired')),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '7 days'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Analyses Table
CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    media_id UUID REFERENCES media(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    blueprint JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for performant lookup
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_media_project_id ON media(project_id);
CREATE INDEX IF NOT EXISTS idx_media_user_id ON media(user_id);
CREATE INDEX IF NOT EXISTS idx_media_expires_at ON media(expires_at);
CREATE INDEX IF NOT EXISTS idx_analyses_project_id ON analyses(project_id);
CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id);

-- Enable Row Level Security (RLS) on all tables
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE media ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;

-- 4. Explicit Grants for PostgREST Roles
GRANT ALL ON TABLE projects TO authenticated, service_role;
GRANT ALL ON TABLE media TO authenticated, service_role;
GRANT ALL ON TABLE analyses TO authenticated, service_role;

-- 5. Row Level Security Policies
-- Scoped strictly to authenticated users (including anonymous Supabase users where auth.uid() is populated).
-- Cross-user access is prohibited: anonymous user A cannot access anonymous user B's records.

-- Projects policies
DROP POLICY IF EXISTS "Users can only select own projects" ON projects;
CREATE POLICY "Users can only select own projects"
    ON projects FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can only insert own projects" ON projects;
CREATE POLICY "Users can only insert own projects"
    ON projects FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can only update own projects" ON projects;
CREATE POLICY "Users can only update own projects"
    ON projects FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can only delete own projects" ON projects;
CREATE POLICY "Users can only delete own projects"
    ON projects FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);

-- Media policies
DROP POLICY IF EXISTS "Users can only select own media" ON media;
CREATE POLICY "Users can only select own media"
    ON media FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can only insert own media" ON media;
CREATE POLICY "Users can only insert own media"
    ON media FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can only update own media" ON media;
CREATE POLICY "Users can only update own media"
    ON media FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can only delete own media" ON media;
CREATE POLICY "Users can only delete own media"
    ON media FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);

-- Analyses policies
DROP POLICY IF EXISTS "Users can only select own analyses" ON analyses;
CREATE POLICY "Users can only select own analyses"
    ON analyses FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can only insert own analyses" ON analyses;
CREATE POLICY "Users can only insert own analyses"
    ON analyses FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can only update own analyses" ON analyses;
CREATE POLICY "Users can only update own analyses"
    ON analyses FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can only delete own analyses" ON analyses;
CREATE POLICY "Users can only delete own analyses"
    ON analyses FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);
