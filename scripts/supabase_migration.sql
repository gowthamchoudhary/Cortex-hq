-- ============================================================================
-- Cortex-HQ: SQLite → Supabase migration
--
-- Run this in the Supabase SQL Editor (https://supabase.com/dashboard)
-- or via the Supabase CLI:  supabase db push
--
-- This creates all tables that were previously stored in local SQLite files
-- (auth/user_brains.db, identity/identity.db, deploy/agents.db).
-- ============================================================================

-- -------------------------------------------------------------------
-- 1. user_brains  (was: auth/user_brains.db)
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_brains (
    user_id         TEXT NOT NULL,
    collection_name TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'member',
    created_at      INTEGER NOT NULL DEFAULT (extract(epoch from now())),
    PRIMARY KEY (user_id, collection_name)
);

-- -------------------------------------------------------------------
-- 2. user_identities  (was: auth/user_brains.db)
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_identities (
    user_id    TEXT PRIMARY KEY,
    email      TEXT UNIQUE,
    phone      TEXT UNIQUE,
    created_at INTEGER NOT NULL DEFAULT (extract(epoch from now()))
);

-- -------------------------------------------------------------------
-- 3. employees  (was: identity/identity.db)
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS employees (
    collection          TEXT NOT NULL,
    employee_id         TEXT NOT NULL,
    name                TEXT NOT NULL,
    work_email          TEXT NOT NULL,
    department          TEXT,
    role_title          TEXT,
    cortex_role         TEXT NOT NULL DEFAULT 'member',
    manager_employee_id TEXT,
    work_email_verified INTEGER NOT NULL DEFAULT 0,
    created_at          INTEGER NOT NULL DEFAULT (extract(epoch from now())),
    updated_at          INTEGER NOT NULL DEFAULT (extract(epoch from now())),
    PRIMARY KEY (collection, employee_id),
    UNIQUE (collection, work_email)
);

-- -------------------------------------------------------------------
-- 4. external_identities  (was: identity/identity.db)
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS external_identities (
    collection       TEXT NOT NULL,
    platform         TEXT NOT NULL,
    platform_user_id TEXT NOT NULL,
    employee_id      TEXT NOT NULL,
    created_at       INTEGER NOT NULL DEFAULT (extract(epoch from now())),
    PRIMARY KEY (collection, platform, platform_user_id)
);

-- -------------------------------------------------------------------
-- 5. invitations  (was: identity/identity.db)
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invitations (
    token       TEXT PRIMARY KEY,
    collection  TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  INTEGER NOT NULL DEFAULT (extract(epoch from now())),
    expires_at  INTEGER NOT NULL
);

-- -------------------------------------------------------------------
-- 6. email_verifications  (was: identity/identity.db)
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_verifications (
    email       TEXT NOT NULL,
    code        TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    created_at  INTEGER NOT NULL DEFAULT (extract(epoch from now())),
    expires_at  INTEGER NOT NULL,
    PRIMARY KEY (email, code)
);

-- -------------------------------------------------------------------
-- 7. agents  (was: deploy/agents.db)
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agents (
    agent_id     TEXT PRIMARY KEY,
    agent_name   TEXT NOT NULL,
    collection   TEXT NOT NULL,
    role_default TEXT NOT NULL DEFAULT 'member',
    created_at   INTEGER NOT NULL DEFAULT (extract(epoch from now()))
);

-- -------------------------------------------------------------------
-- 8. deployments  (was: deploy/agents.db)
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS deployments (
    agent_id    TEXT NOT NULL,
    platform    TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'pending',
    deployed_at INTEGER NOT NULL DEFAULT (extract(epoch from now())),
    PRIMARY KEY (agent_id, platform)
);

-- -------------------------------------------------------------------
-- 9. oauth_tokens  (was: oauth/oauth.db)
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS oauth_tokens (
    collection   TEXT NOT NULL,
    provider     TEXT NOT NULL,
    token_type   TEXT NOT NULL DEFAULT 'user',
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at   INTEGER,
    scopes       TEXT,
    created_at   INTEGER NOT NULL DEFAULT (extract(epoch from now())),
    updated_at   INTEGER NOT NULL DEFAULT (extract(epoch from now())),
    PRIMARY KEY (collection, provider, token_type)
);

-- -------------------------------------------------------------------
-- Indexes for common query patterns
-- -------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_user_brains_user ON user_brains (user_id);
CREATE INDEX IF NOT EXISTS idx_user_brains_collection ON user_brains (collection_name);
CREATE INDEX IF NOT EXISTS idx_employees_collection ON employees (collection);
CREATE INDEX IF NOT EXISTS idx_employees_email ON employees (collection, work_email);
CREATE INDEX IF NOT EXISTS idx_invitations_collection ON invitations (collection);
CREATE INDEX IF NOT EXISTS idx_invitations_status ON invitations (status);
CREATE INDEX IF NOT EXISTS idx_agents_collection ON agents (collection);
CREATE INDEX IF NOT EXISTS idx_deployments_agent ON deployments (agent_id);
