# SQLite schema translation map

Status: source-complete DDL ledger; per-constraint implementation and behavioral verification pending.

UUID → TEXT retaining wire format; timestamptz → UTC canonical text; boolean → INTEGER CHECK 0/1; json/jsonb → validated JSON TEXT; bytea → BLOB; arrays → child relation tables where referenced, otherwise JSON with explicit order semantics. Translate PostgreSQL enum constraints to CHECK or lookup tables. Preserve NULL and default distinctions. Preserve every UNIQUE/FK/ON DELETE below; enable foreign_keys for each connection. PostgreSQL sequences require explicit per-workspace atomic allocation. Partial indexes require matching SQLite predicates. GIN/trigram/tsvector search requires separately tested tokenization/ranking; no claimed equivalence. FOR UPDATE/SKIP LOCKED → bounded short SQLite claim transactions with owner/fencing predicates. SQL functions/triggers/RLS need explicit repository authorization and migration equivalents.

## server/go/migrations/001_init.up.sql

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users
CREATE TABLE "user" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Workspaces
CREATE TABLE workspace (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Members (user <-> workspace)
CREATE TABLE member (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'member')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(workspace_id, user_id)
);

-- Agents
CREATE TABLE agent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    avatar_url TEXT,
    runtime_mode TEXT NOT NULL CHECK (runtime_mode IN ('local', 'cloud')),
    runtime_config JSONB NOT NULL DEFAULT '{}',
    visibility TEXT NOT NULL DEFAULT 'workspace' CHECK (visibility IN ('workspace', 'private')),
    status TEXT NOT NULL DEFAULT 'offline' CHECK (status IN ('idle', 'working', 'blocked', 'error', 'offline')),
    max_concurrent_tasks INT NOT NULL DEFAULT 1,
    owner_id UUID REFERENCES "user"(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Issues
CREATE TABLE issue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'backlog'
        CHECK (status IN ('backlog', 'todo', 'in_progress', 'in_review', 'done', 'blocked', 'cancelled')),
    priority TEXT NOT NULL DEFAULT 'none'
        CHECK (priority IN ('urgent', 'high', 'medium', 'low', 'none')),
    assignee_type TEXT CHECK (assignee_type IN ('member', 'agent')),
    assignee_id UUID,
    creator_type TEXT NOT NULL CHECK (creator_type IN ('member', 'agent')),
    creator_id UUID NOT NULL,
    parent_issue_id UUID REFERENCES issue(id) ON DELETE SET NULL,
    acceptance_criteria JSONB NOT NULL DEFAULT '[]',
    context_refs JSONB NOT NULL DEFAULT '[]',
    position FLOAT NOT NULL DEFAULT 0,
    due_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Issue labels
CREATE TABLE issue_label (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT NOT NULL
);

CREATE TABLE issue_to_label (
    issue_id UUID NOT NULL REFERENCES issue(id) ON DELETE CASCADE,
    label_id UUID NOT NULL REFERENCES issue_label(id) ON DELETE CASCADE,
    PRIMARY KEY (issue_id, label_id)
);

-- Issue dependencies
CREATE TABLE issue_dependency (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id UUID NOT NULL REFERENCES issue(id) ON DELETE CASCADE,
    depends_on_issue_id UUID NOT NULL REFERENCES issue(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('blocks', 'blocked_by', 'related'))
);

-- Comments
CREATE TABLE comment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id UUID NOT NULL REFERENCES issue(id) ON DELETE CASCADE,
    author_type TEXT NOT NULL CHECK (author_type IN ('member', 'agent')),
    author_id UUID NOT NULL,
    content TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'comment'
        CHECK (type IN ('comment', 'status_change', 'progress_update', 'system')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Inbox items
CREATE TABLE inbox_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    recipient_type TEXT NOT NULL CHECK (recipient_type IN ('member', 'agent')),
    recipient_id UUID NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info'
        CHECK (severity IN ('action_required', 'attention', 'info')),
    issue_id UUID REFERENCES issue(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT,
    read BOOLEAN NOT NULL DEFAULT FALSE,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Agent task queue
CREATE TABLE agent_task_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    issue_id UUID NOT NULL REFERENCES issue(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'dispatched', 'running', 'completed', 'failed', 'cancelled')),
    priority INT NOT NULL DEFAULT 0,
    dispatched_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Daemon connections
CREATE TABLE daemon_connection (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    daemon_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'disconnected'
        CHECK (status IN ('connected', 'disconnected')),
    last_heartbeat_at TIMESTAMPTZ,
    runtime_info JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Activity log
CREATE TABLE activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    issue_id UUID REFERENCES issue(id) ON DELETE CASCADE,
    actor_type TEXT CHECK (actor_type IN ('member', 'agent', 'system')),
    actor_id UUID,
    action TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_issue_workspace ON issue(workspace_id);
CREATE INDEX idx_issue_assignee ON issue(assignee_type, assignee_id);
CREATE INDEX idx_issue_status ON issue(workspace_id, status);
CREATE INDEX idx_issue_parent ON issue(parent_issue_id);
CREATE INDEX idx_comment_issue ON comment(issue_id);
CREATE INDEX idx_inbox_recipient ON inbox_item(recipient_type, recipient_id, read);
CREATE INDEX idx_agent_task_queue_agent ON agent_task_queue(agent_id, status);
CREATE INDEX idx_activity_log_issue ON activity_log(issue_id);
CREATE INDEX idx_member_workspace ON member(workspace_id);
CREATE INDEX idx_agent_workspace ON agent(workspace_id);

```

## server/go/migrations/002_agent_config.up.sql

```sql
-- Add agent configuration columns: skills, tools, triggers
ALTER TABLE agent
    ADD COLUMN description TEXT NOT NULL DEFAULT '',
    ADD COLUMN skills TEXT NOT NULL DEFAULT '',
    ADD COLUMN tools JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN triggers JSONB NOT NULL DEFAULT '[]';

```

## server/go/migrations/003_task_context.up.sql

```sql
-- Add context snapshot to agent tasks so daemons have everything needed to execute
ALTER TABLE agent_task_queue
    ADD COLUMN context JSONB;

-- Partial index for efficient daemon polling of pending tasks
CREATE INDEX idx_agent_task_queue_pending
    ON agent_task_queue(agent_id, priority DESC, created_at ASC)
    WHERE status IN ('queued', 'dispatched');

-- Unique constraint for daemon connection upsert
ALTER TABLE daemon_connection
    ADD CONSTRAINT uq_daemon_agent UNIQUE (agent_id, daemon_id);

```

## server/go/migrations/004_agent_runtime_loop.up.sql

```sql
CREATE TABLE agent_runtime (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    daemon_id TEXT,
    name TEXT NOT NULL,
    runtime_mode TEXT NOT NULL CHECK (runtime_mode IN ('local', 'cloud')),
    provider TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offline' CHECK (status IN ('online', 'offline')),
    device_info TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, daemon_id, provider)
);

ALTER TABLE agent
    ADD COLUMN runtime_id UUID;

INSERT INTO agent_runtime (
    workspace_id,
    daemon_id,
    name,
    runtime_mode,
    provider,
    status,
    device_info,
    metadata,
    last_seen_at,
    created_at,
    updated_at
)
SELECT
    a.workspace_id,
    NULL,
    COALESCE(NULLIF(a.runtime_config->>'runtime_name', ''), a.name || ' Runtime'),
    a.runtime_mode,
    COALESCE(
        NULLIF(a.runtime_config->>'provider', ''),
        CASE
            WHEN a.runtime_mode = 'cloud' THEN 'workpal_agent'
            ELSE 'legacy_local'
        END
    ),
    CASE
        WHEN a.status = 'offline' THEN 'offline'
        ELSE 'online'
    END,
    COALESCE(
        NULLIF(a.runtime_config->>'runtime_name', ''),
        CASE
            WHEN a.runtime_mode = 'cloud' THEN 'Cloud runtime'
            ELSE 'Local runtime'
        END
    ),
    jsonb_build_object('migrated_agent_id', a.id::text),
    CASE
        WHEN a.status = 'offline' THEN NULL
        ELSE a.updated_at
    END,
    a.created_at,
    a.updated_at
FROM agent a;

UPDATE agent a
SET runtime_id = ar.id
FROM agent_runtime ar
WHERE ar.metadata->>'migrated_agent_id' = a.id::text;

ALTER TABLE agent
    ALTER COLUMN runtime_id SET NOT NULL,
    ADD CONSTRAINT agent_runtime_id_fkey
        FOREIGN KEY (runtime_id) REFERENCES agent_runtime(id) ON DELETE RESTRICT;

ALTER TABLE agent_task_queue
    ADD COLUMN runtime_id UUID;

UPDATE agent_task_queue atq
SET runtime_id = a.runtime_id
FROM agent a
WHERE a.id = atq.agent_id;

ALTER TABLE agent_task_queue
    ALTER COLUMN runtime_id SET NOT NULL,
    ADD CONSTRAINT agent_task_queue_runtime_id_fkey
        FOREIGN KEY (runtime_id) REFERENCES agent_runtime(id) ON DELETE CASCADE;

CREATE INDEX idx_agent_runtime_workspace ON agent_runtime(workspace_id);
CREATE INDEX idx_agent_runtime_status ON agent_runtime(workspace_id, status);
CREATE INDEX idx_agent_task_queue_runtime_pending
    ON agent_task_queue(runtime_id, priority DESC, created_at ASC)
    WHERE status IN ('queued', 'dispatched');

```

## server/go/migrations/005_daemon_pairing.up.sql

```sql
CREATE TABLE daemon_pairing_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token TEXT NOT NULL UNIQUE,
    daemon_id TEXT NOT NULL,
    device_name TEXT NOT NULL,
    runtime_name TEXT NOT NULL,
    runtime_type TEXT NOT NULL,
    runtime_version TEXT NOT NULL DEFAULT '',
    workspace_id UUID REFERENCES workspace(id) ON DELETE CASCADE,
    approved_by UUID REFERENCES "user"(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'claimed', 'expired')),
    approved_at TIMESTAMPTZ,
    claimed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_daemon_pairing_session_token ON daemon_pairing_session (token);
CREATE INDEX idx_daemon_pairing_session_status_expires ON daemon_pairing_session (status, expires_at);

```

## server/go/migrations/006_workspace_context.up.sql

```sql
ALTER TABLE workspace ADD COLUMN context TEXT;

```

## server/go/migrations/007_drop_issue_repository.up.sql

```sql
ALTER TABLE issue DROP COLUMN IF EXISTS repository;

```

## server/go/migrations/008_structured_skills.up.sql

```sql
-- Structured Skills: workspace-level skill entities with supporting files
-- and many-to-many agent-skill associations.

CREATE TABLE skill (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    config JSONB NOT NULL DEFAULT '{}',
    created_by UUID REFERENCES "user"(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(workspace_id, name)
);

CREATE TABLE skill_file (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skill(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(skill_id, path)
);

CREATE TABLE agent_skill (
    agent_id UUID NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES skill(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (agent_id, skill_id)
);

-- Remove old text-based skills column from agent
ALTER TABLE agent DROP COLUMN IF EXISTS skills;

-- Indexes
CREATE INDEX idx_skill_workspace ON skill(workspace_id);
CREATE INDEX idx_skill_file_skill ON skill_file(skill_id);
CREATE INDEX idx_agent_skill_skill ON agent_skill(skill_id);
CREATE INDEX idx_agent_skill_agent ON agent_skill(agent_id);

```

## server/go/migrations/009_verification_code.up.sql

```sql
CREATE TABLE verification_code (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    code TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_verification_code_email ON verification_code(email, used, expires_at);

```

## server/go/migrations/010_verification_code_attempts.up.sql

```sql
ALTER TABLE verification_code ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;

```

## server/go/migrations/011_personal_access_tokens.up.sql

```sql
CREATE TABLE personal_access_token (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    token_prefix TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pat_user ON personal_access_token(user_id, revoked);
CREATE UNIQUE INDEX idx_pat_token_hash ON personal_access_token(token_hash);

```

## server/go/migrations/012_inbox_actor.up.sql

```sql
ALTER TABLE inbox_item ADD COLUMN IF NOT EXISTS actor_type TEXT;
ALTER TABLE inbox_item ADD COLUMN IF NOT EXISTS actor_id UUID;

```

## server/go/migrations/013_runtime_usage.up.sql

```sql
CREATE TABLE runtime_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    runtime_id UUID NOT NULL REFERENCES agent_runtime(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    cache_read_tokens BIGINT NOT NULL DEFAULT 0,
    cache_write_tokens BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (runtime_id, date, provider, model)
);

CREATE INDEX idx_runtime_usage_runtime_date ON runtime_usage(runtime_id, date DESC);

```

## server/go/migrations/014_workspace_repos.up.sql

```sql
ALTER TABLE workspace ADD COLUMN repos JSONB NOT NULL DEFAULT '[]';

```

## server/go/migrations/015_issue_subscriber.up.sql

```sql
-- Issue subscribers: tracks who is subscribed to notifications for an issue
CREATE TABLE issue_subscriber (
    issue_id   UUID NOT NULL REFERENCES issue(id) ON DELETE CASCADE,
    user_type  TEXT NOT NULL CHECK (user_type IN ('member', 'agent')),
    user_id    UUID NOT NULL,
    reason     TEXT NOT NULL CHECK (reason IN ('creator', 'assignee', 'commenter', 'mentioned', 'manual')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (issue_id, user_type, user_id)
);

CREATE INDEX idx_issue_subscriber_user ON issue_subscriber(user_type, user_id);

```

## server/go/migrations/016_backfill_subscribers.up.sql

```sql
-- Backfill creators as subscribers
INSERT INTO issue_subscriber (issue_id, user_type, user_id, reason)
SELECT id, creator_type, creator_id, 'creator'
FROM issue
ON CONFLICT DO NOTHING;

-- Backfill assignees as subscribers
INSERT INTO issue_subscriber (issue_id, user_type, user_id, reason)
SELECT id, assignee_type, assignee_id, 'assignee'
FROM issue
WHERE assignee_type IS NOT NULL AND assignee_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- Backfill commenters as subscribers
INSERT INTO issue_subscriber (issue_id, user_type, user_id, reason)
SELECT DISTINCT c.issue_id, c.author_type, c.author_id, 'commenter'
FROM comment c
ON CONFLICT DO NOTHING;

```

## server/go/migrations/017_comment_parent_id.up.sql

```sql
ALTER TABLE comment ADD COLUMN parent_id UUID REFERENCES comment(id) ON DELETE SET NULL;

```

## server/go/migrations/018_comment_parent_cascade.up.sql

```sql
ALTER TABLE comment DROP CONSTRAINT IF EXISTS comment_parent_id_fkey;
ALTER TABLE comment ADD CONSTRAINT comment_parent_id_fkey
    FOREIGN KEY (parent_id) REFERENCES comment(id) ON DELETE CASCADE;

```

## server/go/migrations/019_inbox_details.up.sql

```sql
ALTER TABLE inbox_item ADD COLUMN IF NOT EXISTS details JSONB DEFAULT '{}';

```

## server/go/migrations/020_issue_number.up.sql

```sql
-- Add issue_prefix and issue_counter to workspace for human-readable issue IDs.
ALTER TABLE workspace
    ADD COLUMN issue_prefix TEXT NOT NULL DEFAULT '',
    ADD COLUMN issue_counter INT NOT NULL DEFAULT 0;

-- Add per-workspace issue number.
ALTER TABLE issue
    ADD COLUMN number INT NOT NULL DEFAULT 0;

-- Backfill: generate issue_prefix from workspace name (first 3 uppercase chars).
UPDATE workspace SET issue_prefix = UPPER(
    LEFT(REGEXP_REPLACE(name, '[^a-zA-Z]', '', 'g'), 3)
);

-- Fallback for workspaces with empty prefix after cleanup.
UPDATE workspace SET issue_prefix = 'WS' WHERE issue_prefix = '';

-- Backfill: assign sequential numbers to existing issues per workspace.
WITH numbered AS (
    SELECT id, workspace_id,
           ROW_NUMBER() OVER (PARTITION BY workspace_id ORDER BY created_at ASC) AS rn
    FROM issue
)
UPDATE issue SET number = numbered.rn
FROM numbered WHERE issue.id = numbered.id;

-- Update workspace counters to match.
UPDATE workspace SET issue_counter = COALESCE(
    (SELECT MAX(number) FROM issue WHERE issue.workspace_id = workspace.id), 0
);

-- Add unique constraint.
ALTER TABLE issue ADD CONSTRAINT uq_issue_workspace_number UNIQUE (workspace_id, number);

-- Index for fast lookup by workspace + number.
CREATE INDEX idx_issue_workspace_number ON issue(workspace_id, number);

```

## server/go/migrations/020_task_session.up.sql

```sql
-- Add session persistence columns to agent_task_queue.
-- session_id: the Claude Code session ID returned after execution.
-- work_dir: the working directory used during execution.
-- These enable resuming the same Claude Code session across multiple tasks
-- for the same (agent, issue) pair via --resume <session_id>.
ALTER TABLE agent_task_queue ADD COLUMN session_id TEXT;
ALTER TABLE agent_task_queue ADD COLUMN work_dir TEXT;

```

## server/go/migrations/021_agent_instructions.up.sql

```sql
ALTER TABLE agent ADD COLUMN instructions TEXT NOT NULL DEFAULT '';

```

## server/go/migrations/022_task_lifecycle_guards.up.sql

```sql
-- Prevent duplicate pending tasks for the same issue (coalescing queue safety net).
-- At most one queued/dispatched task per issue at any time.
CREATE UNIQUE INDEX idx_one_pending_task_per_issue
    ON agent_task_queue (issue_id)
    WHERE status IN ('queued', 'dispatched');

```

## server/go/migrations/023_agent_concurrency_default.up.sql

```sql
ALTER TABLE agent ALTER COLUMN max_concurrent_tasks SET DEFAULT 6;
UPDATE agent SET max_concurrent_tasks = 6 WHERE max_concurrent_tasks = 1;

```

## server/go/migrations/024_backfill_empty_issue_prefix.up.sql

```sql
-- Backfill workspaces that have an empty issue_prefix (e.g. auto-created
-- during first login before the prefix was wired up in ensureUserWorkspace).
UPDATE workspace SET issue_prefix = UPPER(
    LEFT(REGEXP_REPLACE(name, '[^a-zA-Z]', '', 'g'), 3)
) WHERE issue_prefix = '';

-- Fallback for workspaces whose name has no alphabetic characters.
UPDATE workspace SET issue_prefix = 'WS' WHERE issue_prefix = '';

```

## server/go/migrations/025_comment_workspace_id.up.sql

```sql
ALTER TABLE comment ADD COLUMN workspace_id UUID REFERENCES workspace(id) ON DELETE CASCADE;

-- Backfill from issue.workspace_id
UPDATE comment SET workspace_id = issue.workspace_id
FROM issue WHERE comment.issue_id = issue.id;

-- Make non-nullable after backfill
ALTER TABLE comment ALTER COLUMN workspace_id SET NOT NULL;

```

## server/go/migrations/026_comment_reactions.up.sql

```sql
CREATE TABLE comment_reaction (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID NOT NULL REFERENCES comment(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('member', 'agent')),
    actor_id UUID NOT NULL,
    emoji TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (comment_id, actor_type, actor_id, emoji)
);

CREATE INDEX idx_comment_reaction_comment_id ON comment_reaction(comment_id);

```

## server/go/migrations/026_task_messages.up.sql

```sql
CREATE TABLE task_message (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES agent_task_queue(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    tool TEXT,
    content TEXT,
    input JSONB,
    output TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_task_message_task_id_seq ON task_message(task_id, seq);

```

## server/go/migrations/027_issue_reactions.up.sql

```sql
CREATE TABLE issue_reaction (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id UUID NOT NULL REFERENCES issue(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('member', 'agent')),
    actor_id UUID NOT NULL,
    emoji TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (issue_id, actor_type, actor_id, emoji)
);

CREATE INDEX idx_issue_reaction_issue_id ON issue_reaction(issue_id);

```

## server/go/migrations/028_task_trigger_comment.up.sql

```sql
ALTER TABLE agent_task_queue ADD COLUMN trigger_comment_id UUID REFERENCES comment(id) ON DELETE SET NULL;

```

## server/go/migrations/029_attachment.up.sql

```sql
CREATE TABLE attachment (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    issue_id      UUID REFERENCES issue(id) ON DELETE CASCADE,
    comment_id    UUID REFERENCES comment(id) ON DELETE CASCADE,
    uploader_type TEXT NOT NULL CHECK (uploader_type IN ('member', 'agent')),
    uploader_id   UUID NOT NULL,
    filename      TEXT NOT NULL,
    url           TEXT NOT NULL,
    content_type  TEXT NOT NULL,
    size_bytes    BIGINT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_attachment_issue ON attachment(issue_id) WHERE issue_id IS NOT NULL;
CREATE INDEX idx_attachment_comment ON attachment(comment_id) WHERE comment_id IS NOT NULL;
CREATE INDEX idx_attachment_workspace ON attachment(workspace_id);

```

## server/go/migrations/029_daemon_token.up.sql

```sql
CREATE TABLE daemon_token (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    daemon_id TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_daemon_token_hash ON daemon_token(token_hash);
CREATE INDEX idx_daemon_token_workspace_daemon ON daemon_token(workspace_id, daemon_id);

```

## server/go/migrations/029_drop_daemon_pairing.up.sql

```sql
DROP TABLE IF EXISTS daemon_pairing_session;

```

## server/go/migrations/030_agent_default_private.up.sql

```sql
ALTER TABLE agent ALTER COLUMN visibility SET DEFAULT 'private';

```

## server/go/migrations/031_agent_archive.up.sql

```sql
-- Add archive support to agents (soft-delete replacement).
-- archived_at IS NOT NULL means the agent is archived.
ALTER TABLE agent ADD COLUMN archived_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE agent ADD COLUMN archived_by UUID DEFAULT NULL REFERENCES "user"(id);

```

## server/go/migrations/032_drop_agent_triggers.up.sql

```sql
-- Remove the triggers and tools columns from agent table.
-- Trigger behavior (on_assign, on_comment, on_mention) is now always enabled (hardcoded).
-- Tools was a placeholder field never used at runtime.
ALTER TABLE agent DROP COLUMN IF EXISTS triggers;
ALTER TABLE agent DROP COLUMN IF EXISTS tools;

```

## server/go/migrations/032_issue_search_index.up.sql

```sql
-- Enable pg_bigm extension for bigram-based full-text search (CJK-friendly).
-- Skips gracefully if pg_bigm is not available (e.g. CI environments).
DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS pg_bigm;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pg_bigm not available, skipping bigram indexes';
END
$$;

-- GIN indexes on issue title/description for LIKE '%keyword%' queries.
-- Only created when pg_bigm is installed.
DO $$
BEGIN
  CREATE INDEX idx_issue_title_bigm ON issue USING gin (title gin_bigm_ops);
  CREATE INDEX idx_issue_description_bigm ON issue USING gin (COALESCE(description, '') gin_bigm_ops);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'skipping bigram indexes (pg_bigm not installed)';
END
$$;

```

## server/go/migrations/032_runtime_owner.up.sql

```sql
ALTER TABLE agent_runtime ADD COLUMN owner_id UUID REFERENCES "user"(id);

-- Backfill: set existing runtimes' owner to the workspace owner
UPDATE agent_runtime ar
SET owner_id = (
    SELECT m.user_id FROM member m
    WHERE m.workspace_id = ar.workspace_id AND m.role = 'owner'
    LIMIT 1
);

```

## server/go/migrations/032_task_usage.up.sql

```sql
CREATE TABLE task_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES agent_task_queue(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL,
    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    cache_read_tokens BIGINT NOT NULL DEFAULT 0,
    cache_write_tokens BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, provider, model)
);

CREATE INDEX idx_task_usage_task_id ON task_usage(task_id);

```

## server/go/migrations/033_chat.up.sql

```sql
-- Add chat session and chat message tables for the agent chat feature.

-- chat_session: persistent chat between a user and an agent.
CREATE TABLE chat_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    creator_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '',
    session_id TEXT,
    work_dir TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_chat_session_workspace ON chat_session(workspace_id);
CREATE INDEX idx_chat_session_creator ON chat_session(creator_id, workspace_id);

-- chat_message: individual messages in a chat session.
CREATE TABLE chat_message (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_session_id UUID NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    task_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_chat_message_session ON chat_message(chat_session_id, created_at);

-- Make issue_id nullable on agent_task_queue so chat tasks don't need an issue.
ALTER TABLE agent_task_queue ALTER COLUMN issue_id DROP NOT NULL;

-- Add chat_session_id to agent_task_queue for chat tasks.
ALTER TABLE agent_task_queue ADD COLUMN chat_session_id UUID REFERENCES chat_session(id) ON DELETE SET NULL;

```

## server/go/migrations/033_comment_search_index.up.sql

```sql
-- GIN index on comment content for LIKE '%keyword%' queries (pg_bigm).
-- Only created when pg_bigm is installed.
DO $$
BEGIN
  CREATE INDEX idx_comment_content_bigm ON comment USING gin (content gin_bigm_ops);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'skipping bigram index on comment (pg_bigm not installed)';
END
$$;

```

## server/go/migrations/034_projects.up.sql

```sql
-- Project table
CREATE TABLE project (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    status TEXT NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'in_progress', 'paused', 'completed', 'cancelled')),
    lead_type TEXT CHECK (lead_type IN ('member', 'agent')),
    lead_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_project_workspace ON project(workspace_id);

-- Add project_id to issue
ALTER TABLE issue ADD COLUMN project_id UUID REFERENCES project(id) ON DELETE SET NULL;
CREATE INDEX idx_issue_project ON issue(project_id);

```

## server/go/migrations/035_project_priority.up.sql

```sql
ALTER TABLE project ADD COLUMN priority TEXT NOT NULL DEFAULT 'none'
    CHECK (priority IN ('urgent', 'high', 'medium', 'low', 'none'));

```

## server/go/migrations/035_task_queue_issue_id_index.up.sql

```sql
-- Add a general index on agent_task_queue(issue_id) to support aggregation
-- queries like GetIssueUsageSummary that scan across all task statuses.
-- (Migration 022 only covers queued/dispatched rows via a partial index.)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_issue_id
    ON agent_task_queue (issue_id);

```

## server/go/migrations/036_search_index_lower.up.sql

```sql
-- Rebuild pg_bigm GIN indexes on LOWER() expressions so that
-- LOWER(column) LIKE pattern queries can utilize them.
-- pg_bigm 1.2 (RDS) does not support ILIKE index scans;
-- LOWER(col) LIKE LOWER(pattern) is the compatible alternative.

-- Drop old indexes that were built on raw (non-lowered) columns.
DROP INDEX IF EXISTS idx_issue_title_bigm;
DROP INDEX IF EXISTS idx_issue_description_bigm;
DROP INDEX IF EXISTS idx_comment_content_bigm;

-- Recreate indexes on LOWER() expressions.
-- Wrapped in exception handler so CI environments without pg_bigm still pass.
DO $$
BEGIN
  CREATE INDEX idx_issue_title_bigm ON issue USING gin (LOWER(title) gin_bigm_ops);
  CREATE INDEX idx_issue_description_bigm ON issue USING gin (LOWER(COALESCE(description, '')) gin_bigm_ops);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'skipping bigram indexes on issue (pg_bigm not installed)';
END
$$;

DO $$
BEGIN
  CREATE INDEX idx_comment_content_bigm ON comment USING gin (LOWER(content) gin_bigm_ops);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'skipping bigram index on comment (pg_bigm not installed)';
END
$$;

```

## server/go/migrations/037_fix_pending_task_unique_index.up.sql

```sql
-- Fix: the old index only allowed one pending task per issue across ALL agents.
-- This caused different agents' pending tasks to block each other.
-- Change to per-(issue, agent) so each agent can independently have one pending task.
DROP INDEX IF EXISTS idx_one_pending_task_per_issue;

CREATE UNIQUE INDEX idx_one_pending_task_per_issue_agent
    ON agent_task_queue (issue_id, agent_id)
    WHERE status IN ('queued', 'dispatched');

```

## server/go/migrations/038_pinned_items.up.sql

```sql
-- Pinned items: per-user quick-access items in the sidebar
CREATE TABLE pinned_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL CHECK (item_type IN ('issue', 'project')),
    item_id UUID NOT NULL,
    position FLOAT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, user_id, item_type, item_id)
);

CREATE INDEX idx_pinned_item_user_ws ON pinned_item (workspace_id, user_id, position);

```

## server/go/migrations/039_project_search_index.up.sql

```sql
-- Add GIN bigram indexes on project title and description for search.
DO $$
BEGIN
  CREATE INDEX idx_project_title_bigm ON project USING gin (LOWER(title) gin_bigm_ops);
  CREATE INDEX idx_project_description_bigm ON project USING gin (LOWER(COALESCE(description, '')) gin_bigm_ops);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'skipping bigram indexes on project (pg_bigm not installed)';
END
$$;

```

## server/go/migrations/040_agent_custom_env.up.sql

```sql
-- Add custom_env column to agent table for user-configurable environment
-- variables that get injected into the agent subprocess at launch time.
-- Supports router/proxy (ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL),
-- Bedrock (CLAUDE_CODE_USE_BEDROCK + AWS creds), and Vertex AI modes.
ALTER TABLE agent ADD COLUMN custom_env JSONB NOT NULL DEFAULT '{}';

```

## server/go/migrations/040_chat_unread_since.up.sql

```sql
-- Event-driven unread tracking for chat sessions.
--
-- Semantics: unread_since is the timestamp of the first unread assistant
-- message. It stays NULL while the session has no unread. It's SET when
-- an assistant reply lands and the column was NULL. It's RESET to NULL
-- when the user marks the session as read. Existing rows start as NULL,
-- meaning "no unread to track" — historic chats are not mass-flagged.
ALTER TABLE chat_session ADD COLUMN unread_since TIMESTAMPTZ;

-- GetPendingChatTask runs on every session open / switch and filters by
-- chat_session_id + in-flight status + orders by created_at. A partial
-- index on the in-flight subset keeps that query cheap as the queue grows.
CREATE INDEX IF NOT EXISTS idx_agent_task_queue_chat_pending
  ON agent_task_queue (chat_session_id, created_at DESC)
  WHERE chat_session_id IS NOT NULL
    AND status IN ('queued', 'dispatched', 'running');

```

## server/go/migrations/041_agent_custom_args.up.sql

```sql
-- Add custom_args column to agent table for user-configurable CLI arguments
-- that get appended to the agent subprocess command at launch time.
-- Stored as JSONB array of strings (e.g. ["--model", "o3", "--max-turns", "50"]).
ALTER TABLE agent ADD COLUMN custom_args JSONB NOT NULL DEFAULT '[]';

```

## server/go/migrations/041_workspace_invitation.up.sql

```sql
CREATE TABLE workspace_invitation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    inviter_id UUID NOT NULL REFERENCES "user"(id),
    invitee_email TEXT NOT NULL,
    invitee_user_id UUID REFERENCES "user"(id),
    role TEXT NOT NULL CHECK (role IN ('admin', 'member')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '7 days'
);

-- Only one pending invitation per workspace + email at a time.
CREATE UNIQUE INDEX idx_invitation_unique_pending
    ON workspace_invitation(workspace_id, invitee_email) WHERE status = 'pending';

-- Fast lookup of pending invitations for a user (by email or user_id).
CREATE INDEX idx_invitation_invitee_email ON workspace_invitation(invitee_email) WHERE status = 'pending';
CREATE INDEX idx_invitation_invitee_user  ON workspace_invitation(invitee_user_id) WHERE status = 'pending';

```

## server/go/migrations/042_autopilot.up.sql

```sql
-- Autopilot: scheduled/triggered automations that assign recurring work to AI Agents.

CREATE TABLE IF NOT EXISTS autopilot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    project_id UUID REFERENCES project(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    assignee_id UUID NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('urgent', 'high', 'medium', 'low', 'none')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'archived')),
    execution_mode TEXT NOT NULL DEFAULT 'create_issue'
        CHECK (execution_mode IN ('create_issue', 'run_only')),
    issue_title_template TEXT,
    concurrency_policy TEXT NOT NULL DEFAULT 'skip'
        CHECK (concurrency_policy IN ('skip', 'queue', 'replace')),
    created_by_type TEXT NOT NULL CHECK (created_by_type IN ('member', 'agent')),
    created_by_id UUID NOT NULL,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_autopilot_workspace ON autopilot(workspace_id);
CREATE INDEX IF NOT EXISTS idx_autopilot_assignee ON autopilot(assignee_id);

-- Trigger: how an autopilot gets kicked off (schedule, webhook, or API).
CREATE TABLE IF NOT EXISTS autopilot_trigger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    autopilot_id UUID NOT NULL REFERENCES autopilot(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('schedule', 'webhook', 'api')),
    enabled BOOLEAN NOT NULL DEFAULT true,
    cron_expression TEXT,
    timezone TEXT DEFAULT 'UTC',
    next_run_at TIMESTAMPTZ,
    webhook_token TEXT,
    label TEXT,
    last_fired_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_autopilot_trigger_autopilot ON autopilot_trigger(autopilot_id);
CREATE INDEX IF NOT EXISTS idx_autopilot_trigger_next_run ON autopilot_trigger(next_run_at)
    WHERE enabled = true AND kind = 'schedule';

-- Run: one execution of an autopilot.
CREATE TABLE IF NOT EXISTS autopilot_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    autopilot_id UUID NOT NULL REFERENCES autopilot(id) ON DELETE CASCADE,
    trigger_id UUID REFERENCES autopilot_trigger(id) ON DELETE SET NULL,
    source TEXT NOT NULL CHECK (source IN ('schedule', 'manual', 'webhook', 'api')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'issue_created', 'running', 'skipped', 'completed', 'failed')),
    issue_id UUID REFERENCES issue(id) ON DELETE SET NULL,
    task_id UUID REFERENCES agent_task_queue(id) ON DELETE SET NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    failure_reason TEXT,
    trigger_payload JSONB,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_autopilot_run_autopilot ON autopilot_run(autopilot_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_autopilot_run_status ON autopilot_run(autopilot_id, status)
    WHERE status IN ('pending', 'issue_created', 'running');

-- Link agent tasks to autopilot runs (same pattern as chat_session_id from migration 033).
ALTER TABLE agent_task_queue ADD COLUMN IF NOT EXISTS autopilot_run_id UUID REFERENCES autopilot_run(id) ON DELETE SET NULL;

-- Track which issues were created by an autopilot so they can be filtered in lists.
ALTER TABLE issue ADD COLUMN IF NOT EXISTS origin_type TEXT CHECK (origin_type IN ('autopilot'));
ALTER TABLE issue ADD COLUMN IF NOT EXISTS origin_id UUID;
CREATE INDEX IF NOT EXISTS idx_issue_origin ON issue(origin_type, origin_id) WHERE origin_type IS NOT NULL;

```

## server/go/migrations/043_audit_reserved_slugs.up.sql

```sql
-- Audit existing workspace slugs against the reserved-words list.
--
-- After the URL refactor, workspace URLs are /{slug}/... where slug must not
-- collide with frontend top-level routes (login, onboarding, api, etc.).
-- The CreateWorkspace handler now rejects new reserved slugs, but pre-refactor
-- data could already contain conflicting slugs. This migration fails loudly
-- so deploy is blocked until those workspaces are renamed or deleted.
--
-- Keep the slug list in sync with:
--  - server/go/internal/handler/workspace_reserved_slugs.go
--  - packages/core/paths/reserved-slugs.ts

DO $$
DECLARE
  conflict_count INT;
  conflict_list TEXT;
BEGIN
  SELECT
    COUNT(*),
    string_agg(slug, ', ' ORDER BY slug)
  INTO conflict_count, conflict_list
  FROM workspace
  WHERE slug IN (
    -- Auth + onboarding
    'login', 'logout', 'signup', 'onboarding', 'invite', 'auth',
    -- Reserved for future platform routes
    'api', 'admin', 'settings', 'help', 'about', 'pricing', 'changelog',
    -- Next.js / hosting internals
    '_next', 'favicon.ico', 'robots.txt', 'sitemap.xml', 'manifest.json', '.well-known'
  );

  IF conflict_count > 0 THEN
    RAISE EXCEPTION 'Found % workspace(s) with reserved slugs: %. Rename or delete before deploying.', conflict_count, conflict_list;
  END IF;
END $$;

```

## server/go/migrations/043_fix_orphaned_autopilot_runs.up.sql

```sql
-- Remove concurrency_policy from autopilot (was broken: skip had orphan bug,
-- queue didn't actually queue, replace didn't cancel running tasks).

-- 1. Clean up orphaned runs (issue deleted → issue_id NULL, status stuck).
UPDATE autopilot_run
SET status = 'failed',
    completed_at = now(),
    failure_reason = 'linked issue was deleted'
WHERE status = 'issue_created'
  AND issue_id IS NULL;

-- 2. Migrate skipped/pending runs to failed (these statuses are removed).
UPDATE autopilot_run
SET status = 'failed',
    completed_at = COALESCE(completed_at, now()),
    failure_reason = COALESCE(failure_reason, 'migrated from legacy status')
WHERE status IN ('skipped', 'pending');

-- 3. Update the status CHECK constraint to remove skipped and pending.
ALTER TABLE autopilot_run DROP CONSTRAINT IF EXISTS autopilot_run_status_check;
ALTER TABLE autopilot_run ADD CONSTRAINT autopilot_run_status_check
    CHECK (status IN ('issue_created', 'running', 'completed', 'failed'));

-- 4. Drop concurrency_policy column.
ALTER TABLE autopilot DROP COLUMN IF EXISTS concurrency_policy;

-- 5. Update the partial index on status to match new allowed values.
DROP INDEX IF EXISTS idx_autopilot_run_status;
CREATE INDEX IF NOT EXISTS idx_autopilot_run_status ON autopilot_run(autopilot_id, status)
    WHERE status IN ('issue_created', 'running');

-- 6. Add index for issue-linked run lookups (used by FailAutopilotRunsByIssue
--    and GetAutopilotRunByIssue before issue deletion).
CREATE INDEX IF NOT EXISTS idx_autopilot_run_issue ON autopilot_run(issue_id)
    WHERE issue_id IS NOT NULL;

```

## server/go/migrations/044_fix_workspace_fallback_slug.up.sql

```sql
-- Cleanup for the "workspace" auto-generated slug fallback bug.
--
-- The frontend's nameToWorkspaceSlug() previously fell back to the literal
-- string "workspace" when the input name produced no valid slug characters
-- (Chinese / Japanese / emoji / Arabic names all stripped to empty by the
-- /[^a-z0-9]+/g regex). This meant the first non-ASCII-named workspace on
-- any instance silently got slug = "workspace" and (a) showed a confusing
-- /workspace/{view} URL after the URL refactor, (b) blocked subsequent
-- non-ASCII-named workspaces with 409 conflicts on the unique slug index.
--
-- The frontend bug is fixed in
--   packages/views/workspace/slug.ts (commit d5c9613f)
-- but pre-existing data with slug = 'workspace' must be migrated. Renaming
-- to 'workspace-<8 hex chars>' preserves URL stability for the few users
-- already on it while ensuring uniqueness if multiple instances had this
-- workspace (e.g. local dev DBs across the team).
--
-- For other broken slugs (numeric-only, emoji-only, etc.) we don't migrate
-- here because they are valid per the regex and the user might have chosen
-- them intentionally. Only the literal "workspace" fallback is patched.

UPDATE workspace
SET slug = 'workspace-' || substring(replace(id::text, '-', '') from 1 for 8)
WHERE slug = 'workspace';

```

## server/go/migrations/045_audit_dashboard_route_slugs.up.sql

```sql
-- Audit existing workspace slugs against the dashboard route segment names.
--
-- Migration 043 audited the auth/onboarding/hosting reserved words. This one
-- adds the dashboard route segments (issues / projects / agents / inbox /
-- my-issues / runtimes / skills / autopilots) — slug = any of these would
-- produce visually ambiguous URLs after the URL refactor (e.g. /issues/abc
-- could mean "issue abc in workspace 'issues'" or "issue abc in some
-- workspace"). Reserve to avoid the confusion.
--
-- "settings" was already reserved by 043, no need to repeat.
--
-- Keep this slug list in sync with:
--  - server/go/internal/handler/workspace_reserved_slugs.go
--  - packages/core/paths/reserved-slugs.ts

DO $$
DECLARE
  conflict_count INT;
  conflict_list TEXT;
BEGIN
  SELECT
    COUNT(*),
    string_agg(slug, ', ' ORDER BY slug)
  INTO conflict_count, conflict_list
  FROM workspace
  WHERE slug IN (
    'issues', 'projects', 'autopilots', 'agents',
    'inbox', 'my-issues', 'runtimes', 'skills'
  );

  IF conflict_count > 0 THEN
    RAISE EXCEPTION 'Found % workspace(s) with slugs that collide with dashboard routes: %. Rename or delete before deploying.', conflict_count, conflict_list;
  END IF;
END $$;

```

## server/go/migrations/046_agent_mcp_config.up.sql

```sql
ALTER TABLE agent ADD COLUMN mcp_config jsonb;

```

## server/go/migrations/046_agent_unique_name.up.sql

```sql
-- Migration: 046_agent_unique_name
-- Enforces uniqueness of agent names within a workspace so that the API can
-- return a clear 409 Conflict instead of a silent duplicate or a 500 error.
--
-- Step 1 deduplicates any existing rows that would violate the constraint,
-- keeping the most recently updated agent when names collide.
-- Step 2 adds the constraint so future inserts are rejected at the DB level.
--
-- See: docs/improvements.md PR-3, docs/pr-strategy.md Milestone 1

-- Step 1: delete duplicates, keep the most recently updated one
DELETE FROM agent a
USING (
    SELECT id,
           ROW_NUMBER() OVER (PARTITION BY workspace_id, name ORDER BY updated_at DESC) AS rn
    FROM agent
) ranked
WHERE a.id = ranked.id AND ranked.rn > 1;

-- Step 2: add the constraint
ALTER TABLE agent
    ADD CONSTRAINT agent_workspace_name_unique UNIQUE (workspace_id, name);

```

## server/go/migrations/046_drop_runtime_usage.up.sql

```sql
DROP TABLE IF EXISTS runtime_usage;

```

## server/go/migrations/047_audit_extended_reserved_slugs.up.sql

```sql
-- Audit existing workspace slugs against the extended reserved-slug list.
--
-- This PR (1) renames the global workspace-creation route from /new-workspace
-- to /workspaces/new, which moves the reserved name from "new-workspace" to
-- "workspaces", and (2) expands the reserved slug list to cover the broader
-- set recommended by the URL-design audit (auth flow words, RFC 2142 mailbox
-- names, hostname confusables, common platform routes).
--
-- Migration 046 was REMOVED in the same PR. It was auditing "new-workspace"
-- which is no longer reserved, so it had become dead code AND was actively
-- blocking prd deploy on a real-user workspace that no longer needs renaming
-- (the workspace is now safe under the new route — `new-workspace` slug
-- resolves to its workspace, no longer shadowed by the global route which
-- moved to /workspaces/new). Removing 046 is forward-only safe: 046 had
-- never successfully applied in prd (it was the source of the deploy
-- block), and the audit-only nature means down-rollback is a no-op.
--
-- The data audit was performed before this migration was written and confirmed
-- ZERO conflicts for every slug listed below in production. This migration
-- exists as a safety net: if a workspace with one of these slugs slips into
-- prod between audit and deploy, the migration will fail loudly rather than
-- silently shadowing the workspace behind a system route.
--
-- Slugs INTENTIONALLY OMITTED from this audit despite being in the reserved
-- list: 'admin', 'workpal', 'new', 'setup', 'www'. These already have one
-- conflicting workspace each in production. They will be handled in a
-- follow-up PR (rename via owner outreach + targeted migration), not blocked
-- on this deploy.
--
-- Keep this slug list aligned with:
--  - server/go/internal/handler/workspace_reserved_slugs.go
--  - packages/core/paths/reserved-slugs.ts

DO $$
DECLARE
  conflict_count INT;
  conflict_list TEXT;
BEGIN
  SELECT
    COUNT(*),
    string_agg(slug, ', ' ORDER BY slug)
  INTO conflict_count, conflict_list
  FROM workspace
  WHERE slug IN (
    -- Auth flow (newly added)
    'signin', 'signout', 'oauth', 'callback', 'verify', 'reset', 'password',

    -- Platform routes (newly added)
    'docs', 'support', 'status', 'legal', 'privacy', 'terms', 'security',
    'contact', 'blog', 'careers', 'press', 'download',

    -- Workspace/team segments (newly added — replaces 'new-workspace')
    'workspaces', 'teams',

    -- RFC 2142 mailboxes (newly added)
    'postmaster', 'abuse', 'noreply', 'webmaster', 'hostmaster',

    -- Hostname confusables (newly added)
    'mail', 'ftp', 'static', 'cdn', 'assets', 'public', 'files', 'uploads'
  );

  IF conflict_count > 0 THEN
    RAISE EXCEPTION 'Found % workspace(s) with slugs that collide with extended reserved list: %. Rename or delete before deploying.', conflict_count, conflict_list;
  END IF;
END $$;

```

## server/go/migrations/048_runtime_daemon_uuid.up.sql

```sql
-- Runtime identity is moving from `os.Hostname()` to a persistent daemon UUID.
-- `legacy_daemon_id` records the most recent hostname-derived daemon_id that
-- was merged into this row so the previous identity remains traceable for
-- debugging and audit after the old row is deleted.
ALTER TABLE agent_runtime
    ADD COLUMN legacy_daemon_id TEXT;

```

## server/go/migrations/049_audit_legacy_reserved_slugs.up.sql

```sql
-- Audit `admin`, `workpal`, `new`, `www` against the workspace.slug column.
--
-- Follow-up to migration 047 (extended reserved slugs). 047 intentionally
-- omitted these four slugs from its audit because each had one conflicting
-- workspace in production at the time, and blocking deploy on owner outreach
-- was deemed unacceptable. MUL-972 closed that loop on prd:
--
--   * `admin`   (99cd10e4-…) → renamed to `legacy-admin-99cd10e4`
--   * `workpal` (dcd796aa-…) → renamed to `legacy-workpal-dcd796aa`
--   * `new`     (e391e3ed-…) → renamed to `legacy-new-e391e3ed`
--   * `www`     (5e8d38b2-…) → workspace deleted (was empty: 0 issues /
--                              projects / agents, owner-only member)
--
-- With the prd data clean, this migration promotes those four slugs into the
-- audit set so any future workspace that slips in with one of them fails
-- startup loudly instead of being silently shadowed by a global route.
--
-- `setup` is STILL omitted from this audit. The `setup` workspace
-- (b43f0bc2-…) is a real production user (Roberto Betancourth, building a
-- chants/Alabanzas app) and is being handled out-of-band via owner outreach
-- to negotiate a rename. A separate follow-up migration will fold `setup`
-- into the audit once that workspace's slug has been migrated.
--
-- Keep this slug list aligned with:
--  - server/go/internal/handler/workspace_reserved_slugs.go
--  - packages/core/paths/reserved-slugs.ts

DO $$
DECLARE
  conflict_count INT;
  conflict_list TEXT;
BEGIN
  SELECT
    COUNT(*),
    string_agg(slug, ', ' ORDER BY slug)
  INTO conflict_count, conflict_list
  FROM workspace
  WHERE slug IN (
    'admin',
    'workpal',
    'new',
    'www'
  );

  IF conflict_count > 0 THEN
    RAISE EXCEPTION 'Found % workspace(s) with slugs that collide with the legacy reserved-slug audit set: %. Rename or delete before deploying (see MUL-972 for the playbook).', conflict_count, conflict_list;
  END IF;
END $$;

```

## server/go/migrations/050_add_onboarded_at_to_users.up.sql

```sql
ALTER TABLE "user" ADD COLUMN onboarded_at TIMESTAMPTZ;

-- Grandfather existing users. Treat any row that already exists at the
-- moment this column lands as already-onboarded so the deploy doesn't
-- wall them off behind a flow they never asked for. `created_at` (not
-- NOW()) keeps analytics honest — "signup → onboarded interval" reads
-- as 0 for pre-launch users, which under grandfathering semantics is
-- accurate ("they onboarded implicitly at signup").
UPDATE "user" SET onboarded_at = created_at;

```

## server/go/migrations/050_agent_model.up.sql

```sql
-- Adds an explicit per-agent model field. Previously the only way to
-- pick a model per agent was via custom_env / custom_args; a first-class
-- column lets the UI render a dropdown and keeps Codex-style app-server
-- providers (which reject -m in custom_args) working without CLI flags.
ALTER TABLE agent ADD COLUMN model TEXT;

```

## server/go/migrations/050_issue_first_executed_at.up.sql

```sql
-- first_executed_at is stamped atomically the first time an issue's task
-- reaches a terminal `done` state. Analytics reads this as the single
-- source of truth for the issue_executed funnel event — atomic UPDATE …
-- WHERE first_executed_at IS NULL guarantees at-most-one emission per
-- issue regardless of retries, re-assignments, or comment-triggered
-- follow-up tasks.
ALTER TABLE issue
    ADD COLUMN first_executed_at TIMESTAMPTZ NULL;

-- A partial index on the NULL-until-set column lets the workspace-scoped
-- "how many issues executed so far?" count (nth_issue_for_workspace)
-- skip the large tail of never-executed issues.
CREATE INDEX IF NOT EXISTS idx_issue_first_executed_at
    ON issue (workspace_id, first_executed_at)
    WHERE first_executed_at IS NOT NULL;

```

## server/go/migrations/051_add_onboarding_state_to_users.up.sql

```sql
ALTER TABLE "user"
  ADD COLUMN onboarding_questionnaire JSONB NOT NULL DEFAULT '{}'::jsonb;

```

## server/go/migrations/052_add_cloud_waitlist_to_users.up.sql

```sql
-- RFC 5321 caps email addresses at 254 chars. Bounded TEXT prevents
-- the column being abused as arbitrary storage.
ALTER TABLE "user"
  ADD COLUMN cloud_waitlist_email VARCHAR(254),
  ADD COLUMN cloud_waitlist_reason TEXT;

```

## server/go/migrations/053_drop_orphan_onboarding_current_step.up.sql

```sql
-- An earlier iteration of migration 051 added `onboarding_current_step`
-- and then later the same PR removed it (the column was never actually
-- consumed by the shipping code). Any environment that pulled the
-- interim revision and ran `migrate-up` has a dead column; any
-- environment that only sees the final 051 never will. This migration
-- collapses both into the same final schema. IF EXISTS makes it a
-- no-op on fresh environments.
ALTER TABLE "user" DROP COLUMN IF EXISTS onboarding_current_step;

```

## server/go/migrations/054_add_starter_content_state_to_users.up.sql

```sql
-- Post-onboarding starter content opt-in. State values:
--   NULL           → we haven't asked the user yet (new user just after
--                    onboarding). The workspace issues page shows the
--                    StarterContentPrompt dialog until they decide.
--   'imported'     → user chose to import; seeding ran; never ask again.
--   'dismissed'    → user declined; never ask again.
--   'skipped_legacy' → backfilled for pre-feature users so they aren't
--                    prompted when they next sign in.
ALTER TABLE "user" ADD COLUMN starter_content_state TEXT;

-- Anyone who already finished onboarding before this feature existed
-- should NOT see the prompt — their workspace has already settled into
-- whatever state they wanted.
UPDATE "user"
   SET starter_content_state = 'skipped_legacy'
 WHERE onboarded_at IS NOT NULL
   AND starter_content_state IS NULL;

```

## server/go/migrations/055_task_lease_and_retry.up.sql

```sql
-- Adds task-level retry/lease bookkeeping so the runtime sweeper and the
-- daemon startup recovery path can distinguish "fresh attempt" from
-- "auto-rerun after orphan", and so resume context survives a daemon
-- restart mid-execution.
--
-- Columns:
--   attempt           -- 1 for the first run, incremented per auto-retry/manual rerun
--   max_attempts      -- ceiling honored by the auto-retry path; 1 disables retry
--   parent_task_id    -- back-pointer to the task that this one re-attempts
--   failure_reason    -- coarse classifier set when status flips to failed:
--                        'agent_error', 'timeout', 'runtime_offline',
--                        'runtime_recovery', 'manual'. The auto-retry path
--                        uses this to decide whether to spawn a child task.
--   last_heartbeat_at -- mid-task heartbeat timestamp; the runtime heartbeat
--                        already drives runtime liveness, but per-task
--                        timestamps let us tell stale tasks apart from
--                        long-running ones in future enhancements.

ALTER TABLE agent_task_queue
  ADD COLUMN attempt INT NOT NULL DEFAULT 1,
  ADD COLUMN max_attempts INT NOT NULL DEFAULT 2,
  ADD COLUMN parent_task_id UUID REFERENCES agent_task_queue(id) ON DELETE SET NULL,
  ADD COLUMN failure_reason TEXT,
  ADD COLUMN last_heartbeat_at TIMESTAMPTZ;

CREATE INDEX idx_agent_task_queue_parent ON agent_task_queue(parent_task_id);

```

## server/go/migrations/056_audit_newly_reserved_slugs.up.sql

```sql
-- Audit + rename existing workspace slugs against the newly-added reserved
-- set from MUL-961 (slug review follow-up).
--
-- This PR expands the reserved list in three directions:
--   * §1 Real conflict: `homepage` — `/homepage` is an active Next.js route
--     (`apps/web/app/(landing)/homepage/page.tsx`) that was missing from the
--     reserved list. Audit confirms zero prod workspaces with this slug.
--   * §3 Likely-future routes: home, dashboard, profile, account, billing,
--     notifications, search, members.
--   * API / ops prefixes: v1, v2, graphql, webhooks, sdk, tokens, cli,
--     health, ws, metrics, ping.
--
-- Per db-boy's prod audit (MUL-961 thread, 2026-04-22), two slugs in the §3
-- set already had live prod workspaces:
--
--   * `home`       (68a982da-68a7-4e2e-ac8e-45a0323507f3) — zzlye, 2026-04-14
--   * `dashboard`  (ea5a332f-06f9-480d-ab81-8f2324c92d80) — 王争,  2026-04-22
--
-- Decision on MUL-961: force-rename both via this migration (scheme 1), same
-- playbook as MUL-972 for admin/workpal/new/www. Rename targets `home-1`
-- and `dashboard-1` were verified unoccupied at audit time. The subsequent
-- DO block is a generic fallback that picks `<slug>-N` for any other row
-- that slips in between audit and deploy (defensive against a race with new
-- workspace creation — the reserved-slug check in app code lands in the
-- same deploy, but the migration runs first).
--
-- Owner outreach: zzlye@ and 王争@ should be notified that their
-- workspace URL prefix changed (/home → /home-1, /dashboard → /dashboard-1).
--
-- Keep this slug list aligned with:
--  - server/go/internal/handler/workspace_reserved_slugs.go
--  - packages/core/paths/reserved-slugs.ts

-- 1. Targeted renames for the two known conflicts at audit time.
UPDATE workspace SET slug = 'home-1'
  WHERE id = '68a982da-68a7-4e2e-ac8e-45a0323507f3' AND slug = 'home';
UPDATE workspace SET slug = 'dashboard-1'
  WHERE id = 'ea5a332f-06f9-480d-ab81-8f2324c92d80' AND slug = 'dashboard';

-- 2. Generic fallback: any other row whose slug lands in the newly
-- reserved set (race or new data between audit and deploy) is renamed to
-- `<slug>-N` with the lowest N that is free. Same pattern as the existing
-- audit migrations, hardened against collisions.
DO $$
DECLARE
  r RECORD;
  n INT;
BEGIN
  FOR r IN
    SELECT id, slug FROM workspace
    WHERE slug IN (
      -- Real conflict fix
      'homepage',
      -- Platform / marketing (newly added)
      'home', 'dashboard',
      -- Account / billing (newly added)
      'profile', 'account', 'billing', 'notifications', 'search', 'members',
      -- API / integration prefixes (newly added)
      'v1', 'v2', 'graphql', 'webhooks', 'sdk', 'tokens', 'cli',
      -- Backend ops / observability (newly added)
      'health', 'ws', 'metrics', 'ping'
    )
  LOOP
    n := 1;
    WHILE EXISTS (SELECT 1 FROM workspace WHERE slug = r.slug || '-' || n) LOOP
      n := n + 1;
    END LOOP;
    UPDATE workspace SET slug = r.slug || '-' || n WHERE id = r.id;
    RAISE NOTICE 'Renamed workspace % slug from % to %', r.id, r.slug, r.slug || '-' || n;
  END LOOP;
END $$;

-- 3. Post-condition audit: no workspace should remain on a reserved slug.
DO $$
DECLARE
  conflict_count INT;
  conflict_list TEXT;
BEGIN
  SELECT
    COUNT(*),
    string_agg(slug, ', ' ORDER BY slug)
  INTO conflict_count, conflict_list
  FROM workspace
  WHERE slug IN (
    'homepage',
    'home', 'dashboard',
    'profile', 'account', 'billing', 'notifications', 'search', 'members',
    'v1', 'v2', 'graphql', 'webhooks', 'sdk', 'tokens', 'cli',
    'health', 'ws', 'metrics', 'ping'
  );

  IF conflict_count > 0 THEN
    RAISE EXCEPTION 'After rename pass, % workspace(s) still on reserved slugs: %. This should be impossible — investigate.', conflict_count, conflict_list;
  END IF;
END $$;

```

## server/go/migrations/057_feedback.up.sql

```sql
CREATE TABLE feedback (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    workspace_id  UUID REFERENCES workspace(id) ON DELETE SET NULL,
    message       TEXT NOT NULL,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_feedback_user_created ON feedback(user_id, created_at DESC);

```

## server/go/migrations/058_drop_autopilot_priority_and_project_id.up.sql

```sql
-- Drop priority and project_id from autopilot.
-- These fields were never useful in the product: project_id was never exposed in the UI,
-- and priority was redundant with the agent's own task queue priority.

ALTER TABLE autopilot DROP COLUMN IF EXISTS priority;
ALTER TABLE autopilot DROP COLUMN IF EXISTS project_id;

```

## server/go/migrations/059_label_timestamps.up.sql

```sql
-- Add timestamp columns to issue_label so labels track their own lifecycle.
-- The table was scaffolded in 001_init.up.sql but never wired up to any code
-- path; timestamps are added here as a precondition for the new CRUD handlers,
-- CLI, and UI (see #1191).

ALTER TABLE issue_label
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Dedupe case-insensitive collisions before the unique index is created.
-- Self-hosted deployments may have `Bug` + `bug` pairs from manual poking at
-- the table, which would otherwise abort this migration when the unique index
-- is added below. Keep the oldest row intact (smallest id, by lexicographic
-- UUID order — effectively earliest-inserted since ids are gen_random_uuid()),
-- rename every later duplicate by appending a short UUID suffix. Visible only
-- on the rare installs that had duplicates; a no-op otherwise.
UPDATE issue_label AS il
SET name = il.name || ' (' || substring(il.id::text, 1, 8) || ')'
WHERE EXISTS (
    SELECT 1 FROM issue_label il2
    WHERE il2.workspace_id = il.workspace_id
      AND LOWER(il2.name) = LOWER(il.name)
      AND il2.id < il.id
);

-- Workspace-scoped uniqueness on label name. Case-insensitive to avoid
-- "Bug" / "bug" drift that would confuse users in the picker UI.
CREATE UNIQUE INDEX IF NOT EXISTS issue_label_workspace_name_lower_idx
    ON issue_label (workspace_id, LOWER(name));

```

## server/go/migrations/060_add_user_language.up.sql

```sql
ALTER TABLE "user" ADD COLUMN language VARCHAR(20) DEFAULT NULL;

```

## server/go/migrations/060_agent_description_length.up.sql

```sql
-- Cap agent.description at 255 characters so the column matches the
-- product-side limit enforced by the UI (counter + disabled save) and the
-- handler validation. The TEXT type stays — char_length is a constraint
-- on top, not a type change, which keeps the existing column data intact
-- and avoids a rewrite of the table.
--
-- Pre-flight truncate: any existing row that already exceeds the new
-- ceiling gets clipped to 255 chars. Without this the constraint add
-- would abort on the first over-limit row. Affected rows are rare (no UI
-- ever encouraged long descriptions), but defensive trimming keeps
-- self-hosted installs from blocking on the migration.
UPDATE agent
SET description = substring(description from 1 for 255)
WHERE char_length(description) > 255;

-- Two-step add: NOT VALID skips the table scan and only briefly takes an
-- ACCESS EXCLUSIVE lock to register the constraint, so concurrent writes
-- are not blocked. New inserts/updates are enforced from this point on.
-- The follow-up VALIDATE CONSTRAINT runs the actual scan under SHARE
-- UPDATE EXCLUSIVE, which permits concurrent writes during the scan.
--
-- At today's agent-table size the difference is invisible, but the
-- pattern is free defensively and matches Squawk's recommended migration
-- shape (https://squawkhq.com/docs/constraint-missing-not-valid).
ALTER TABLE agent
    ADD CONSTRAINT agent_description_length
    CHECK (char_length(description) <= 255) NOT VALID;

ALTER TABLE agent VALIDATE CONSTRAINT agent_description_length;

```

## server/go/migrations/060_chat_session_runtime_id.up.sql

```sql
ALTER TABLE chat_session
ADD COLUMN runtime_id UUID REFERENCES agent_runtime(id) ON DELETE SET NULL;

-- Backfill only sessions with a recorded resume pointer from a completed or
-- failed task. Sessions with no prior task remain NULL and will fail closed
-- until a future successful task writes a session_id/runtime_id pair.
UPDATE chat_session cs
SET runtime_id = latest.runtime_id
FROM (
    SELECT DISTINCT ON (chat_session_id)
        chat_session_id,
        runtime_id,
        session_id
    FROM agent_task_queue
    WHERE chat_session_id IS NOT NULL
      AND session_id IS NOT NULL
      AND status IN ('completed', 'failed')
    ORDER BY chat_session_id, COALESCE(completed_at, started_at, dispatched_at, created_at) DESC
) latest
WHERE latest.chat_session_id = cs.id
  AND latest.session_id = cs.session_id;

```

## server/go/migrations/060_issue_origin_quick_create.up.sql

```sql
-- Extend issue.origin_type to allow the quick-create flow to stamp issues with
-- origin_type='quick_create' + origin_id=<agent_task_queue.id>. The completion
-- handler uses this for a deterministic lookup of "the issue this quick-create
-- task produced" instead of "the agent's most recent issue", which races against
-- concurrent issue creates by the same agent (e.g. assignment task running
-- alongside quick-create when max_concurrent_tasks > 1).
ALTER TABLE issue DROP CONSTRAINT IF EXISTS issue_origin_type_check;
ALTER TABLE issue ADD CONSTRAINT issue_origin_type_check
    CHECK (origin_type IN ('autopilot', 'quick_create'));

```

## server/go/migrations/061_task_trigger_summary.up.sql

```sql
-- Snapshot the trigger context (comment text, autopilot title, etc) into
-- the task row at creation time. Lets every task row self-describe across
-- surfaces (issue detail Execution log, agent activity tooltip, inbox)
-- without joining back to the originating row, and survives later edits
-- or deletes of that source.
ALTER TABLE agent_task_queue ADD COLUMN trigger_summary TEXT;

```

## server/go/migrations/062_chat_message_failure_reason.up.sql

```sql
-- Mirror the issue path's "fallback comment on failure" with a failure_reason
-- column on chat_message. When FailTask runs on a chat task, server writes
-- an assistant chat_message tagged with the daemon-reported reason so the
-- conversation history shows what happened (instead of the previous black
-- hole where a failed task left no trace in the user-visible thread).
ALTER TABLE chat_message ADD COLUMN failure_reason TEXT;

```

## server/go/migrations/063_chat_message_elapsed.up.sql

```sql
-- Capture per-task wall-clock duration (queue → done) on assistant chat
-- messages so the UI can render "Replied in 38s" / "Failed after 12s"
-- under each reply. BIGINT to avoid any int32 overflow concerns even
-- though chat tasks are short — keeps the column reusable for longer
-- workloads later.
ALTER TABLE chat_message ADD COLUMN elapsed_ms BIGINT;

```

## server/go/migrations/064_notification_preference.up.sql

```sql
CREATE TABLE notification_preference (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    preferences JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(workspace_id, user_id)
);

```

## server/go/migrations/065_backfill_onboarded_at.up.sql

```sql
-- Backfill onboarded_at for users who already belong to a workspace.
-- PR #1868 (since reverted) routed users by hasWorkspace instead of onboarded_at,
-- producing a population of users with workspace memberships but
-- onboarded_at == NULL. After the new design enforces
-- "member row exists ↔ onboarded_at != null" via backend transactions,
-- this one-shot backfill cleans existing dirty rows.
--
-- Uses created_at as the timestamp because these users were de facto onboarded
-- when their account was first created — backfilling with now() would distort
-- onboarding-funnel analytics. COALESCE keeps it idempotent.
UPDATE "user"
SET onboarded_at = COALESCE(onboarded_at, created_at)
WHERE id IN (SELECT DISTINCT user_id FROM member);

```

## server/go/migrations/065_project_resources.up.sql

```sql
-- Project Resources: typed pointers from a project to external resources
-- (github_repo for now; notion_page / gdoc / url / file later). The shape is
-- intentionally polymorphic — resource_type is a free string and resource_ref
-- is JSONB, so adding a new type requires zero schema changes.
CREATE TABLE project_resource (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    workspace_id  UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    resource_type TEXT NOT NULL,
    resource_ref  JSONB NOT NULL,
    label         TEXT,
    position      INT  NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    UUID,
    UNIQUE (project_id, resource_type, resource_ref)
);

CREATE INDEX idx_project_resource_project ON project_resource(project_id, position);
CREATE INDEX idx_project_resource_workspace ON project_resource(workspace_id);

```

## server/go/migrations/066_force_fresh_session.up.sql

```sql
-- Per-task signal that the manual rerun flow uses to short-circuit the
-- (agent_id, issue_id) session resume lookup. Set when a user clicks
-- rerun: the user just judged the prior output bad, so the daemon must
-- start a fresh agent session instead of resuming the same conversation
-- that produced the bad result. Auto-retry of an orphaned mid-flight
-- failure leaves this FALSE so MUL-1128's resume contract is preserved.
ALTER TABLE agent_task_queue
  ADD COLUMN force_fresh_session BOOLEAN NOT NULL DEFAULT FALSE;

```

## server/go/migrations/067_task_queue_claim_candidate_index.up.sql

```sql
-- Partial index that backs ListQueuedClaimCandidatesByRuntime. Daemons poll
-- /tasks/claim every 30s per runtime; the filter "runtime_id = $1 AND
-- status = 'queued'" runs every poll and is the dominant cost on warm paths.
-- Restricting to status = 'queued' keeps the index tiny — terminal-state
-- rows (completed/failed/cancelled) accumulate forever in the table but are
-- excluded from the index, so it stays bounded by current queue depth.
-- ORDER BY priority DESC, created_at ASC mirrors the SELECT so the planner
-- can serve the query as an index-only scan without an extra sort.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_claim_candidates
    ON agent_task_queue (runtime_id, priority DESC, created_at ASC)
    WHERE status = 'queued';

```

## server/go/migrations/068_timeline_keyset_index.up.sql

```sql
-- Composite indexes that back the cursor-paginated timeline endpoint.
-- The keyset query shape is "WHERE issue_id = $1 AND (created_at, id) < ($2, $3)
-- ORDER BY created_at DESC, id DESC LIMIT $4". With (issue_id, created_at DESC,
-- id DESC) the planner can serve this as an index-only scan with no sort.
-- The leading issue_id column also covers the simple "WHERE issue_id = $1"
-- lookups, making the previous single-column idx_comment_issue and
-- idx_activity_log_issue redundant.
--
-- Not using CREATE INDEX CONCURRENTLY because the migration runner wraps
-- multi-statement files in an implicit transaction, which conflicts with
-- CONCURRENTLY. For pre-production scale this brief lock is acceptable; if
-- this ever needs to run on a hot prod table, do it as a one-off ops step.

CREATE INDEX IF NOT EXISTS idx_comment_issue_keyset
    ON comment (issue_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_activity_log_issue_keyset
    ON activity_log (issue_id, created_at DESC, id DESC);

DROP INDEX IF EXISTS idx_comment_issue;
DROP INDEX IF EXISTS idx_activity_log_issue;

```

## server/go/migrations/069_comment_resolved_at.up.sql

```sql
ALTER TABLE comment
    ADD COLUMN resolved_at TIMESTAMPTZ NULL,
    ADD COLUMN resolved_by_type TEXT NULL,
    ADD COLUMN resolved_by_id UUID NULL;

ALTER TABLE comment
    ADD CONSTRAINT comment_resolved_consistency CHECK (
        (resolved_at IS NULL AND resolved_by_type IS NULL AND resolved_by_id IS NULL)
        OR (resolved_at IS NOT NULL AND resolved_by_type IS NOT NULL AND resolved_by_id IS NOT NULL)
    );

CREATE INDEX comment_issue_resolved_at_idx ON comment (issue_id, resolved_at);

```

## server/go/migrations/069_drop_task_last_heartbeat.up.sql

```sql
-- Drops agent_task_queue.last_heartbeat_at. The column was introduced in
-- migration 055 as scaffolding for "future enhancements" (telling stale
-- tasks apart from long-running ones), but no consumer was ever built:
-- runtime liveness is owned by agent_runtime.last_seen_at + the Redis
-- LivenessStore, and FailStaleTasks keys off dispatched_at/started_at.
-- The only writer was UpdateAgentTaskSession bumping it on every PinTaskSession
-- call, which was a wasted write. Drop the column so the write goes away too.

ALTER TABLE agent_task_queue
  DROP COLUMN IF EXISTS last_heartbeat_at;

```

## server/go/migrations/072_task_usage_updated_at.up.sql

```sql
-- Add `updated_at` to task_usage so the daily-rollup worker (added in 073)
-- can detect rows that were corrected by `UpsertTaskUsage` after their
-- original creation. The existing UPSERT path overwrites token counts on
-- conflict but leaves created_at unchanged, so a watermark on created_at
-- alone would silently miss those corrections.
--
-- Schema-only, online-safe migration. The column is nullable with no
-- backfill UPDATE so this is metadata-only on a hot, high-write table —
-- no full-table rewrite, no row-lock storm, no WAL spike. Old rows stay
-- NULL; the rollup function (073) handles them via
-- `COALESCE(updated_at, created_at)` and an OR branch in the window
-- filter so legacy rows are still discoverable by backfill.
--
-- DEFAULT now() is set after the column exists so new INSERTs (and
-- UpsertTaskUsage on conflict, which sets the value explicitly) always
-- get a timestamp. Setting the default on an existing column does NOT
-- touch existing rows; only new rows get the default. This keeps the
-- migration cheap on ~hundreds of millions of `task_usage` rows.
ALTER TABLE task_usage
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

ALTER TABLE task_usage
    ALTER COLUMN updated_at SET DEFAULT now();

```

## server/go/migrations/073_task_usage_daily_rollup.up.sql

```sql
-- Daily rollup table for `task_usage`. Background: the dashboard query
-- ListRuntimeUsage runs `SUM() GROUP BY DATE(created_at), provider, model`
-- against the raw event stream and is called once per runtime row on the
-- runtimes list (plus once per detail page load), so it dominates DB load
-- as event volume grows. We materialise the day-bucketed aggregate here
-- so reads scan O(days × providers × models) rows instead of O(events).
--
-- All query dimensions are denormalised into the table so reads never
-- need to join `agent_task_queue`. The PK doubles as the upsert key for
-- the rollup worker.
CREATE TABLE task_usage_daily (
    bucket_date         DATE        NOT NULL,
    workspace_id        UUID        NOT NULL,
    runtime_id          UUID        NOT NULL,
    provider            TEXT        NOT NULL,
    model               TEXT        NOT NULL,
    input_tokens        BIGINT      NOT NULL DEFAULT 0,
    output_tokens       BIGINT      NOT NULL DEFAULT 0,
    cache_read_tokens   BIGINT      NOT NULL DEFAULT 0,
    cache_write_tokens  BIGINT      NOT NULL DEFAULT 0,
    event_count         BIGINT      NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (bucket_date, workspace_id, runtime_id, provider, model)
);

-- Primary read path: runtime detail page + runtimes-list cost cell, both
-- filter by runtime_id and order by date DESC. bucket_date DESC in the
-- index lets the query avoid an extra sort.
CREATE INDEX idx_task_usage_daily_runtime_date
    ON task_usage_daily (runtime_id, bucket_date DESC);

-- Workspace-wide aggregations hit this index instead of fanning out per
-- runtime.
CREATE INDEX idx_task_usage_daily_workspace_date
    ON task_usage_daily (workspace_id, bucket_date DESC);

-- Single-row state table tracking how far the rollup worker has consumed.
CREATE TABLE task_usage_rollup_state (
    id                    SMALLINT    PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    watermark_at          TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01 00:00:00+00',
    last_run_started_at   TIMESTAMPTZ,
    last_run_finished_at  TIMESTAMPTZ,
    last_run_rows         BIGINT      NOT NULL DEFAULT 0,
    last_error            TEXT
);
INSERT INTO task_usage_rollup_state (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Window-based aggregation primitive. Used by both the cron-driven
-- watermark advancer and the offline backfill command, so they stay
-- byte-identical in their semantics. Returns the number of output rows
-- touched.
--
-- IDEMPOTENCY CONTRACT (this is the important bit):
--   For every (bucket_date, workspace_id, runtime_id, provider, model)
--   key that has at least one task_usage row whose `updated_at` falls in
--   [p_from, p_to), this function REPLACES the corresponding daily row
--   with the SUM of *all* task_usage rows for that key (regardless of
--   their updated_at). It does NOT add a delta.
--
-- Consequences:
--   * Replaying the same window is safe — the row is rebuilt from raw
--     each time, so the result converges.
--   * Two callers (cron + backfill) processing overlapping windows is
--     safe — both write the same value.
--   * `UpsertTaskUsage` corrections that overwrite token counts are
--     captured: the corrected row's updated_at gets bumped, the next
--     window picks up its bucket key, and the bucket is recomputed
--     from current truth.
--
-- Cost: the recompute reads ALL task_usage rows for each dirty bucket,
-- not just the windowed slice. In steady state only "today" buckets are
-- dirty (a handful of keys per active runtime), so this stays cheap.
-- During backfill the entire history's bucket keys become dirty once;
-- the backfill walks history in monthly slices to bound the working
-- set per call.
CREATE OR REPLACE FUNCTION rollup_task_usage_daily_window(
    p_from TIMESTAMPTZ,
    p_to   TIMESTAMPTZ
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT;
BEGIN
    IF p_from >= p_to THEN
        RETURN 0;
    END IF;

    WITH dirty_keys AS (
        SELECT DISTINCT
            DATE(tu.created_at) AS bucket_date,
            i.workspace_id      AS workspace_id,
            atq.runtime_id      AS runtime_id,
            tu.provider         AS provider,
            tu.model            AS model
        FROM task_usage tu
        JOIN agent_task_queue atq ON atq.id      = tu.task_id
        JOIN issue            i   ON i.id        = atq.issue_id
        WHERE atq.runtime_id IS NOT NULL
          AND (
              -- Steady state: rows updated within the watermark window.
              -- Hits idx_task_usage_updated_at directly.
              (tu.updated_at >= p_from AND tu.updated_at < p_to)
              -- Legacy rows from before migration 072 (updated_at IS NULL)
              -- — discoverable via created_at + the partial index added
              -- in 077. Steady-state windows after backfill never include
              -- historical dates, so this branch is a no-op once the
              -- backfill has swept history.
              OR (tu.updated_at IS NULL
                  AND tu.created_at >= p_from
                  AND tu.created_at <  p_to)
          )
    ),
    recomputed AS (
        SELECT
            dk.bucket_date,
            dk.workspace_id,
            dk.runtime_id,
            dk.provider,
            dk.model,
            SUM(tu.input_tokens)::bigint        AS input_tokens,
            SUM(tu.output_tokens)::bigint       AS output_tokens,
            SUM(tu.cache_read_tokens)::bigint   AS cache_read_tokens,
            SUM(tu.cache_write_tokens)::bigint  AS cache_write_tokens,
            COUNT(*)::bigint                    AS event_count
        FROM dirty_keys dk
        JOIN agent_task_queue atq ON atq.runtime_id = dk.runtime_id
        JOIN issue            i   ON i.id           = atq.issue_id
                                  AND i.workspace_id = dk.workspace_id
        JOIN task_usage       tu  ON tu.task_id     = atq.id
                                  AND tu.provider   = dk.provider
                                  AND tu.model      = dk.model
                                  AND DATE(tu.created_at) = dk.bucket_date
        GROUP BY 1, 2, 3, 4, 5
    )
    INSERT INTO task_usage_daily AS d (
        bucket_date, workspace_id, runtime_id, provider, model,
        input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
        event_count
    )
    SELECT
        bucket_date, workspace_id, runtime_id, provider, model,
        input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
        event_count
    FROM recomputed
    ON CONFLICT (bucket_date, workspace_id, runtime_id, provider, model) DO UPDATE
        SET input_tokens       = EXCLUDED.input_tokens,
            output_tokens      = EXCLUDED.output_tokens,
            cache_read_tokens  = EXCLUDED.cache_read_tokens,
            cache_write_tokens = EXCLUDED.cache_write_tokens,
            event_count        = EXCLUDED.event_count,
            updated_at         = now();

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    RETURN v_rows;
END;
$$;

-- Cron entry point. Advances the watermark by one window each call.
--
-- Invariants:
--  * `pg_try_advisory_lock(4242)` serialises overlapping ticks.
--  * The window upper bound is `now() - 5 minutes`. The lag exists
--    because `task_usage` rows are written from a separate transaction;
--    a row with updated_at = T can become visible to this snapshot at
--    some t > T. 5 minutes is a generous bound on that visibility delay
--    and keeps the dashboard "today" bucket at most ~10 min stale
--    (5 min lag + 5 min cron period).
--  * On error we record `last_error` and re-raise; the watermark is NOT
--    advanced because the UPDATE that advances it only runs after the
--    upsert succeeds.
--  * SAFE TO RUN CONCURRENTLY WITH BACKFILL: the window primitive is
--    idempotent (see contract above), so even if cron fires while the
--    offline backfill is also walking history, the worst case is some
--    bucket gets written twice with the same value.
CREATE OR REPLACE FUNCTION rollup_task_usage_daily()
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_lock_ok BOOLEAN;
    v_from    TIMESTAMPTZ;
    v_to      TIMESTAMPTZ;
    v_rows    BIGINT := 0;
BEGIN
    SELECT pg_try_advisory_lock(4242) INTO v_lock_ok;
    IF NOT v_lock_ok THEN
        RETURN 0;
    END IF;

    BEGIN
        UPDATE task_usage_rollup_state
           SET last_run_started_at = now(),
               last_error          = NULL
         WHERE id = 1
        RETURNING watermark_at INTO v_from;

        v_to := now() - INTERVAL '5 minutes';

        IF v_from < v_to THEN
            v_rows := rollup_task_usage_daily_window(v_from, v_to);

            UPDATE task_usage_rollup_state
               SET watermark_at         = v_to,
                   last_run_finished_at = now(),
                   last_run_rows        = v_rows
             WHERE id = 1;
        ELSE
            UPDATE task_usage_rollup_state
               SET last_run_finished_at = now(),
                   last_run_rows        = 0
             WHERE id = 1;
        END IF;

        PERFORM pg_advisory_unlock(4242);
        RETURN v_rows;
    EXCEPTION WHEN OTHERS THEN
        UPDATE task_usage_rollup_state
           SET last_error           = SQLERRM,
               last_run_finished_at = now()
         WHERE id = 1;
        PERFORM pg_advisory_unlock(4242);
        RAISE;
    END;
END;
$$;

```

## server/go/migrations/074_task_usage_updated_at_index.up.sql

```sql
-- Drives the rollup worker's "what changed since last tick" scan in
-- 073's window function. CONCURRENTLY avoids blocking writes during
-- build (matches the pattern used in 035/067 for live indexes).
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_usage_updated_at
    ON task_usage (updated_at);

```

## server/go/migrations/075_task_usage_created_at_index.up.sql

```sql
-- Helps the two lazy endpoints (ListRuntimeUsageByAgent / GetRuntimeUsageByHour)
-- that still scan the raw `task_usage` table by created_at. CONCURRENTLY
-- avoids blocking writes during build.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_usage_created_at
    ON task_usage (created_at);

```

## server/go/migrations/076_task_usage_pgcron_extension.up.sql

```sql
-- Enable pg_cron extension if available, but DO NOT schedule the rollup
-- job here. Scheduling must happen *after* a successful backfill run, so
-- the cron tick doesn't race the backfill (both write the same daily
-- buckets — the rollup function in 073 is now idempotent, so collisions
-- produce correct values, but we still avoid overlap as a defense in
-- depth + to keep load low during backfill).
--
-- Operator playbook (in deployment runbook):
--   1) Apply migrations 072..075 (this file is 076).
--   2) Run `go run ./cmd/backfill_task_usage_daily` — succeeds and
--      stamps the rollup-state watermark.
--   3) Set USAGE_DAILY_ROLLUP_ENABLED=true on the API and roll out.
--   4) As superuser:
--        SELECT cron.schedule(
--          'rollup_task_usage_daily',
--          '*/5 * * * *',
--          $$SELECT rollup_task_usage_daily()$$
--        );
--   5) As superuser, also schedule cron-log pruning (see notes below).
--
-- The CREATE EXTENSION is wrapped in DO/EXCEPTION so dev/CI environments
-- without `shared_preload_libraries=pg_cron` skip gracefully and the
-- migration still succeeds (mirrors migration 032 pg_bigm pattern).
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_cron;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'pg_cron extension not available; skipping. Schedule rollup_task_usage_daily() via your platform''s scheduling primitive (Kubernetes CronJob, etc.).';
END
$$;

-- Health check helper. Returns NULL if the rollup has never run, or the
-- number of seconds since the last successful tick. Use this from
-- monitoring / alerts:
--   * Alert if NULL for >15 minutes after deployment (cron not scheduled).
--   * Alert if value > 900 seconds (cron stuck or job failing).
CREATE OR REPLACE FUNCTION task_usage_rollup_lag_seconds()
RETURNS DOUBLE PRECISION
LANGUAGE sql
STABLE
AS $$
    SELECT EXTRACT(EPOCH FROM (now() - last_run_finished_at))
      FROM task_usage_rollup_state
     WHERE id = 1;
$$;

```

## server/go/migrations/077_task_usage_daily_invalidation.up.sql

```sql
-- Catch joined-table changes that the `updated_at` watermark in 073 misses.
--
-- The window function in 073 finds dirty buckets via `task_usage.updated_at`.
-- That covers INSERT and UPDATE on `task_usage`, but NOT:
--   1) DELETE on `task_usage` itself (no row left to discover).
--   2) Cascade DELETE through `agent_task_queue` (issue/queue rows go away,
--      taking task_usage with them).
--   3) UPDATE of `agent_task_queue.runtime_id` — used by the runtime
--      consolidation path (`ReassignTasksToRuntime`) — which moves usage
--      from one runtime's bucket to another without touching task_usage.
--
-- Without invalidation, the rollup table diverges from raw task_usage:
-- deleted issues stay billed forever, reassigned tasks stay attributed to
-- the old runtime. The raw-table fallback path doesn't suffer from this,
-- so the two read paths would silently disagree.
--
-- Solution: an explicit `task_usage_daily_dirty` queue table populated by
-- triggers on the joined tables, drained by the rollup window function.

CREATE TABLE task_usage_daily_dirty (
    bucket_date  DATE        NOT NULL,
    workspace_id UUID        NOT NULL,
    runtime_id   UUID        NOT NULL,
    provider     TEXT        NOT NULL,
    model        TEXT        NOT NULL,
    enqueued_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (bucket_date, workspace_id, runtime_id, provider, model)
);

-- Drained by enqueued_at <= cutoff in the window function. Enqueue on
-- conflict updates enqueued_at to GREATEST(existing, new) so that an
-- invalidation arriving DURING a rollup tick (between the function's
-- snapshot and its drain step) keeps an enqueued_at > p_to and
-- survives the drain. Without that, the late invalidation would be
-- silently dropped.
CREATE INDEX idx_task_usage_daily_dirty_enqueued_at
    ON task_usage_daily_dirty (enqueued_at);

-- NOTE: The partial index supporting the legacy `updated_at IS NULL`
-- branch in the rollup window function is created in migration 078 with
-- `CREATE INDEX CONCURRENTLY` to avoid blocking writes on the hot
-- task_usage table. Until 078 has been applied, the OR branch falls
-- back to a sequential scan filtered by `updated_at IS NULL`. That is
-- acceptable because the rollup function is only invoked after this
-- migration AND the backfill have run; in steady state no rows have
-- NULL updated_at.

-- Trigger function for agent_task_queue. Two cases:
--   * UPDATE of runtime_id (old != new): usage moves between runtimes.
--     Enqueue both OLD and NEW runtime buckets so both get recomputed.
--   * DELETE: row + its task_usage children are about to vanish.
--     Enqueue OLD runtime buckets so the daily rows get cleared.
-- We resolve workspace_id via `agent` (NOT via `issue`). When a DELETE
-- cascades from issue → agent_task_queue, the issue row is already gone
-- by the time this BEFORE DELETE trigger fires, so a join on `issue`
-- would return zero rows and the enqueue would silently no-op. `agent`
-- has its own ON DELETE CASCADE to atq but is not in the issue cascade
-- chain, so it's still alive.
CREATE OR REPLACE FUNCTION enqueue_task_usage_daily_dirty_for_atq()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.runtime_id IS DISTINCT FROM NEW.runtime_id THEN
            IF OLD.runtime_id IS NOT NULL THEN
                INSERT INTO task_usage_daily_dirty (bucket_date, workspace_id, runtime_id, provider, model)
                SELECT DISTINCT DATE(tu.created_at), a.workspace_id, OLD.runtime_id, tu.provider, tu.model
                  FROM task_usage tu
                  JOIN agent a ON a.id = OLD.agent_id
                 WHERE tu.task_id = OLD.id
                ON CONFLICT (bucket_date, workspace_id, runtime_id, provider, model) DO UPDATE
                    SET enqueued_at = GREATEST(task_usage_daily_dirty.enqueued_at, EXCLUDED.enqueued_at);
            END IF;
            IF NEW.runtime_id IS NOT NULL THEN
                INSERT INTO task_usage_daily_dirty (bucket_date, workspace_id, runtime_id, provider, model)
                SELECT DISTINCT DATE(tu.created_at), a.workspace_id, NEW.runtime_id, tu.provider, tu.model
                  FROM task_usage tu
                  JOIN agent a ON a.id = NEW.agent_id
                 WHERE tu.task_id = NEW.id
                ON CONFLICT (bucket_date, workspace_id, runtime_id, provider, model) DO UPDATE
                    SET enqueued_at = GREATEST(task_usage_daily_dirty.enqueued_at, EXCLUDED.enqueued_at);
            END IF;
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        IF OLD.runtime_id IS NOT NULL THEN
            INSERT INTO task_usage_daily_dirty (bucket_date, workspace_id, runtime_id, provider, model)
            SELECT DISTINCT DATE(tu.created_at), a.workspace_id, OLD.runtime_id, tu.provider, tu.model
              FROM task_usage tu
              JOIN agent a ON a.id = OLD.agent_id
             WHERE tu.task_id = OLD.id
            ON CONFLICT (bucket_date, workspace_id, runtime_id, provider, model) DO UPDATE
                SET enqueued_at = GREATEST(task_usage_daily_dirty.enqueued_at, EXCLUDED.enqueued_at);
        END IF;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_atq_dirty_rollup
BEFORE UPDATE OF runtime_id OR DELETE ON agent_task_queue
FOR EACH ROW EXECUTE FUNCTION enqueue_task_usage_daily_dirty_for_atq();

-- Trigger function for direct task_usage DELETE (rare — direct cleanup,
-- not via cascade). UPDATE on task_usage is already covered by the
-- updated_at watermark in the window function.
-- workspace_id resolved via agent (see comment on the atq trigger
-- function for why issue is unsafe in cascade contexts).
CREATE OR REPLACE FUNCTION enqueue_task_usage_daily_dirty_for_tu()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO task_usage_daily_dirty (bucket_date, workspace_id, runtime_id, provider, model)
    SELECT DATE(OLD.created_at), a.workspace_id, atq.runtime_id, OLD.provider, OLD.model
      FROM agent_task_queue atq
      JOIN agent a ON a.id = atq.agent_id
     WHERE atq.id = OLD.task_id
       AND atq.runtime_id IS NOT NULL
    ON CONFLICT (bucket_date, workspace_id, runtime_id, provider, model) DO UPDATE
        SET enqueued_at = GREATEST(task_usage_daily_dirty.enqueued_at, EXCLUDED.enqueued_at);
    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_tu_dirty_rollup
BEFORE DELETE ON task_usage
FOR EACH ROW EXECUTE FUNCTION enqueue_task_usage_daily_dirty_for_tu();

-- Replace the rollup window function to also drain the dirty queue and
-- DELETE buckets that no longer have any source rows.
--
-- Pure-SQL CTE form so multiple calls in the same transaction (tests,
-- backfill scripts) don't collide on temp-table names.
CREATE OR REPLACE FUNCTION rollup_task_usage_daily_window(
    p_from TIMESTAMPTZ,
    p_to   TIMESTAMPTZ
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT;
BEGIN
    IF p_from >= p_to THEN
        RETURN 0;
    END IF;

    WITH
    -- Source 1: rows with updated_at in this window (steady state) plus
    -- the legacy-row OR branch for NULL updated_at (covered by partial
    -- index idx_task_usage_created_at_legacy from migration 078).
    --
    -- workspace_id is resolved via `agent`, NOT `issue`, to match the
    -- trigger functions above. There is no schema-level FK guaranteeing
    -- agent.workspace_id == issue.workspace_id, so mixing the two
    -- sources would let dirty_from_updates / recomputed disagree with
    -- dirty_from_queue's view of which workspace a task belongs to.
    -- Going through agent everywhere keeps trigger / discovery /
    -- recompute aligned without leaning on an unenforced invariant.
    dirty_from_updates AS (
        SELECT DISTINCT
            DATE(tu.created_at) AS bucket_date,
            a.workspace_id      AS workspace_id,
            atq.runtime_id      AS runtime_id,
            tu.provider         AS provider,
            tu.model            AS model
          FROM task_usage tu
          JOIN agent_task_queue atq ON atq.id      = tu.task_id
          JOIN agent            a   ON a.id        = atq.agent_id
         WHERE atq.runtime_id IS NOT NULL
           AND (
                (tu.updated_at >= p_from AND tu.updated_at < p_to)
                OR (tu.updated_at IS NULL
                    AND tu.created_at >= p_from
                    AND tu.created_at <  p_to)
           )
    ),
    -- Source 2: explicit invalidation queue (deletes + reassignments).
    dirty_from_queue AS (
        SELECT bucket_date, workspace_id, runtime_id, provider, model
          FROM task_usage_daily_dirty
         WHERE enqueued_at < p_to
    ),
    dirty_keys AS (
        SELECT * FROM dirty_from_updates
        UNION
        SELECT * FROM dirty_from_queue
    ),
    -- Recompute each dirty bucket from ground truth. Same agent-based
    -- workspace resolution as dirty_from_updates above.
    recomputed AS (
        SELECT
            dk.bucket_date,
            dk.workspace_id,
            dk.runtime_id,
            dk.provider,
            dk.model,
            SUM(tu.input_tokens)::bigint        AS input_tokens,
            SUM(tu.output_tokens)::bigint       AS output_tokens,
            SUM(tu.cache_read_tokens)::bigint   AS cache_read_tokens,
            SUM(tu.cache_write_tokens)::bigint  AS cache_write_tokens,
            COUNT(*)::bigint                    AS event_count
          FROM dirty_keys dk
          JOIN agent_task_queue atq ON atq.runtime_id = dk.runtime_id
          JOIN agent            a   ON a.id           = atq.agent_id
                                    AND a.workspace_id = dk.workspace_id
          JOIN task_usage       tu  ON tu.task_id     = atq.id
                                    AND tu.provider   = dk.provider
                                    AND tu.model      = dk.model
                                    AND DATE(tu.created_at) = dk.bucket_date
         GROUP BY 1, 2, 3, 4, 5
    ),
    -- REPLACE present buckets.
    upserted AS (
        INSERT INTO task_usage_daily AS d (
            bucket_date, workspace_id, runtime_id, provider, model,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            event_count
        )
        SELECT
            bucket_date, workspace_id, runtime_id, provider, model,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            event_count
          FROM recomputed
        ON CONFLICT (bucket_date, workspace_id, runtime_id, provider, model) DO UPDATE
            SET input_tokens       = EXCLUDED.input_tokens,
                output_tokens      = EXCLUDED.output_tokens,
                cache_read_tokens  = EXCLUDED.cache_read_tokens,
                cache_write_tokens = EXCLUDED.cache_write_tokens,
                event_count        = EXCLUDED.event_count,
                updated_at         = now()
        RETURNING 1
    ),
    -- DELETE buckets that are dirty but have no source rows anymore.
    -- Important: USING dirty_keys (not recomputed) so we can detect
    -- "all source rows gone" — if recomputed has no row for a key, the
    -- bucket is empty and should be removed.
    deleted_empty AS (
        DELETE FROM task_usage_daily d
         USING dirty_keys dk
         WHERE d.bucket_date  = dk.bucket_date
           AND d.workspace_id = dk.workspace_id
           AND d.runtime_id   = dk.runtime_id
           AND d.provider     = dk.provider
           AND d.model        = dk.model
           AND NOT EXISTS (
               SELECT 1 FROM recomputed r
                WHERE r.bucket_date  = dk.bucket_date
                  AND r.workspace_id = dk.workspace_id
                  AND r.runtime_id   = dk.runtime_id
                  AND r.provider     = dk.provider
                  AND r.model        = dk.model
           )
        RETURNING 1
    )
    SELECT (SELECT COUNT(*) FROM upserted) + (SELECT COUNT(*) FROM deleted_empty)
      INTO v_rows;

    -- Drain the consumed dirty queue rows. Anything enqueued AFTER p_to
    -- stays for the next call — keeps the contract aligned with the
    -- watermark.
    DELETE FROM task_usage_daily_dirty WHERE enqueued_at < p_to;

    RETURN v_rows;
END;
$$;

```

## server/go/migrations/078_task_usage_created_at_legacy_index.up.sql

```sql
-- Partial index supporting the rollup window function's legacy NULL
-- branch (072 added `updated_at` as nullable; rows that existed before
-- the column was added stay NULL until either backfill replaces them or
-- a subsequent UpsertTaskUsage refreshes them).
--
-- Built CONCURRENTLY because task_usage is a hot, large table — same
-- pattern as 074/075. Run this AFTER 077 is applied and BEFORE turning
-- on the read-path feature flag / scheduling pg_cron.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_usage_created_at_legacy
    ON task_usage (created_at)
    WHERE updated_at IS NULL;

```

## server/go/migrations/079_autopilot_run_skipped_status.up.sql

```sql
-- MUL-1899: re-introduce the 'skipped' terminal status for autopilot_run.
-- Migration 043 removed 'skipped' along with the broken concurrency_policy
-- feature, but the offline-runtime admission gate added in this PR needs a
-- non-failure terminal status to record dispatches that were intentionally
-- declined (e.g. assignee runtime is offline). Reusing 'failed' would
-- pollute the failure-rate signal that drives the auto-pause monitor.
ALTER TABLE autopilot_run DROP CONSTRAINT IF EXISTS autopilot_run_status_check;
ALTER TABLE autopilot_run ADD CONSTRAINT autopilot_run_status_check
    CHECK (status IN ('issue_created', 'running', 'completed', 'failed', 'skipped'));

-- Partial index on status for in-flight runs is unchanged: 'skipped' is
-- terminal so the existing index (issue_created/running) still matches.
--
-- The companion partial index for the queued-task TTL sweeper lives in
-- migration 080 — it must be created CONCURRENTLY (hot table) and therefore
-- cannot share a multi-statement file with the constraint change above.

```

## server/go/migrations/079_backfill_api_invalid_request.up.sql

```sql
-- Backfill the api_invalid_request poisoned-session classifier introduced
-- in MUL-1921. The daemon now tags failed tasks whose error matches an
-- Anthropic 400 invalid_request_error so GetLastTaskSession excludes them
-- from the (agent_id, issue_id) resume lookup, but that change is
-- forward-only: existing failed rows still carry the default
-- failure_reason='agent_error' and the resume query falls back to them
-- on the next claim, re-poisoning every retry.
--
-- Re-classify any historical row whose error text matches the same
-- canonical shape (case-insensitive substrings "400" and
-- "invalid_request_error") so deploying this PR actually unblocks issues
-- like MUL-1918 instead of just preventing future regressions.
UPDATE agent_task_queue
SET failure_reason = 'api_invalid_request'
WHERE status = 'failed'
  AND COALESCE(failure_reason, '') = 'agent_error'
  AND error ILIKE '%400%'
  AND error ILIKE '%invalid_request_error%';

```

## server/go/migrations/079_github_integration.up.sql

```sql
-- GitHub App integration: connected installations, mirrored pull request state,
-- and the link table joining issues ↔ PRs.

CREATE TABLE github_installation (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    installation_id BIGINT NOT NULL,
    account_login   TEXT NOT NULL,
    account_type    TEXT NOT NULL DEFAULT 'User'
        CHECK (account_type IN ('User', 'Organization')),
    account_avatar_url TEXT,
    connected_by_id UUID REFERENCES "user"(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (installation_id)
);

CREATE INDEX idx_github_installation_workspace ON github_installation(workspace_id);

CREATE TABLE github_pull_request (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    installation_id BIGINT NOT NULL,
    repo_owner      TEXT NOT NULL,
    repo_name       TEXT NOT NULL,
    pr_number       INTEGER NOT NULL,
    title           TEXT NOT NULL,
    state           TEXT NOT NULL
        CHECK (state IN ('open', 'closed', 'merged', 'draft')),
    html_url        TEXT NOT NULL,
    branch          TEXT,
    author_login    TEXT,
    author_avatar_url TEXT,
    merged_at       TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ,
    pr_created_at   TIMESTAMPTZ NOT NULL,
    pr_updated_at   TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, repo_owner, repo_name, pr_number)
);

CREATE INDEX idx_github_pull_request_workspace ON github_pull_request(workspace_id);

CREATE TABLE issue_pull_request (
    issue_id        UUID NOT NULL REFERENCES issue(id) ON DELETE CASCADE,
    pull_request_id UUID NOT NULL REFERENCES github_pull_request(id) ON DELETE CASCADE,
    linked_by_type  TEXT,
    linked_by_id    UUID,
    linked_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (issue_id, pull_request_id)
);

CREATE INDEX idx_issue_pull_request_pr ON issue_pull_request(pull_request_id);

```

## server/go/migrations/080_agent_task_queue_queued_index.up.sql

```sql
-- Partial index that backs the queued-task TTL sweeper added in MUL-1899
-- (sweepExpiredQueuedTasks in cmd/server/runtime_sweeper.go). The sweeper
-- runs every 30s and looks up the oldest queued tasks with:
--   WHERE status = 'queued' AND created_at < now() - interval '...'
--   ORDER BY created_at ASC LIMIT 500
-- Without a queued-only partial index on created_at this devolves into a
-- full scan once historical terminal rows accumulate (MUL-1899 baseline:
-- ~89k+ rows). The partial index stays tiny because only in-flight rows
-- live in 'queued'.
--
-- CONCURRENTLY because agent_task_queue is hot — a plain CREATE INDEX would
-- take an ACCESS EXCLUSIVE lock and block the dispatch path during build.
-- Matches the pattern in 035/067/074/075/078; 068 documents that the
-- migration runner cannot mix CONCURRENTLY with other statements in the
-- same file, so this lives in its own single-statement migration.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_queued_created_at
    ON agent_task_queue (created_at)
    WHERE status = 'queued';

```

## server/go/migrations/081_runtime_timezone.up.sql

```sql
-- Per-runtime IANA timezone, used as the bucket boundary for daily and
-- hourly token-usage aggregation (see runtime_usage.sql + the rollup
-- function in 082_rollup_runtime_timezone.up.sql).
--
-- Defaults to 'UTC' so the migration is non-disruptive: pre-existing
-- runtimes keep their current UTC-bucketed semantics until an operator
-- (web UI) or a daemon (system zoneinfo on registration) overrides it.
-- All historical task_usage_daily rows stay UTC-cut; only buckets that
-- get re-touched by new task_usage events after this migration ships
-- get rebuilt under the runtime's tz. This is intentional — the product
-- decision was "guarantee future correctness, do not backfill history".
ALTER TABLE agent_runtime
    ADD COLUMN timezone TEXT NOT NULL DEFAULT 'UTC';

COMMENT ON COLUMN agent_runtime.timezone IS
    'IANA timezone (e.g. ''Asia/Shanghai''). Bucket boundary for per-day '
    'and per-hour token usage aggregation. Defaults to UTC for runtimes '
    'that existed before MUL-1950; the daemon registration / web UI '
    'overwrites this with an operator-detected value going forward.';

```

## server/go/migrations/082_rollup_runtime_timezone.up.sql

```sql
-- Re-bucket the rollup pipeline by the owning runtime's IANA timezone
-- (added in 081), instead of the Postgres session timezone (which is
-- effectively UTC in production).
--
-- This affects three places that all derive a bucket_date from
-- `task_usage.created_at`:
--
--   1. enqueue_task_usage_daily_dirty_for_atq() — trigger that enqueues
--      dirty buckets when a task_usage's atq row changes runtime or
--      gets deleted.
--   2. enqueue_task_usage_daily_dirty_for_tu()  — trigger that enqueues
--      dirty buckets when a task_usage row is deleted directly.
--   3. rollup_task_usage_daily_window()         — the cron-driven window
--      function that drains dirty keys and recomputes their buckets.
--
-- All three previously called bare `DATE(tu.created_at)`. They now call
-- `DATE(tu.created_at AT TIME ZONE rt.timezone)`, joining `agent_runtime
-- rt` along the existing path to atq.runtime_id. Skipping any one of
-- them would split the bucket key between writers (triggers / window)
-- and the rollup table itself.
--
-- *** NO HISTORICAL BACKFILL ***
-- This migration changes only the function bodies, not any data. Rows
-- already present in `task_usage_daily` keep their previously computed
-- (UTC) `bucket_date` values. From the moment this migration ships,
-- *future* writes / re-touches of any bucket recompute the date under
-- the runtime's tz. For runtimes that stay on `'UTC'` (the column
-- default) this is a no-op; for runtimes whose operators set a non-UTC
-- tz, dates only converge as their underlying raw rows get re-touched
-- by new events. The product decision (MUL-1950) was "guarantee future
-- correctness, do not backfill history".

CREATE OR REPLACE FUNCTION enqueue_task_usage_daily_dirty_for_atq()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.runtime_id IS DISTINCT FROM NEW.runtime_id THEN
            IF OLD.runtime_id IS NOT NULL THEN
                INSERT INTO task_usage_daily_dirty (bucket_date, workspace_id, runtime_id, provider, model)
                SELECT DISTINCT
                       DATE(tu.created_at AT TIME ZONE rt.timezone),
                       a.workspace_id,
                       OLD.runtime_id,
                       tu.provider,
                       tu.model
                  FROM task_usage tu
                  JOIN agent         a  ON a.id  = OLD.agent_id
                  JOIN agent_runtime rt ON rt.id = OLD.runtime_id
                 WHERE tu.task_id = OLD.id
                ON CONFLICT (bucket_date, workspace_id, runtime_id, provider, model) DO UPDATE
                    SET enqueued_at = GREATEST(task_usage_daily_dirty.enqueued_at, EXCLUDED.enqueued_at);
            END IF;
            IF NEW.runtime_id IS NOT NULL THEN
                INSERT INTO task_usage_daily_dirty (bucket_date, workspace_id, runtime_id, provider, model)
                SELECT DISTINCT
                       DATE(tu.created_at AT TIME ZONE rt.timezone),
                       a.workspace_id,
                       NEW.runtime_id,
                       tu.provider,
                       tu.model
                  FROM task_usage tu
                  JOIN agent         a  ON a.id  = NEW.agent_id
                  JOIN agent_runtime rt ON rt.id = NEW.runtime_id
                 WHERE tu.task_id = NEW.id
                ON CONFLICT (bucket_date, workspace_id, runtime_id, provider, model) DO UPDATE
                    SET enqueued_at = GREATEST(task_usage_daily_dirty.enqueued_at, EXCLUDED.enqueued_at);
            END IF;
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        IF OLD.runtime_id IS NOT NULL THEN
            INSERT INTO task_usage_daily_dirty (bucket_date, workspace_id, runtime_id, provider, model)
            SELECT DISTINCT
                   DATE(tu.created_at AT TIME ZONE rt.timezone),
                   a.workspace_id,
                   OLD.runtime_id,
                   tu.provider,
                   tu.model
              FROM task_usage tu
              JOIN agent         a  ON a.id  = OLD.agent_id
              JOIN agent_runtime rt ON rt.id = OLD.runtime_id
             WHERE tu.task_id = OLD.id
            ON CONFLICT (bucket_date, workspace_id, runtime_id, provider, model) DO UPDATE
                SET enqueued_at = GREATEST(task_usage_daily_dirty.enqueued_at, EXCLUDED.enqueued_at);
        END IF;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION enqueue_task_usage_daily_dirty_for_tu()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO task_usage_daily_dirty (bucket_date, workspace_id, runtime_id, provider, model)
    SELECT DATE(OLD.created_at AT TIME ZONE rt.timezone),
           a.workspace_id,
           atq.runtime_id,
           OLD.provider,
           OLD.model
      FROM agent_task_queue atq
      JOIN agent         a  ON a.id  = atq.agent_id
      JOIN agent_runtime rt ON rt.id = atq.runtime_id
     WHERE atq.id = OLD.task_id
       AND atq.runtime_id IS NOT NULL
    ON CONFLICT (bucket_date, workspace_id, runtime_id, provider, model) DO UPDATE
        SET enqueued_at = GREATEST(task_usage_daily_dirty.enqueued_at, EXCLUDED.enqueued_at);
    RETURN OLD;
END;
$$;

CREATE OR REPLACE FUNCTION rollup_task_usage_daily_window(
    p_from TIMESTAMPTZ,
    p_to   TIMESTAMPTZ
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT;
BEGIN
    IF p_from >= p_to THEN
        RETURN 0;
    END IF;

    WITH
    -- Source 1: rows with updated_at in this window (steady state) plus
    -- the legacy-row OR branch for NULL updated_at (covered by partial
    -- index idx_task_usage_created_at_legacy from migration 078).
    --
    -- bucket_date is now derived under each runtime's IANA timezone via
    -- AT TIME ZONE rt.timezone. agent_runtime joins through atq.runtime_id
    -- which is already required NOT NULL in the same WHERE clause.
    dirty_from_updates AS (
        SELECT DISTINCT
            DATE(tu.created_at AT TIME ZONE rt.timezone) AS bucket_date,
            a.workspace_id      AS workspace_id,
            atq.runtime_id      AS runtime_id,
            tu.provider         AS provider,
            tu.model            AS model
          FROM task_usage tu
          JOIN agent_task_queue atq ON atq.id      = tu.task_id
          JOIN agent            a   ON a.id        = atq.agent_id
          JOIN agent_runtime    rt  ON rt.id       = atq.runtime_id
         WHERE atq.runtime_id IS NOT NULL
           AND (
                (tu.updated_at >= p_from AND tu.updated_at < p_to)
                OR (tu.updated_at IS NULL
                    AND tu.created_at >= p_from
                    AND tu.created_at <  p_to)
           )
    ),
    -- Source 2: explicit invalidation queue (deletes + reassignments).
    -- The queue rows already carry bucket_date computed under each
    -- runtime's tz at trigger time, so we don't translate again here.
    dirty_from_queue AS (
        SELECT bucket_date, workspace_id, runtime_id, provider, model
          FROM task_usage_daily_dirty
         WHERE enqueued_at < p_to
    ),
    dirty_keys AS (
        SELECT * FROM dirty_from_updates
        UNION
        SELECT * FROM dirty_from_queue
    ),
    -- Recompute each dirty bucket from ground truth. The bucket_date
    -- predicate uses the runtime's tz so it matches dirty_from_updates
    -- and the trigger functions byte-for-byte.
    recomputed AS (
        SELECT
            dk.bucket_date,
            dk.workspace_id,
            dk.runtime_id,
            dk.provider,
            dk.model,
            SUM(tu.input_tokens)::bigint        AS input_tokens,
            SUM(tu.output_tokens)::bigint       AS output_tokens,
            SUM(tu.cache_read_tokens)::bigint   AS cache_read_tokens,
            SUM(tu.cache_write_tokens)::bigint  AS cache_write_tokens,
            COUNT(*)::bigint                    AS event_count
          FROM dirty_keys dk
          JOIN agent_runtime    rt  ON rt.id           = dk.runtime_id
          JOIN agent_task_queue atq ON atq.runtime_id = dk.runtime_id
          JOIN agent            a   ON a.id           = atq.agent_id
                                    AND a.workspace_id = dk.workspace_id
          JOIN task_usage       tu  ON tu.task_id     = atq.id
                                    AND tu.provider   = dk.provider
                                    AND tu.model      = dk.model
                                    AND DATE(tu.created_at AT TIME ZONE rt.timezone) = dk.bucket_date
         GROUP BY 1, 2, 3, 4, 5
    ),
    -- REPLACE present buckets.
    upserted AS (
        INSERT INTO task_usage_daily AS d (
            bucket_date, workspace_id, runtime_id, provider, model,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            event_count
        )
        SELECT
            bucket_date, workspace_id, runtime_id, provider, model,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            event_count
          FROM recomputed
        ON CONFLICT (bucket_date, workspace_id, runtime_id, provider, model) DO UPDATE
            SET input_tokens       = EXCLUDED.input_tokens,
                output_tokens      = EXCLUDED.output_tokens,
                cache_read_tokens  = EXCLUDED.cache_read_tokens,
                cache_write_tokens = EXCLUDED.cache_write_tokens,
                event_count        = EXCLUDED.event_count,
                updated_at         = now()
        RETURNING 1
    ),
    -- DELETE buckets that are dirty but have no source rows anymore.
    deleted_empty AS (
        DELETE FROM task_usage_daily d
         USING dirty_keys dk
         WHERE d.bucket_date  = dk.bucket_date
           AND d.workspace_id = dk.workspace_id
           AND d.runtime_id   = dk.runtime_id
           AND d.provider     = dk.provider
           AND d.model        = dk.model
           AND NOT EXISTS (
               SELECT 1 FROM recomputed r
                WHERE r.bucket_date  = dk.bucket_date
                  AND r.workspace_id = dk.workspace_id
                  AND r.runtime_id   = dk.runtime_id
                  AND r.provider     = dk.provider
                  AND r.model        = dk.model
           )
        RETURNING 1
    )
    SELECT (SELECT COUNT(*) FROM upserted) + (SELECT COUNT(*) FROM deleted_empty)
      INTO v_rows;

    DELETE FROM task_usage_daily_dirty WHERE enqueued_at < p_to;

    RETURN v_rows;
END;
$$;

```

## server/go/migrations/083_attachment_chat_columns.up.sql

```sql
ALTER TABLE attachment
  ADD COLUMN chat_session_id UUID REFERENCES chat_session(id) ON DELETE CASCADE,
  ADD COLUMN chat_message_id UUID REFERENCES chat_message(id) ON DELETE CASCADE;

CREATE INDEX idx_attachment_chat_session
  ON attachment(chat_session_id)
  WHERE chat_session_id IS NOT NULL;

CREATE INDEX idx_attachment_chat_message
  ON attachment(chat_message_id)
  WHERE chat_message_id IS NOT NULL;

```

## server/go/migrations/083_runtime_visibility.up.sql

```sql
ALTER TABLE agent_runtime
    ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private', 'public'));

```

## server/go/migrations/084_squad.up.sql

```sql
-- Squad: a collaborative unit that can be @mentioned or assigned to issues.
CREATE TABLE squad (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    leader_id UUID NOT NULL REFERENCES agent(id) ON DELETE RESTRICT,
    creator_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(workspace_id, name)
);

CREATE INDEX idx_squad_workspace ON squad(workspace_id);

-- Squad members: agents or workspace members belonging to a squad.
CREATE TABLE squad_member (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    squad_id UUID NOT NULL REFERENCES squad(id) ON DELETE CASCADE,
    member_type TEXT NOT NULL CHECK (member_type IN ('agent', 'member')),
    member_id UUID NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(squad_id, member_type, member_id)
);

CREATE INDEX idx_squad_member_squad ON squad_member(squad_id);
CREATE INDEX idx_squad_member_entity ON squad_member(member_type, member_id);

-- Extend issue assignee_type to support 'squad'.
ALTER TABLE issue DROP CONSTRAINT IF EXISTS issue_assignee_type_check;
ALTER TABLE issue ADD CONSTRAINT issue_assignee_type_check
    CHECK (assignee_type IN ('member', 'agent', 'squad'));

```

## server/go/migrations/084_task_usage_dashboard_rollup.up.sql

```sql
-- Daily rollup table for the workspace `/{slug}/dashboard` page. Mirrors
-- the per-runtime rollup in migration 073 (`task_usage_daily`) but indexes
-- on a different set of dimensions:
--
--   (bucket_date, workspace_id, agent_id, project_id, model)
--
-- vs. the existing 073:
--
--   (bucket_date, workspace_id, runtime_id, provider, model)
--
-- The dashboard queries don't filter by `runtime_id` and the per-runtime
-- table doesn't carry `agent_id` / `project_id`, so we materialise a
-- dedicated rollup instead of extending the existing one and balloonng
-- its cardinality (`runtime × agent × project × model` per day vs.
-- `runtime × model`). The cron entry point + dirty-queue invalidation
-- pattern is otherwise identical.
--
-- `project_id` is the project at rollup time, snapshotted via
-- `agent_task_queue.issue_id → issue.project_id`. Re-attribution after a
-- user reassigns an issue's project lands via the `issue` trigger below;
-- historical buckets that aren't touched again stay attributed where
-- they were when the rollup ran. (Operator follow-up: re-run the backfill
-- command on the affected window if a bulk project move needs to
-- propagate to old data.)
--
-- `project_id` is nullable — issues without a project still produce
-- usage rows. We use `UNIQUE NULLS NOT DISTINCT` (PG 15+) so NULL is
-- treated as a single distinct value in the unique key, which lets
-- `INSERT ... ON CONFLICT` upsert "no-project" buckets the same way it
-- handles a specific project.
--
-- Bucket date is computed in **UTC**. The per-runtime rollup uses the
-- runtime's tz (migration 082) because each row has a single runtime;
-- this rollup aggregates *across* runtimes that may sit in different
-- tzs, and there is no single correct local boundary. The dashboard
-- frontend just renders the raw ISO date.
CREATE TABLE task_usage_dashboard_daily (
    bucket_date         DATE        NOT NULL,
    workspace_id        UUID        NOT NULL,
    agent_id            UUID        NOT NULL,
    project_id          UUID,
    model               TEXT        NOT NULL,
    input_tokens        BIGINT      NOT NULL DEFAULT 0,
    output_tokens       BIGINT      NOT NULL DEFAULT 0,
    cache_read_tokens   BIGINT      NOT NULL DEFAULT 0,
    cache_write_tokens  BIGINT      NOT NULL DEFAULT 0,
    task_count          BIGINT      NOT NULL DEFAULT 0,
    event_count         BIGINT      NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_task_usage_dashboard_daily_key
        UNIQUE NULLS NOT DISTINCT
        (bucket_date, workspace_id, agent_id, project_id, model)
);

-- Workspace-wide reads (no project filter) hit this index.
CREATE INDEX idx_task_usage_dashboard_daily_workspace_date
    ON task_usage_dashboard_daily (workspace_id, bucket_date DESC);

-- Per-project reads. Partial index because most queries either filter to
-- one project or "all" — both extremes benefit from this layout.
CREATE INDEX idx_task_usage_dashboard_daily_project_date
    ON task_usage_dashboard_daily (workspace_id, project_id, bucket_date DESC);

-- Per-agent reads (the "by agent" panel).
CREATE INDEX idx_task_usage_dashboard_daily_agent_date
    ON task_usage_dashboard_daily (workspace_id, agent_id, bucket_date DESC);

CREATE TABLE task_usage_dashboard_rollup_state (
    id                    SMALLINT    PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    watermark_at          TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01 00:00:00+00',
    last_run_started_at   TIMESTAMPTZ,
    last_run_finished_at  TIMESTAMPTZ,
    last_run_rows         BIGINT      NOT NULL DEFAULT 0,
    last_error            TEXT
);
INSERT INTO task_usage_dashboard_rollup_state (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Dirty queue for invalidations the `updated_at` watermark can't see:
--   * DELETE on `task_usage` (no row left for the watermark).
--   * DELETE cascade through `agent_task_queue` (task_usage rows gone).
--   * UPDATE of `issue.project_id` — moves the bucket to a new key.
--
-- bucket key matches the rollup table so the queue can be UNIONed into
-- `dirty_keys` in the window function with no translation. project_id is
-- nullable here for the same reason as in the rollup table.
CREATE TABLE task_usage_dashboard_dirty (
    bucket_date  DATE        NOT NULL,
    workspace_id UUID        NOT NULL,
    agent_id     UUID        NOT NULL,
    project_id   UUID,
    model        TEXT        NOT NULL,
    enqueued_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_task_usage_dashboard_dirty_key
        UNIQUE NULLS NOT DISTINCT
        (bucket_date, workspace_id, agent_id, project_id, model)
);

CREATE INDEX idx_task_usage_dashboard_dirty_enqueued_at
    ON task_usage_dashboard_dirty (enqueued_at);

-- Trigger 1: agent_task_queue BEFORE UPDATE OF issue_id OR DELETE.
--
-- Two cases:
--
--   * UPDATE OF issue_id — currently only `LinkTaskToIssue` (quick-create
--     tasks attaching to the issue the agent just produced) writes here,
--     moving the task from `issue_id IS NULL` to a real issue. If usage
--     already rolled up under the no-project bucket, we have to enqueue
--     both OLD (NULL project) AND NEW (the new issue's project) so the
--     next tick re-attributes the tokens.
--
--   * DELETE — direct atq deletions land here with the issue row still
--     alive, so `LEFT JOIN issue` resolves the project correctly.
--     Cascade DELETE driven from `DELETE FROM issue` is handled by
--     `enqueue_task_usage_dashboard_dirty_for_issue_delete` below (which
--     fires *before* the cascade, while `issue.project_id` is still
--     readable); this trigger may also fire during that cascade, but the
--     join returns no row → workspace_id is missing, so the JOIN on
--     `agent` keeps the enqueue safe and the resulting NULL-project key
--     no-ops on recompute (deleted_empty path).
CREATE OR REPLACE FUNCTION enqueue_task_usage_dashboard_dirty_for_atq()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.issue_id IS DISTINCT FROM NEW.issue_id THEN
            -- OLD side: project_id of OLD.issue_id (NULL when OLD.issue_id IS NULL,
            -- e.g. the quick-create starting state).
            INSERT INTO task_usage_dashboard_dirty (
                bucket_date, workspace_id, agent_id, project_id, model
            )
            SELECT DISTINCT
                DATE(tu.created_at),
                a.workspace_id,
                OLD.agent_id,
                i_old.project_id,
                tu.model
              FROM task_usage tu
              JOIN agent a ON a.id = OLD.agent_id
              LEFT JOIN issue i_old ON i_old.id = OLD.issue_id
             WHERE tu.task_id = OLD.id
            ON CONFLICT ON CONSTRAINT uq_task_usage_dashboard_dirty_key DO UPDATE
                SET enqueued_at = GREATEST(task_usage_dashboard_dirty.enqueued_at, EXCLUDED.enqueued_at);

            -- NEW side: project_id of NEW.issue_id.
            INSERT INTO task_usage_dashboard_dirty (
                bucket_date, workspace_id, agent_id, project_id, model
            )
            SELECT DISTINCT
                DATE(tu.created_at),
                a.workspace_id,
                NEW.agent_id,
                i_new.project_id,
                tu.model
              FROM task_usage tu
              JOIN agent a ON a.id = NEW.agent_id
              LEFT JOIN issue i_new ON i_new.id = NEW.issue_id
             WHERE tu.task_id = NEW.id
            ON CONFLICT ON CONSTRAINT uq_task_usage_dashboard_dirty_key DO UPDATE
                SET enqueued_at = GREATEST(task_usage_dashboard_dirty.enqueued_at, EXCLUDED.enqueued_at);
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO task_usage_dashboard_dirty (
            bucket_date, workspace_id, agent_id, project_id, model
        )
        SELECT DISTINCT
            DATE(tu.created_at),
            a.workspace_id,
            OLD.agent_id,
            i.project_id,
            tu.model
          FROM task_usage tu
          JOIN agent a ON a.id = OLD.agent_id
          LEFT JOIN issue i ON i.id = OLD.issue_id
         WHERE tu.task_id = OLD.id
        ON CONFLICT ON CONSTRAINT uq_task_usage_dashboard_dirty_key DO UPDATE
            SET enqueued_at = GREATEST(task_usage_dashboard_dirty.enqueued_at, EXCLUDED.enqueued_at);
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_atq_dirty_dashboard
BEFORE UPDATE OF issue_id OR DELETE ON agent_task_queue
FOR EACH ROW EXECUTE FUNCTION enqueue_task_usage_dashboard_dirty_for_atq();

-- Trigger 1b: issue BEFORE DELETE.
--
-- `DELETE FROM issue` cascades to `agent_task_queue` and onward to
-- `task_usage`. By the time the atq BEFORE DELETE trigger runs, the
-- issue row is gone and `LEFT JOIN issue` returns NULL for project_id,
-- so the atq trigger would enqueue a NULL-project key — the rollup row
-- under the original project would never get cleared and would keep
-- billing the workspace for tokens that no longer have a source.
--
-- This trigger fires BEFORE the cascade, while `OLD.project_id` is still
-- readable, and enqueues one dirty row per (date, agent, model) the
-- issue's tasks contributed to. The next rollup tick recomputes the
-- bucket, finds no source rows under the original project, and drops it
-- (deleted_empty path).
CREATE OR REPLACE FUNCTION enqueue_task_usage_dashboard_dirty_for_issue_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO task_usage_dashboard_dirty (
        bucket_date, workspace_id, agent_id, project_id, model
    )
    SELECT DISTINCT
        DATE(tu.created_at),
        OLD.workspace_id,
        atq.agent_id,
        OLD.project_id,
        tu.model
      FROM agent_task_queue atq
      JOIN task_usage tu ON tu.task_id = atq.id
     WHERE atq.issue_id = OLD.id
    ON CONFLICT ON CONSTRAINT uq_task_usage_dashboard_dirty_key DO UPDATE
        SET enqueued_at = GREATEST(task_usage_dashboard_dirty.enqueued_at, EXCLUDED.enqueued_at);
    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_issue_delete_dirty_dashboard
BEFORE DELETE ON issue
FOR EACH ROW EXECUTE FUNCTION enqueue_task_usage_dashboard_dirty_for_issue_delete();

-- Trigger 2: task_usage BEFORE DELETE.
-- Rare in practice (no direct DELETE call sites today) but ensures the
-- rollup converges if one is added. UPDATE / INSERT are caught by the
-- updated_at watermark in the window function.
CREATE OR REPLACE FUNCTION enqueue_task_usage_dashboard_dirty_for_tu()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO task_usage_dashboard_dirty (
        bucket_date, workspace_id, agent_id, project_id, model
    )
    SELECT
        DATE(OLD.created_at),
        a.workspace_id,
        atq.agent_id,
        i.project_id,
        OLD.model
      FROM agent_task_queue atq
      JOIN agent a ON a.id = atq.agent_id
      LEFT JOIN issue i ON i.id = atq.issue_id
     WHERE atq.id = OLD.task_id
    ON CONFLICT ON CONSTRAINT uq_task_usage_dashboard_dirty_key DO UPDATE
        SET enqueued_at = GREATEST(task_usage_dashboard_dirty.enqueued_at, EXCLUDED.enqueued_at);
    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_tu_dirty_dashboard
BEFORE DELETE ON task_usage
FOR EACH ROW EXECUTE FUNCTION enqueue_task_usage_dashboard_dirty_for_tu();

-- Trigger 3: issue BEFORE UPDATE OF project_id.
-- Re-attribute every (date, agent, model) bucket touched by tasks under
-- this issue: enqueue OLD project_id (so it stops claiming the tokens)
-- AND NEW project_id (so it picks them up). Both go through the same
-- dirty queue; the window function recomputes from the live join in
-- recomputed CTE, which now sees NEW.project_id, so the OLD bucket
-- either drops to 0 (deleted_empty path) or shrinks.
CREATE OR REPLACE FUNCTION enqueue_task_usage_dashboard_dirty_for_issue_project()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.project_id IS DISTINCT FROM NEW.project_id THEN
        -- OLD project buckets.
        INSERT INTO task_usage_dashboard_dirty (
            bucket_date, workspace_id, agent_id, project_id, model
        )
        SELECT DISTINCT
            DATE(tu.created_at),
            NEW.workspace_id,
            atq.agent_id,
            OLD.project_id,
            tu.model
          FROM agent_task_queue atq
          JOIN task_usage       tu ON tu.task_id = atq.id
         WHERE atq.issue_id = NEW.id
        ON CONFLICT ON CONSTRAINT uq_task_usage_dashboard_dirty_key DO UPDATE
            SET enqueued_at = GREATEST(task_usage_dashboard_dirty.enqueued_at, EXCLUDED.enqueued_at);

        -- NEW project buckets.
        INSERT INTO task_usage_dashboard_dirty (
            bucket_date, workspace_id, agent_id, project_id, model
        )
        SELECT DISTINCT
            DATE(tu.created_at),
            NEW.workspace_id,
            atq.agent_id,
            NEW.project_id,
            tu.model
          FROM agent_task_queue atq
          JOIN task_usage       tu ON tu.task_id = atq.id
         WHERE atq.issue_id = NEW.id
        ON CONFLICT ON CONSTRAINT uq_task_usage_dashboard_dirty_key DO UPDATE
            SET enqueued_at = GREATEST(task_usage_dashboard_dirty.enqueued_at, EXCLUDED.enqueued_at);
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_issue_project_dirty_dashboard
BEFORE UPDATE OF project_id ON issue
FOR EACH ROW EXECUTE FUNCTION enqueue_task_usage_dashboard_dirty_for_issue_project();

-- Window function. Same shape as 077's rollup_task_usage_daily_window:
--   1. Discover dirty keys from updated_at watermark + the explicit queue.
--   2. Recompute each from raw via the agent_task_queue + issue join.
--   3. Upsert present buckets, delete buckets that recomputed to nothing.
--   4. Drain the queue rows whose enqueued_at < p_to.
--
-- IDEMPOTENCY: re-running the same window yields the same final state,
-- because each touched key is rebuilt from raw, not deltaed.
CREATE OR REPLACE FUNCTION rollup_task_usage_dashboard_daily_window(
    p_from TIMESTAMPTZ,
    p_to   TIMESTAMPTZ
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT;
BEGIN
    IF p_from >= p_to THEN
        RETURN 0;
    END IF;

    WITH
    dirty_from_updates AS (
        SELECT DISTINCT
            DATE(tu.created_at) AS bucket_date,
            a.workspace_id      AS workspace_id,
            atq.agent_id        AS agent_id,
            i.project_id        AS project_id,
            tu.model            AS model
          FROM task_usage tu
          JOIN agent_task_queue atq ON atq.id      = tu.task_id
          JOIN agent            a   ON a.id        = atq.agent_id
          LEFT JOIN issue       i   ON i.id        = atq.issue_id
         WHERE (
                (tu.updated_at >= p_from AND tu.updated_at < p_to)
                -- Legacy `updated_at IS NULL` rows: 077 handles this via a
                -- partial index. We rely on the same `idx_task_usage_created_at_legacy`
                -- (migration 078) for this branch.
                OR (tu.updated_at IS NULL
                    AND tu.created_at >= p_from
                    AND tu.created_at <  p_to)
           )
    ),
    dirty_from_queue AS (
        SELECT bucket_date, workspace_id, agent_id, project_id, model
          FROM task_usage_dashboard_dirty
         WHERE enqueued_at < p_to
    ),
    dirty_keys AS (
        SELECT * FROM dirty_from_updates
        UNION
        SELECT * FROM dirty_from_queue
    ),
    recomputed AS (
        SELECT
            dk.bucket_date,
            dk.workspace_id,
            dk.agent_id,
            dk.project_id,
            dk.model,
            SUM(tu.input_tokens)::bigint       AS input_tokens,
            SUM(tu.output_tokens)::bigint      AS output_tokens,
            SUM(tu.cache_read_tokens)::bigint  AS cache_read_tokens,
            SUM(tu.cache_write_tokens)::bigint AS cache_write_tokens,
            COUNT(DISTINCT tu.task_id)::bigint AS task_count,
            COUNT(*)::bigint                   AS event_count
          FROM dirty_keys dk
          JOIN agent_task_queue atq ON atq.agent_id    = dk.agent_id
          JOIN agent            a   ON a.id            = atq.agent_id
                                    AND a.workspace_id = dk.workspace_id
          LEFT JOIN issue       i   ON i.id            = atq.issue_id
          JOIN task_usage       tu  ON tu.task_id      = atq.id
                                    AND tu.model       = dk.model
                                    AND DATE(tu.created_at) = dk.bucket_date
         WHERE (i.project_id IS NOT DISTINCT FROM dk.project_id)
         GROUP BY 1, 2, 3, 4, 5
    ),
    upserted AS (
        INSERT INTO task_usage_dashboard_daily AS d (
            bucket_date, workspace_id, agent_id, project_id, model,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            task_count, event_count
        )
        SELECT
            bucket_date, workspace_id, agent_id, project_id, model,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            task_count, event_count
          FROM recomputed
        ON CONFLICT ON CONSTRAINT uq_task_usage_dashboard_daily_key DO UPDATE
            SET input_tokens       = EXCLUDED.input_tokens,
                output_tokens      = EXCLUDED.output_tokens,
                cache_read_tokens  = EXCLUDED.cache_read_tokens,
                cache_write_tokens = EXCLUDED.cache_write_tokens,
                task_count         = EXCLUDED.task_count,
                event_count        = EXCLUDED.event_count,
                updated_at         = now()
        RETURNING 1
    ),
    deleted_empty AS (
        DELETE FROM task_usage_dashboard_daily d
         USING dirty_keys dk
         WHERE d.bucket_date  = dk.bucket_date
           AND d.workspace_id = dk.workspace_id
           AND d.agent_id     = dk.agent_id
           AND d.project_id IS NOT DISTINCT FROM dk.project_id
           AND d.model        = dk.model
           AND NOT EXISTS (
               SELECT 1 FROM recomputed r
                WHERE r.bucket_date  = dk.bucket_date
                  AND r.workspace_id = dk.workspace_id
                  AND r.agent_id     = dk.agent_id
                  AND r.project_id IS NOT DISTINCT FROM dk.project_id
                  AND r.model        = dk.model
           )
        RETURNING 1
    )
    SELECT (SELECT COUNT(*) FROM upserted) + (SELECT COUNT(*) FROM deleted_empty)
      INTO v_rows;

    DELETE FROM task_usage_dashboard_dirty WHERE enqueued_at < p_to;

    RETURN v_rows;
END;
$$;

-- Cron entry. Mirrors `rollup_task_usage_daily` (migration 073) — same
-- advisory-lock + watermark + error-recovery shape. Uses lock id 4244
-- so it serialises independently of the per-runtime rollup (4242).
CREATE OR REPLACE FUNCTION rollup_task_usage_dashboard_daily()
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_lock_ok BOOLEAN;
    v_from    TIMESTAMPTZ;
    v_to      TIMESTAMPTZ;
    v_rows    BIGINT := 0;
BEGIN
    SELECT pg_try_advisory_lock(4244) INTO v_lock_ok;
    IF NOT v_lock_ok THEN
        RETURN 0;
    END IF;

    BEGIN
        UPDATE task_usage_dashboard_rollup_state
           SET last_run_started_at = now(),
               last_error          = NULL
         WHERE id = 1
        RETURNING watermark_at INTO v_from;

        v_to := now() - INTERVAL '5 minutes';

        IF v_from < v_to THEN
            v_rows := rollup_task_usage_dashboard_daily_window(v_from, v_to);

            UPDATE task_usage_dashboard_rollup_state
               SET watermark_at         = v_to,
                   last_run_finished_at = now(),
                   last_run_rows        = v_rows
             WHERE id = 1;
        ELSE
            UPDATE task_usage_dashboard_rollup_state
               SET last_run_finished_at = now(),
                   last_run_rows        = 0
             WHERE id = 1;
        END IF;

        PERFORM pg_advisory_unlock(4244);
        RETURN v_rows;
    EXCEPTION WHEN OTHERS THEN
        UPDATE task_usage_dashboard_rollup_state
           SET last_error           = SQLERRM,
               last_run_finished_at = now()
         WHERE id = 1;
        PERFORM pg_advisory_unlock(4244);
        RAISE;
    END;
END;
$$;

-- Health-check helper mirroring task_usage_rollup_lag_seconds() (076).
-- Alert via monitoring on NULL > 15 min after deploy, or value > 900s.
CREATE OR REPLACE FUNCTION task_usage_dashboard_rollup_lag_seconds()
RETURNS DOUBLE PRECISION
LANGUAGE sql
STABLE
AS $$
    SELECT EXTRACT(EPOCH FROM (now() - last_run_finished_at))
      FROM task_usage_dashboard_rollup_state
     WHERE id = 1;
$$;

-- NOTE: cron job is NOT scheduled by this migration — same convention as
-- 076 for the per-runtime rollup. Operator playbook:
--   1) Apply migrations through 084.
--   2) Run `go run ./cmd/backfill_task_usage_dashboard_daily`.
--   3) Set USAGE_DASHBOARD_ROLLUP_ENABLED=true on the API and roll out.
--   4) As superuser:
--        SELECT cron.schedule(
--          'rollup_task_usage_dashboard_daily',
--          '*/5 * * * *',
--          $$SELECT rollup_task_usage_dashboard_daily()$$
--        );

```

## server/go/migrations/085_squad_archive.up.sql

```sql
ALTER TABLE squad ADD COLUMN archived_at TIMESTAMPTZ;
ALTER TABLE squad ADD COLUMN archived_by UUID;

```

## server/go/migrations/086_squad_avatar.up.sql

```sql
ALTER TABLE squad ADD COLUMN avatar_url TEXT;

```

## server/go/migrations/087_squad_name_not_unique.up.sql

```sql
-- Squad names need not be unique within a workspace — different teams may
-- legitimately want the same label (e.g. "Research"), and the leader/UUID
-- already disambiguates them.
ALTER TABLE squad DROP CONSTRAINT IF EXISTS squad_workspace_id_name_key;

```

## server/go/migrations/088_squad_instructions.up.sql

```sql
ALTER TABLE squad ADD COLUMN instructions TEXT NOT NULL DEFAULT '';

```

## server/go/migrations/089_squad_no_action_activity_index.up.sql

```sql
CREATE INDEX IF NOT EXISTS idx_activity_log_squad_no_action_task
    ON activity_log (issue_id, actor_id, ((details->>'task_id')))
    WHERE actor_type = 'agent'
      AND action = 'squad_leader_evaluated'
      AND details->>'outcome' = 'no_action';

```

## server/go/migrations/090_task_is_leader.up.sql

```sql
-- agent_task_queue.is_leader_task marks a task as enqueued in the squad-leader
-- role. The squad-leader self-trigger guard previously skipped a comment
-- whenever its author equalled `squad.LeaderID`, which mis-fired for an agent
-- that is simultaneously a leader and a worker of the same squad: a comment
-- posted by the agent in its worker role never woke its leader role. The
-- guard now consults the agent's most recent task on the issue and skips
-- only when that task was itself a leader task.
ALTER TABLE agent_task_queue
    ADD COLUMN is_leader_task BOOLEAN NOT NULL DEFAULT FALSE;

```

## server/go/migrations/091_autopilot_webhook_triggers.up.sql

```sql
-- Webhook trigger ingress: enforce uniqueness on webhook tokens so the
-- public ingress route /api/webhooks/autopilots/{token} can resolve a trigger
-- in O(1) without ambiguity. Partial index keeps the constraint scoped to
-- webhook-kind triggers only — schedule/api triggers leave webhook_token NULL
-- and don't participate in the unique key.
CREATE UNIQUE INDEX IF NOT EXISTS idx_autopilot_trigger_webhook_token
ON autopilot_trigger(webhook_token)
WHERE kind = 'webhook' AND webhook_token IS NOT NULL;

```

## server/go/migrations/091_issue_start_date.up.sql

```sql
-- issue.start_date pairs with issue.due_date so an issue can express a planned
-- start as well as a deadline. Backs Project Gantt charts (MUL-1881) and the
-- progressive-disclosure "Add property" surface in the issue sidebar.
ALTER TABLE issue
    ADD COLUMN start_date TIMESTAMPTZ;

```

## server/go/migrations/091_pr_ci_conflict.up.sql

```sql
-- PR CI checks + merge conflict status. Adds head_sha + mergeable_state to
-- github_pull_request, plus a per-check_suite table whose rows are filtered
-- by the PR's current head_sha at query time. This lets late-arriving suites
-- for an old head SHA land in the table without polluting the current view.

ALTER TABLE github_pull_request
    ADD COLUMN head_sha TEXT NOT NULL DEFAULT '',
    ADD COLUMN mergeable_state TEXT;

CREATE TABLE github_pull_request_check_suite (
    pr_id        UUID NOT NULL REFERENCES github_pull_request(id) ON DELETE CASCADE,
    suite_id     BIGINT NOT NULL,
    head_sha     TEXT NOT NULL,
    app_id       BIGINT NOT NULL,
    conclusion   TEXT,
    status       TEXT NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (pr_id, suite_id)
);

CREATE INDEX idx_github_pr_check_suite_aggregate
    ON github_pull_request_check_suite (pr_id, head_sha, app_id, updated_at DESC);

```

## server/go/migrations/092_pr_stats.up.sql

```sql
-- PR diff stats (additions / deletions / changed_files) for the card layout.
-- Source: top-level `pull_request` object on every pull_request webhook event
-- (opened / synchronize / edited / labeled / ...). NOT NULL DEFAULT 0 means
-- legacy rows that pre-date this migration read as zero, which the frontend
-- detects via `total === 0` and hides the entire stats row — so the card never
-- renders a misleading "+0 −0 · 0 files" caption for rows that just haven't
-- been refreshed by a webhook yet.

ALTER TABLE github_pull_request
    ADD COLUMN additions     INT NOT NULL DEFAULT 0,
    ADD COLUMN deletions     INT NOT NULL DEFAULT 0,
    ADD COLUMN changed_files INT NOT NULL DEFAULT 0;

```

## server/go/migrations/093_webhook_deliveries.up.sql

```sql
-- Webhook delivery layer: separates "we received an inbound HTTP webhook" from
-- "we created an autopilot run". Splitting the two lets us record duplicate
-- attempts, signature outcomes, ignored/skipped deliveries, and offers a
-- replay path — all of which the previous shape (writing straight into
-- autopilot_run.trigger_payload) could not express.
--
-- Scope of this migration:
--   1. Add `provider` + `signing_secret` to autopilot_trigger so a webhook
--      trigger can optionally carry per-provider configuration for signature
--      verification. signing_secret is plaintext at rest, mirroring how
--      webhook_token already lives — HMAC verification needs the cleartext
--      and there is no general secrets-at-rest infrastructure to layer on
--      yet (see issue MUL-2334 for the design rationale).
--   2. Create webhook_delivery, one row per inbound HTTP request the public
--      ingress endpoint accepted (including rejected / ignored outcomes).
--      Duplicate requests don't get their own row — they bump attempt_count
--      on the existing dedupe target. The autopilot_run table is kept intact
--      and continues to represent the downstream execution — both views are
--      needed.

ALTER TABLE autopilot_trigger
    ADD COLUMN provider TEXT NOT NULL DEFAULT 'generic'
        CHECK (provider IN ('generic', 'github')),
    ADD COLUMN signing_secret TEXT;

CREATE TABLE IF NOT EXISTS webhook_delivery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    autopilot_id UUID NOT NULL REFERENCES autopilot(id) ON DELETE CASCADE,
    trigger_id UUID NOT NULL REFERENCES autopilot_trigger(id) ON DELETE CASCADE,
    provider TEXT NOT NULL
        CHECK (provider IN ('generic', 'github')),
    event TEXT NOT NULL DEFAULT 'webhook.received',
    -- dedupe_key is extracted from request headers per-provider:
    --   github  -> X-GitHub-Delivery
    --   generic -> Idempotency-Key
    -- NULL means "no provider-supplied dedupe identifier"; the partial unique
    -- index below skips these rows so each NULL-keyed delivery is treated as
    -- distinct (correct behavior for clients that don't implement idempotency
    -- headers — the alternative would collapse all of them onto one row).
    dedupe_key TEXT,
    dedupe_source TEXT,
    signature_status TEXT NOT NULL DEFAULT 'not_required'
        CHECK (signature_status IN ('not_required', 'valid', 'invalid', 'missing')),
    -- Delivery status tracks the *ingress*, not the autopilot run:
    --   queued     — INSERTed, dispatch not yet attempted
    --   dispatched — handed off to AutopilotService; autopilot_run_id is set.
    --                A run that was admission-skipped (e.g. runtime offline)
    --                still lives here — the skipped-ness is recorded on
    --                autopilot_run.status, not on the delivery, so the
    --                Deliveries enum stays unambiguous.
    --   rejected   — signature verification failed (invalid or missing)
    --   ignored    — trigger disabled / autopilot paused / archived
    --   failed     — dispatch attempted and errored
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'dispatched', 'rejected', 'ignored', 'failed')),
    attempt_count INTEGER NOT NULL DEFAULT 1,
    -- Selected headers we want to keep for debugging (user-agent, event,
    -- delivery id, idempotency key, signature presence). NOT the raw header
    -- map — never store auth tokens or signature values plaintext.
    selected_headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_type TEXT,
    -- raw_body holds the exact bytes we received, capped at the ingress body
    -- limit (256 KiB). Required for replay and to debug normalization issues.
    -- No TTL/retention enforced here; if delivery volume becomes a storage
    -- concern, add a follow-up migration with a retention job rather than
    -- baking the policy into the schema.
    raw_body BYTEA,
    response_status INTEGER,
    response_body TEXT,
    autopilot_run_id UUID REFERENCES autopilot_run(id) ON DELETE SET NULL,
    replayed_from_delivery_id UUID REFERENCES webhook_delivery(id) ON DELETE SET NULL,
    error TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Listing deliveries per autopilot, newest first.
CREATE INDEX IF NOT EXISTS idx_webhook_delivery_autopilot
    ON webhook_delivery(autopilot_id, created_at DESC);

-- Provider-supplied dedupe identifiers must be unique per trigger. Partial so
-- that NULL keys (no Idempotency-Key / X-GitHub-Delivery header) never
-- collide. Terminal-but-not-successful outcomes (`rejected`, `failed`) are
-- excluded so a transient ingress failure or a misconfigured secret does
-- not strand the operator: providers like GitHub keep X-GitHub-Delivery
-- stable across retries, and a permanently-blocking row would prevent the
-- next retry from ever being dispatched.
CREATE UNIQUE INDEX IF NOT EXISTS idx_webhook_delivery_dedupe
    ON webhook_delivery(trigger_id, dedupe_key)
    WHERE dedupe_key IS NOT NULL AND status NOT IN ('rejected', 'failed');

-- Lookup by linked run (sync flows, gc check, run-detail "what triggered me").
CREATE INDEX IF NOT EXISTS idx_webhook_delivery_run
    ON webhook_delivery(autopilot_run_id)
    WHERE autopilot_run_id IS NOT NULL;

```

## server/go/migrations/094_onboarding_questionnaire_v2.up.sql

```sql
-- Onboarding questionnaire schema v1 → v2 migration.
--
-- v1 shape: { team_size, team_size_other, role, role_other, use_case, use_case_other }
-- v2 shape: { source, source_*, role, role_*, use_case, use_case_*, version: 2 }
--
-- `team_size` is dropped entirely. `role` and `use_case` are remapped
-- to the new enum vocabulary. Historical nulls stay null (NOT marked
-- `*_skipped: true` — the v1 flow forbade skips, so attributing skip
-- intent retroactively would pollute analytics). `source` is null for
-- everyone (we never asked).

UPDATE "user"
SET onboarding_questionnaire = jsonb_strip_nulls(jsonb_build_object(
        'source', NULL,
        'source_other', NULL,
        'source_skipped', false,
        'role', CASE onboarding_questionnaire->>'role'
            WHEN 'developer'    THEN 'engineer'
            WHEN 'product_lead' THEN 'product'
            WHEN 'writer'       THEN 'writer'
            WHEN 'founder'      THEN 'founder'
            WHEN 'other'        THEN 'other'
            ELSE NULL
        END,
        'role_other', onboarding_questionnaire->>'role_other',
        'role_skipped', false,
        'use_case', CASE onboarding_questionnaire->>'use_case'
            WHEN 'coding'           THEN 'ship_code'
            WHEN 'planning'         THEN 'manage_team'
            WHEN 'writing_research' THEN 'write_publish'
            WHEN 'explore'          THEN 'evaluate'
            WHEN 'other'            THEN 'other'
            ELSE NULL
        END,
        'use_case_other', onboarding_questionnaire->>'use_case_other',
        'use_case_skipped', false,
        'version', 2
    ))
WHERE onboarding_questionnaire IS NOT NULL
  AND (onboarding_questionnaire ? 'team_size'
       OR onboarding_questionnaire ? 'role'
       OR onboarding_questionnaire ? 'use_case')
  AND (onboarding_questionnaire->>'version' IS NULL
       OR onboarding_questionnaire->>'version' = '1');

```

## server/go/migrations/095_agent_thinking_level.up.sql

```sql
-- Per-agent thinking / reasoning effort setting. Stored as the
-- runtime-native string (e.g. Claude's "low|medium|high|xhigh|max",
-- Codex's "none|minimal|low|medium|high|xhigh") rather than a
-- cross-runtime abstraction, so the user-visible value matches what
-- each CLI's own UI advertises (see MUL-2339). NULL means "use the
-- runtime/model default" — every backend treats this as "do not
-- inject --effort / reasoning_effort" and lets the CLI pick.
ALTER TABLE agent ADD COLUMN thinking_level TEXT;

```

## server/go/migrations/095_backfill_starter_content_state.up.sql

```sql
-- Backfill `starter_content_state` for users who finished onboarding between
-- the original 054 migration and the removal of the starter-content kit
-- (MUL-2438). 054 only covered pre-feature users; everyone onboarded in the
-- window since then could still be sitting at NULL. Old desktop clients gate
-- the legacy StarterContentPrompt on `starter_content_state IS NULL`, and the
-- /api/me/starter-content/import|dismiss routes no longer exist, so leaving
-- these rows NULL would surface a dialog whose buttons 404. Mark them
-- 'imported' to match the new helper's claim semantics.
UPDATE "user"
   SET starter_content_state = 'imported'
 WHERE onboarded_at IS NOT NULL
   AND starter_content_state IS NULL;

```

## server/go/migrations/096_autopilot_squad_assignee.up.sql

```sql
-- Autopilot: support assigning to a squad (MUL-2429).
--
-- Path A "Squad-as-Leader": when an autopilot's assignee is a squad, dispatch
-- still resolves to a single agent (squad.leader_id) — same semantics as a
-- human manually assigning an issue to that squad. We model this by adding an
-- assignee_type column and dropping the hard FK on assignee_id so the same
-- UUID column can reference either agent(id) or squad(id) depending on the
-- type. Referential integrity is enforced in the application layer (handler
-- validates the squad/agent is in the workspace; dispatch re-resolves at run
-- time and skip-records doomed runs instead of crashing).

ALTER TABLE autopilot
    DROP CONSTRAINT IF EXISTS autopilot_assignee_id_fkey;

ALTER TABLE autopilot
    ADD COLUMN assignee_type TEXT NOT NULL DEFAULT 'agent'
        CHECK (assignee_type IN ('agent', 'squad'));

-- Composite index lets lookups discriminate by type cheaply, e.g. "all
-- autopilots whose assignee is squad X" without scanning the whole table.
-- The legacy idx_autopilot_assignee(assignee_id) stays for plain id lookups.
CREATE INDEX IF NOT EXISTS idx_autopilot_assignee_type_id
    ON autopilot (assignee_type, assignee_id);

-- autopilot_run.squad_id: attribution hook. Populated when ap.assignee_type =
-- 'squad' so reports can group runs by squad even though the executing agent
-- (and the cost it accrues) is the leader. First version does not consume
-- the column; it exists so we never need a backfill.
ALTER TABLE autopilot_run
    ADD COLUMN squad_id UUID REFERENCES squad(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_autopilot_run_squad_id
    ON autopilot_run (squad_id) WHERE squad_id IS NOT NULL;

```

## server/go/migrations/096_pending_check_suite.up.sql

```sql
-- Stash for check_suite webhook events that arrive before the matching PR
-- row has been mirrored (the `pull_request` and `check_suite` webhooks are
-- delivered independently and GitHub does not guarantee order). When the
-- corresponding `pull_request` event upserts the PR row, the handler drains
-- this table for that (workspace, repo, pr_number) and replays each row
-- through the normal check_suite upsert path, then deletes the pending row.
--
-- We key by (workspace_id, repo_owner, repo_name, pr_number, suite_id) so
-- repeated deliveries of the same suite while the PR is still missing are
-- idempotent — the newer payload simply overwrites the older.
CREATE TABLE github_pending_check_suite (
    workspace_id     UUID NOT NULL,
    installation_id  BIGINT NOT NULL,
    repo_owner       TEXT NOT NULL,
    repo_name        TEXT NOT NULL,
    pr_number        INTEGER NOT NULL,
    suite_id         BIGINT NOT NULL,
    head_sha         TEXT NOT NULL,
    app_id           BIGINT NOT NULL,
    conclusion       TEXT,
    status           TEXT NOT NULL,
    suite_updated_at TIMESTAMPTZ NOT NULL,
    received_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, repo_owner, repo_name, pr_number, suite_id)
);

CREATE INDEX idx_github_pending_check_suite_received_at
    ON github_pending_check_suite(received_at);

```

## server/go/migrations/096_user_profile_description.up.sql

```sql
-- Per-user free-form profile description. Read by the daemon at task
-- start and injected into the agent brief under "## Requesting User" so
-- the agent has cheap, durable context about who is asking (role,
-- stack, preferences). NOT NULL DEFAULT '' so userToResponse never has
-- to coalesce nullable state on the read path.

ALTER TABLE "user"
    ADD COLUMN profile_description TEXT NOT NULL DEFAULT '';

```

## server/go/migrations/097_autopilot_project_id.up.sql

```sql
ALTER TABLE autopilot
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES project(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_autopilot_project ON autopilot(project_id);

```

## server/go/migrations/098_contact_sales_inquiries.up.sql

```sql
-- Contact-sales inquiries submitted from the public marketing site.
--
-- The endpoint is unauthenticated so the row has no user_id / workspace_id.
-- Spam mitigation is handled by per-IP rate limiting + business-email
-- validation at the handler layer. We store the IP only so the abuse signal
-- survives a process restart; we never expose it back through the API.

CREATE TABLE contact_sales_inquiry (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name          TEXT NOT NULL,
    last_name           TEXT NOT NULL,
    business_email      TEXT NOT NULL,
    company_name        TEXT NOT NULL,
    company_size        TEXT NOT NULL,
    country_region      TEXT NOT NULL,
    use_case            TEXT NOT NULL,
    goals               TEXT NOT NULL DEFAULT '',
    consent_outreach    BOOLEAN NOT NULL DEFAULT false,
    consent_updates     BOOLEAN NOT NULL DEFAULT false,
    submitter_ip        INET,
    user_agent          TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_contact_sales_inquiry_created ON contact_sales_inquiry(created_at DESC);
CREATE INDEX idx_contact_sales_inquiry_email_created ON contact_sales_inquiry(business_email, created_at DESC);

```

## server/go/migrations/098_user_onboarding_runtime_choice.up.sql

```sql
-- v3 reverts the v2 attempt at persisting Step 3 runtime choice on the user
-- row. The two columns were added in an earlier draft of this migration
-- (wip/onboarding-v2, never shipped to production) and the design moved to
-- a frontend Zustand transient store instead — onboarding state collapses
-- back to the single `onboarded_at` field.
--
-- IF EXISTS guards make this safe whether the original v2 migration ran
-- locally or not.
ALTER TABLE "user"
    DROP CONSTRAINT IF EXISTS user_onboarding_runtime_choice_check;

ALTER TABLE "user"
    DROP COLUMN IF EXISTS onboarding_runtime_skipped;

ALTER TABLE "user"
    DROP COLUMN IF EXISTS onboarding_runtime_id;

```

## server/go/migrations/100_user_timezone.up.sql

```sql
-- Per-user IANA timezone for *viewing* reports — the third leg of the
-- Operational / Scheduling / Viewing trio.
--
-- Distinct from:
--   * agent_runtime.timezone (Operational): where a runtime physically runs.
--     That column is dropped later in this migration set — the hour-of-day
--     activity heatmap now uses the viewer's tz instead.
--   * autopilot_trigger.timezone (Scheduling): the tz the user had in mind
--     when authoring a "run at 9am" rule.
--
-- This column answers: when this user looks at a dashboard, which calendar
-- day should "today" be? Two members of the same workspace sitting in
-- different regions each see their own "today" rendered from the same
-- underlying UTC data.
--
-- NULL means "fall back to the browser-detected tz at render time". New
-- users land on NULL, so there is no required onboarding step; the
-- frontend resolves it transparently. A user who explicitly picks an
-- IANA name in Preferences pins the value here so it survives across
-- devices and sessions.
--
-- This column never affects how data is materialised — all rollups stay
-- in UTC. It is read-only from the rollup pipeline's perspective and is
-- only consumed at query time to drive `DATE(bucket_hour AT TIME ZONE @tz)`.
ALTER TABLE "user"
    ADD COLUMN timezone TEXT NULL;

COMMENT ON COLUMN "user".timezone IS
    'User-preferred IANA timezone for report rendering (Viewing tz). '
    'NULL means "use the browser-detected tz at render time". Affects '
    'dashboards, charts, and any "today" label shown to this user. Does '
    'not affect data materialisation — all rollups remain in UTC.';

```

## server/go/migrations/101_task_usage_hourly_schema.up.sql

```sql
-- Hourly rollup table for `task_usage`, materialised in **UTC**. Replaces
-- both per-runtime `task_usage_daily` (073, 082) and per-workspace
-- `task_usage_dashboard_daily` (084) as the single source of truth for
-- all token-usage reports.
--
-- WHY HOURLY + UTC:
--   The two existing rollups materialise on a `DATE` bucket — one in the
--   runtime's IANA tz, the other in UTC — which forces every report to
--   either accept the materialised tz or scan raw `task_usage`. Hourly
--   UTC buckets are tz-neutral: any viewer-side tz can be applied at
--   query time via `DATE(bucket_hour AT TIME ZONE @tz)` without losing
--   precision and without crossing midnight in the wrong direction.
--
-- WHY ONE TABLE INSTEAD OF TWO:
--   The two existing rollups share the same source rows and the same
--   invalidation surface (atq, task_usage, issue.project_id); maintaining
--   them separately is duplicative. The unified PK carries runtime_id,
--   agent_id, AND project_id, so:
--     * Runtime-detail views filter on runtime_id (covered by
--       idx_..._runtime_time).
--     * Workspace-dashboard views filter on workspace_id + group by
--       agent_id / project_id (covered by the three workspace indexes).
--     * The hour-of-day heatmap groups by EXTRACT(HOUR FROM ... AT TIME
--       ZONE <viewer's tz>) over the same rows — no separate aggregate.
--
-- WHY PROVIDER+MODEL IN THE PK:
--   Per-model breakdowns are a primary read dimension (cost per model,
--   trend per model). Keeping them in the PK keeps the rollup pre-grouped
--   along the same axis the UI uses.
--
-- WHY `UNIQUE NULLS NOT DISTINCT`:
--   `project_id` is nullable — tasks linked to issues without a project,
--   and the quick-create path's "no issue yet" state, both produce
--   no-project usage. PG15's `UNIQUE NULLS NOT DISTINCT` lets ON CONFLICT
--   upsert the no-project bucket the same way it handles a concrete
--   project. (Same pattern as 084.)
CREATE TABLE task_usage_hourly (
    bucket_hour         TIMESTAMPTZ NOT NULL,   -- UTC, truncated to hour boundary
    workspace_id        UUID        NOT NULL,
    runtime_id          UUID        NOT NULL,
    agent_id            UUID        NOT NULL,
    project_id          UUID,                   -- nullable; see above
    provider            TEXT        NOT NULL,
    model               TEXT        NOT NULL,
    input_tokens        BIGINT      NOT NULL DEFAULT 0,
    output_tokens       BIGINT      NOT NULL DEFAULT 0,
    cache_read_tokens   BIGINT      NOT NULL DEFAULT 0,
    cache_write_tokens  BIGINT      NOT NULL DEFAULT 0,
    task_count          BIGINT      NOT NULL DEFAULT 0,
    event_count         BIGINT      NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_task_usage_hourly_key
        UNIQUE NULLS NOT DISTINCT
        (bucket_hour, workspace_id, runtime_id, agent_id, project_id, provider, model)
);

-- Workspace-wide trend (no other filter): /{slug}/dashboard. The leading
-- workspace_id matches every dashboard query; bucket_hour DESC avoids an
-- extra sort when the report walks "last 7/30/90 days" backwards.
CREATE INDEX idx_task_usage_hourly_workspace_time
    ON task_usage_hourly (workspace_id, bucket_hour DESC);

-- Runtime detail page — trend + hour-of-day heatmap on a single runtime.
-- The heatmap groups by `EXTRACT(HOUR FROM bucket_hour AT TIME ZONE
-- <viewer's tz>)` over this range, so we want the rows pre-clustered
-- by runtime.
CREATE INDEX idx_task_usage_hourly_runtime_time
    ON task_usage_hourly (runtime_id, bucket_hour DESC);

-- Workspace dashboard "by agent" panel.
CREATE INDEX idx_task_usage_hourly_workspace_agent_time
    ON task_usage_hourly (workspace_id, agent_id, bucket_hour DESC);

-- Workspace dashboard "by project" panel. Partial because no-project
-- buckets aggregate into a separate bucket and the panel filters them
-- out; this keeps the index small.
CREATE INDEX idx_task_usage_hourly_workspace_project_time
    ON task_usage_hourly (workspace_id, project_id, bucket_hour DESC)
    WHERE project_id IS NOT NULL;

-- Single-row state table tracking the rollup worker's watermark. Same
-- shape as 073's `task_usage_rollup_state` and 084's
-- `task_usage_dashboard_rollup_state` — a SMALLINT(1) PK is the easiest
-- way to enforce "exactly one row" without a CHECK trigger.
CREATE TABLE task_usage_hourly_rollup_state (
    id                    SMALLINT    PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    watermark_at          TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01 00:00:00+00',
    last_run_started_at   TIMESTAMPTZ,
    last_run_finished_at  TIMESTAMPTZ,
    last_run_rows         BIGINT      NOT NULL DEFAULT 0,
    last_error            TEXT
);
INSERT INTO task_usage_hourly_rollup_state (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Dirty queue for invalidations the `updated_at` watermark cannot see:
--   * DELETE on `task_usage` (no row left for the watermark to catch).
--   * Cascade DELETE through `agent_task_queue` (task_usage rows gone).
--   * UPDATE of `issue.project_id` — moves the bucket to a new key,
--     OLD bucket needs to shrink, NEW bucket needs to appear.
--   * UPDATE of `agent_task_queue.runtime_id` / `agent_task_queue.issue_id`
--     — same re-attribution problem on different dimensions.
--
-- bucket_hour is computed in UTC at trigger time, so dirty keys match
-- the rollup table byte-for-byte and the window function can UNION the
-- queue into `dirty_keys` without translation.
--
-- TTL: rows in this queue MUST be pruned (see prune_task_usage_hourly_dirty
-- in the rollup-pipeline migration). Without TTL, dense workloads grow the queue
-- unboundedly — every retouched
-- bucket leaves a row behind. The window function deletes rows whose
-- enqueued_at < p_to as part of each tick, which keeps the steady state
-- bounded; the explicit prune is a belt-and-braces guarantee for rows
-- that somehow escape the window (e.g. crash mid-tick).
CREATE TABLE task_usage_hourly_dirty (
    bucket_hour   TIMESTAMPTZ NOT NULL,
    workspace_id  UUID        NOT NULL,
    runtime_id    UUID        NOT NULL,
    agent_id      UUID        NOT NULL,
    project_id    UUID,
    provider      TEXT        NOT NULL,
    model         TEXT        NOT NULL,
    enqueued_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_task_usage_hourly_dirty_key
        UNIQUE NULLS NOT DISTINCT
        (bucket_hour, workspace_id, runtime_id, agent_id, project_id, provider, model)
);

-- The window function drains rows with enqueued_at < p_to; the prune
-- helper (prune_task_usage_hourly_dirty) deletes rows
-- whose enqueued_at falls outside the retention horizon. Both scans
-- use this index.
CREATE INDEX idx_task_usage_hourly_dirty_enqueued_at
    ON task_usage_hourly_dirty (enqueued_at);

```

## server/go/migrations/102_task_usage_hourly_pipeline.up.sql

```sql
-- Rollup window + triggers + cron entry for `task_usage_hourly`. Same
-- shape as 077 (per-runtime daily) and 084 (dashboard daily), the
-- differences are:
--   * bucket grain is HOUR, not DATE.
--   * bucket boundary is always UTC — regardless of any runtime tz —
--     because viewer-side tz is applied at query time.
--   * a single PK covers runtime + agent + project + provider + model,
--     so both prior pipelines collapse into this one.
--
-- IDEMPOTENCY CONTRACT (same as 073/084):
--   For every dirty key, this function REPLACES the corresponding
--   hourly row with the SUM of *all* task_usage rows for that key. It
--   does NOT delta. Re-running an overlapping window yields the same
--   final state, which is what makes "cron + offline backfill" safe to
--   run concurrently.
--
-- The window function returns the number of (upserted + deleted-empty)
-- rows. Empty buckets that recomputed to zero (because their source
-- rows were deleted or re-attributed) get removed in the same
-- transaction — same `deleted_empty` CTE pattern as 084.

-- Helper: canonical UTC hour boundary. Centralised so triggers and the
-- recompute CTE compute the same expression byte-for-byte; a drift here
-- splits the bucket key between writers and the rollup table and the
-- bucket never converges.
--
-- The two `AT TIME ZONE 'UTC'` are not redundant: the first casts
-- timestamptz -> timestamp (UTC wall clock) so date_trunc is independent
-- of the session timezone; the second casts back to timestamptz. Do not
-- collapse to a bare date_trunc — that would inherit the session tz.
CREATE OR REPLACE FUNCTION task_usage_hour_bucket(ts TIMESTAMPTZ)
RETURNS TIMESTAMPTZ
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT (date_trunc('hour', ts AT TIME ZONE 'UTC')) AT TIME ZONE 'UTC';
$$;

-- Trigger 1: agent_task_queue BEFORE UPDATE OF runtime_id / issue_id OR DELETE.
--
-- Runtime reassignment moves usage between runtime buckets; issue
-- reassignment moves it between (project_id) buckets. Both need
-- OLD and NEW keys enqueued. DELETE only enqueues OLD.
--
-- The atq trigger fires while OLD.* is still resolvable. For DELETE
-- cascades coming from `issue` DELETE, the issue row is gone by the
-- time this trigger sees the atq row, so `LEFT JOIN issue` resolves
-- project_id = NULL. The companion issue-DELETE trigger below covers
-- that case while issue is still readable.
CREATE OR REPLACE FUNCTION enqueue_task_usage_hourly_dirty_for_atq()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.runtime_id IS DISTINCT FROM NEW.runtime_id
           OR OLD.issue_id IS DISTINCT FROM NEW.issue_id THEN
            -- OLD side. NULL runtime_id rows are not aggregated (no
            -- runtime → no bucket); skip those.
            IF OLD.runtime_id IS NOT NULL THEN
                INSERT INTO task_usage_hourly_dirty (
                    bucket_hour, workspace_id, runtime_id, agent_id,
                    project_id, provider, model
                )
                SELECT DISTINCT
                    task_usage_hour_bucket(tu.created_at),
                    a.workspace_id,
                    OLD.runtime_id,
                    OLD.agent_id,
                    i_old.project_id,
                    tu.provider,
                    tu.model
                  FROM task_usage tu
                  JOIN agent a ON a.id = OLD.agent_id
                  LEFT JOIN issue i_old ON i_old.id = OLD.issue_id
                 WHERE tu.task_id = OLD.id
                ON CONFLICT ON CONSTRAINT uq_task_usage_hourly_dirty_key DO UPDATE
                    SET enqueued_at = GREATEST(task_usage_hourly_dirty.enqueued_at, EXCLUDED.enqueued_at);
            END IF;

            IF NEW.runtime_id IS NOT NULL THEN
                INSERT INTO task_usage_hourly_dirty (
                    bucket_hour, workspace_id, runtime_id, agent_id,
                    project_id, provider, model
                )
                SELECT DISTINCT
                    task_usage_hour_bucket(tu.created_at),
                    a.workspace_id,
                    NEW.runtime_id,
                    NEW.agent_id,
                    i_new.project_id,
                    tu.provider,
                    tu.model
                  FROM task_usage tu
                  JOIN agent a ON a.id = NEW.agent_id
                  LEFT JOIN issue i_new ON i_new.id = NEW.issue_id
                 WHERE tu.task_id = NEW.id
                ON CONFLICT ON CONSTRAINT uq_task_usage_hourly_dirty_key DO UPDATE
                    SET enqueued_at = GREATEST(task_usage_hourly_dirty.enqueued_at, EXCLUDED.enqueued_at);
            END IF;
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        IF OLD.runtime_id IS NOT NULL THEN
            INSERT INTO task_usage_hourly_dirty (
                bucket_hour, workspace_id, runtime_id, agent_id,
                project_id, provider, model
            )
            SELECT DISTINCT
                task_usage_hour_bucket(tu.created_at),
                a.workspace_id,
                OLD.runtime_id,
                OLD.agent_id,
                i.project_id,
                tu.provider,
                tu.model
              FROM task_usage tu
              JOIN agent a ON a.id = OLD.agent_id
              LEFT JOIN issue i ON i.id = OLD.issue_id
             WHERE tu.task_id = OLD.id
            ON CONFLICT ON CONSTRAINT uq_task_usage_hourly_dirty_key DO UPDATE
                SET enqueued_at = GREATEST(task_usage_hourly_dirty.enqueued_at, EXCLUDED.enqueued_at);
        END IF;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$;

-- INVARIANT: agent_task_queue.agent_id is immutable once a row is inserted.
-- If a future feature makes agent_id mutable (e.g. reassign / rebind), it
-- MUST be added to this trigger's `OF` column list, otherwise dirty
-- buckets for the old agent_id will not be enqueued and historical
-- aggregates will silently rot.
CREATE TRIGGER trg_atq_dirty_hourly
BEFORE UPDATE OF runtime_id, issue_id OR DELETE ON agent_task_queue
FOR EACH ROW EXECUTE FUNCTION enqueue_task_usage_hourly_dirty_for_atq();

-- Trigger 2: issue BEFORE DELETE — see the analogous trigger in 084 for
-- the full motivation. By the time the atq cascade fires, the issue
-- row is gone, so we capture project_id here while it is still readable.
CREATE OR REPLACE FUNCTION enqueue_task_usage_hourly_dirty_for_issue_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO task_usage_hourly_dirty (
        bucket_hour, workspace_id, runtime_id, agent_id,
        project_id, provider, model
    )
    SELECT DISTINCT
        task_usage_hour_bucket(tu.created_at),
        OLD.workspace_id,
        atq.runtime_id,
        atq.agent_id,
        OLD.project_id,
        tu.provider,
        tu.model
      FROM agent_task_queue atq
      JOIN task_usage tu ON tu.task_id = atq.id
     WHERE atq.issue_id = OLD.id
       AND atq.runtime_id IS NOT NULL
    ON CONFLICT ON CONSTRAINT uq_task_usage_hourly_dirty_key DO UPDATE
        SET enqueued_at = GREATEST(task_usage_hourly_dirty.enqueued_at, EXCLUDED.enqueued_at);
    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_issue_delete_dirty_hourly
BEFORE DELETE ON issue
FOR EACH ROW EXECUTE FUNCTION enqueue_task_usage_hourly_dirty_for_issue_delete();

-- Trigger 3: issue BEFORE UPDATE OF project_id — re-attribute every
-- bucket touched by tasks under this issue. Same logic as 084's
-- analogous trigger.
CREATE OR REPLACE FUNCTION enqueue_task_usage_hourly_dirty_for_issue_project()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.project_id IS DISTINCT FROM NEW.project_id THEN
        -- OLD project buckets.
        INSERT INTO task_usage_hourly_dirty (
            bucket_hour, workspace_id, runtime_id, agent_id,
            project_id, provider, model
        )
        SELECT DISTINCT
            task_usage_hour_bucket(tu.created_at),
            NEW.workspace_id,
            atq.runtime_id,
            atq.agent_id,
            OLD.project_id,
            tu.provider,
            tu.model
          FROM agent_task_queue atq
          JOIN task_usage tu ON tu.task_id = atq.id
         WHERE atq.issue_id = NEW.id
           AND atq.runtime_id IS NOT NULL
        ON CONFLICT ON CONSTRAINT uq_task_usage_hourly_dirty_key DO UPDATE
            SET enqueued_at = GREATEST(task_usage_hourly_dirty.enqueued_at, EXCLUDED.enqueued_at);

        -- NEW project buckets.
        INSERT INTO task_usage_hourly_dirty (
            bucket_hour, workspace_id, runtime_id, agent_id,
            project_id, provider, model
        )
        SELECT DISTINCT
            task_usage_hour_bucket(tu.created_at),
            NEW.workspace_id,
            atq.runtime_id,
            atq.agent_id,
            NEW.project_id,
            tu.provider,
            tu.model
          FROM agent_task_queue atq
          JOIN task_usage tu ON tu.task_id = atq.id
         WHERE atq.issue_id = NEW.id
           AND atq.runtime_id IS NOT NULL
        ON CONFLICT ON CONSTRAINT uq_task_usage_hourly_dirty_key DO UPDATE
            SET enqueued_at = GREATEST(task_usage_hourly_dirty.enqueued_at, EXCLUDED.enqueued_at);
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_issue_project_dirty_hourly
BEFORE UPDATE OF project_id ON issue
FOR EACH ROW EXECUTE FUNCTION enqueue_task_usage_hourly_dirty_for_issue_project();

-- Trigger 4: task_usage BEFORE DELETE — rare in practice (no direct
-- callers today) but keeps the rollup convergent if one is added.
-- INSERT/UPDATE are covered by the watermark window.
CREATE OR REPLACE FUNCTION enqueue_task_usage_hourly_dirty_for_tu()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO task_usage_hourly_dirty (
        bucket_hour, workspace_id, runtime_id, agent_id,
        project_id, provider, model
    )
    SELECT
        task_usage_hour_bucket(OLD.created_at),
        a.workspace_id,
        atq.runtime_id,
        atq.agent_id,
        i.project_id,
        OLD.provider,
        OLD.model
      FROM agent_task_queue atq
      JOIN agent a ON a.id = atq.agent_id
      LEFT JOIN issue i ON i.id = atq.issue_id
     WHERE atq.id = OLD.task_id
       AND atq.runtime_id IS NOT NULL
    ON CONFLICT ON CONSTRAINT uq_task_usage_hourly_dirty_key DO UPDATE
        SET enqueued_at = GREATEST(task_usage_hourly_dirty.enqueued_at, EXCLUDED.enqueued_at);
    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_tu_dirty_hourly
BEFORE DELETE ON task_usage
FOR EACH ROW EXECUTE FUNCTION enqueue_task_usage_hourly_dirty_for_tu();

-- Window function. Mirrors 077/084's structure:
--   1. Discover dirty keys from the updated_at watermark + the queue.
--   2. Recompute each from raw via the atq + agent + issue join.
--   3. Upsert; delete buckets that recomputed to nothing.
--   4. Drain the queue rows whose enqueued_at < p_to.
--
-- The recompute LEFT JOINs `issue`, so tasks with no issue resolve to
-- project_id = NULL and merge cleanly with the corresponding dirty key
-- via `IS NOT DISTINCT FROM`.
CREATE OR REPLACE FUNCTION rollup_task_usage_hourly_window(
    p_from TIMESTAMPTZ,
    p_to   TIMESTAMPTZ
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT;
BEGIN
    IF p_from >= p_to THEN
        RETURN 0;
    END IF;

    WITH
    dirty_from_updates AS (
        SELECT DISTINCT
            task_usage_hour_bucket(tu.created_at) AS bucket_hour,
            a.workspace_id                        AS workspace_id,
            atq.runtime_id                        AS runtime_id,
            atq.agent_id                          AS agent_id,
            i.project_id                          AS project_id,
            tu.provider                           AS provider,
            tu.model                              AS model
          FROM task_usage tu
          JOIN agent_task_queue atq ON atq.id      = tu.task_id
          JOIN agent            a   ON a.id        = atq.agent_id
          LEFT JOIN issue       i   ON i.id        = atq.issue_id
         WHERE atq.runtime_id IS NOT NULL
           AND (
                (tu.updated_at >= p_from AND tu.updated_at < p_to)
                -- Legacy updated_at-NULL rows; partial index from 078.
                OR (tu.updated_at IS NULL
                    AND tu.created_at >= p_from
                    AND tu.created_at <  p_to)
           )
    ),
    dirty_from_queue AS (
        SELECT bucket_hour, workspace_id, runtime_id, agent_id,
               project_id, provider, model
          FROM task_usage_hourly_dirty
         WHERE enqueued_at < p_to
    ),
    dirty_keys AS (
        SELECT * FROM dirty_from_updates
        UNION
        SELECT * FROM dirty_from_queue
    ),
    recomputed AS (
        SELECT
            dk.bucket_hour,
            dk.workspace_id,
            dk.runtime_id,
            dk.agent_id,
            dk.project_id,
            dk.provider,
            dk.model,
            SUM(tu.input_tokens)::bigint       AS input_tokens,
            SUM(tu.output_tokens)::bigint      AS output_tokens,
            SUM(tu.cache_read_tokens)::bigint  AS cache_read_tokens,
            SUM(tu.cache_write_tokens)::bigint AS cache_write_tokens,
            COUNT(DISTINCT tu.task_id)::bigint AS task_count,
            COUNT(*)::bigint                   AS event_count
          FROM dirty_keys dk
          JOIN agent_task_queue atq ON atq.runtime_id  = dk.runtime_id
                                    AND atq.agent_id    = dk.agent_id
          JOIN agent            a   ON a.id            = atq.agent_id
                                    AND a.workspace_id = dk.workspace_id
          LEFT JOIN issue       i   ON i.id            = atq.issue_id
          JOIN task_usage       tu  ON tu.task_id      = atq.id
                                    AND tu.provider    = dk.provider
                                    AND tu.model       = dk.model
                                    AND task_usage_hour_bucket(tu.created_at) = dk.bucket_hour
         WHERE (i.project_id IS NOT DISTINCT FROM dk.project_id)
         GROUP BY 1, 2, 3, 4, 5, 6, 7
    ),
    upserted AS (
        INSERT INTO task_usage_hourly AS d (
            bucket_hour, workspace_id, runtime_id, agent_id,
            project_id, provider, model,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            task_count, event_count
        )
        SELECT
            bucket_hour, workspace_id, runtime_id, agent_id,
            project_id, provider, model,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            task_count, event_count
          FROM recomputed
        ON CONFLICT ON CONSTRAINT uq_task_usage_hourly_key DO UPDATE
            SET input_tokens       = EXCLUDED.input_tokens,
                output_tokens      = EXCLUDED.output_tokens,
                cache_read_tokens  = EXCLUDED.cache_read_tokens,
                cache_write_tokens = EXCLUDED.cache_write_tokens,
                task_count         = EXCLUDED.task_count,
                event_count        = EXCLUDED.event_count,
                updated_at         = now()
        RETURNING 1
    ),
    deleted_empty AS (
        DELETE FROM task_usage_hourly d
         USING dirty_keys dk
         WHERE d.bucket_hour  = dk.bucket_hour
           AND d.workspace_id = dk.workspace_id
           AND d.runtime_id   = dk.runtime_id
           AND d.agent_id     = dk.agent_id
           AND d.project_id IS NOT DISTINCT FROM dk.project_id
           AND d.provider     = dk.provider
           AND d.model        = dk.model
           AND NOT EXISTS (
               SELECT 1 FROM recomputed r
                WHERE r.bucket_hour  = dk.bucket_hour
                  AND r.workspace_id = dk.workspace_id
                  AND r.runtime_id   = dk.runtime_id
                  AND r.agent_id     = dk.agent_id
                  AND r.project_id IS NOT DISTINCT FROM dk.project_id
                  AND r.provider     = dk.provider
                  AND r.model        = dk.model
           )
        RETURNING 1
    )
    SELECT (SELECT COUNT(*) FROM upserted) + (SELECT COUNT(*) FROM deleted_empty)
      INTO v_rows;

    DELETE FROM task_usage_hourly_dirty WHERE enqueued_at < p_to;

    RETURN v_rows;
END;
$$;

-- Dirty-queue TTL. The window function above already deletes drained
-- rows on every tick (`DELETE FROM task_usage_hourly_dirty WHERE
-- enqueued_at < p_to`), which bounds the queue in steady state. This
-- explicit prune is the belt-and-braces guarantee for rows that escape
-- a tick — a crash mid-tick, or the worker paused during an incident /
-- migration freeze. Without it the dirty queue grows unbounded: the
-- hourly grain multiplies the retouched-bucket surface ~24x over the
-- legacy daily rollups, and every retouched bucket leaves a row behind.
--
-- 7-day retention is generous on purpose — the only way a row survives
-- a tick is operator action (worker paused), and a week is long enough
-- that an on-call rotation will notice. Longer, and the queue size
-- starts to dominate the cost of the very draining it enables. The cron
-- entry below folds the prune in, so operators need no second job.
CREATE OR REPLACE FUNCTION prune_task_usage_hourly_dirty(
    p_retention INTERVAL DEFAULT INTERVAL '7 days'
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT;
BEGIN
    DELETE FROM task_usage_hourly_dirty
     WHERE enqueued_at < now() - p_retention;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    RETURN v_rows;
END;
$$;

-- Cron entry. Uses its own advisory lock id 4246 so a tick serialises
-- only against other ticks of this same pipeline.
CREATE OR REPLACE FUNCTION rollup_task_usage_hourly()
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_lock_ok BOOLEAN;
    v_from    TIMESTAMPTZ;
    v_to      TIMESTAMPTZ;
    v_rows    BIGINT := 0;
BEGIN
    SELECT pg_try_advisory_lock(4246) INTO v_lock_ok;
    IF NOT v_lock_ok THEN
        RETURN 0;
    END IF;

    BEGIN
        UPDATE task_usage_hourly_rollup_state
           SET last_run_started_at = now(),
               last_error          = NULL
         WHERE id = 1
        RETURNING watermark_at INTO v_from;

        -- Cap each tick at a one-day window. In steady state v_from is
        -- recent, so LEAST picks `now() - 5 min` and nothing changes. But
        -- if the worker was paused (incident, migration freeze) the
        -- watermark can fall far behind; without the cap a single catch-up
        -- tick would recompute a multi-week window in one statement while
        -- holding lock 4246, blocking every other tick. Capped, catch-up
        -- advances in bounded one-day steps over successive ticks.
        v_to := LEAST(now() - INTERVAL '5 minutes', v_from + INTERVAL '1 day');

        IF v_from < v_to THEN
            v_rows := rollup_task_usage_hourly_window(v_from, v_to);

            UPDATE task_usage_hourly_rollup_state
               SET watermark_at         = v_to,
                   last_run_finished_at = now(),
                   last_run_rows        = v_rows
             WHERE id = 1;
        ELSE
            UPDATE task_usage_hourly_rollup_state
               SET last_run_finished_at = now(),
                   last_run_rows        = 0
             WHERE id = 1;
        END IF;

        PERFORM pg_advisory_unlock(4246);
    EXCEPTION WHEN OTHERS THEN
        UPDATE task_usage_hourly_rollup_state
           SET last_error           = SQLERRM,
               last_run_finished_at = now()
         WHERE id = 1;
        PERFORM pg_advisory_unlock(4246);
        RAISE;
    END;

    -- TTL prune. Runs AFTER the advisory lock is released: on a large
    -- stale backlog the prune can be slow, and holding lock 4246 through
    -- it would serialise every concurrent cron tick. It is a plain
    -- bounded DELETE — idempotent and safe to run unlocked.
    PERFORM prune_task_usage_hourly_dirty();
    RETURN v_rows;
END;
$$;

-- Health-check helper — same shape as 076 / 084 lag helpers.
CREATE OR REPLACE FUNCTION task_usage_hourly_rollup_lag_seconds()
RETURNS DOUBLE PRECISION
LANGUAGE sql
STABLE
AS $$
    SELECT EXTRACT(EPOCH FROM (now() - last_run_finished_at))
      FROM task_usage_hourly_rollup_state
     WHERE id = 1;
$$;

-- Cron registration is intentionally deferred to the operator playbook,
-- matching 076 / 084. Rollout sequence:
--   1) Apply the hourly-pipeline migrations (the task_usage_hourly schema
--      and this pipeline). The legacy daily rollups keep running untouched.
--   2) Run `go run ./cmd/backfill_task_usage_hourly` to seed history.
--   3) As superuser, schedule the cron job:
--        SELECT cron.schedule(
--          'rollup_task_usage_hourly',
--          '*/5 * * * *',
--          $$SELECT rollup_task_usage_hourly()$$
--        );
--   4) Once `task_usage_hourly` is verified against the legacy daily
--      rollups, apply the migration that drops the legacy pipelines.

```

## server/go/migrations/103_drop_legacy_daily_rollups.up.sql

```sql
-- Drop the two legacy daily rollup pipelines now that `task_usage_hourly`
-- is the only read path. Forward-only: there is no down migration that would put the
-- data back, since by the time this ships:
--
--   * The hourly rollup has been live and writing every bucket since
--     the hourly-pipeline migration.
--   * No handler reads from `task_usage_daily` or
--     `task_usage_dashboard_daily`. The runtime PATCH path that used
--     to delete/insert into `task_usage_daily` on tz change has been
--     replaced by a single UPDATE.
--   * The `cmd/backfill_task_usage_daily` and
--     `cmd/backfill_task_usage_dashboard_daily` commands have been
--     removed. The remaining `cmd/backfill_task_usage_hourly` is the
--     only seed path going forward.
--
-- The two pg_cron entries are unscheduled below before their functions
-- are dropped, so a still-registered job cannot tick into a
-- `function does not exist` error. The cron.unschedule calls are wrapped
-- so the migration still succeeds on instances without pg_cron at all
-- (same guard pattern as migration 076).

-- ---------------------------------------------------------------------------
-- Fail-closed guard: refuse to drop the legacy daily pipelines unless the
-- hourly rollup has actually been seeded across the existing `task_usage`
-- history. `migrate up` runs the migration set straight through (no
-- per-version stop), so a self-host operator who skips the documented
-- backfill step would otherwise silently land in a state where dashboards
-- show zeros (see SELF-HOST UPGRADE ORDER in
-- cmd/backfill_task_usage_hourly/main.go). Failing loud here is the
-- only thing that turns an undetected outage into a clear migration error.
--
-- The completion signal we trust is task_usage_hourly_rollup_state.watermark_at:
--
--   * cmd/backfill_task_usage_hourly stamps it to `now() - 5 minutes` only
--     after every monthly slice succeeded (server/go/cmd/backfill_task_usage_hourly/main.go).
--   * rollup_task_usage_hourly() (the pg_cron entry) advances it on every
--     tick (102_task_usage_hourly_pipeline.up.sql).
--   * The default after migration 101 is `1970-01-01`, so an unrun or
--     interrupted backfill is trivially detected.
--
-- A non-empty `task_usage_hourly` is NOT a safe proxy for "backfill done":
-- the triggers in 102 only enqueue dirty keys on agent_task_queue /
-- issue / task_usage DELETE — they do not write hourly rows themselves,
-- and they fire only on writes since 102 landed. A backfill that
-- crashed mid-run, or a manual `rollup_task_usage_hourly_window` call,
-- both leave the hourly table non-empty but with a stale watermark and
-- partial history; the legacy rollups would still be the only complete
-- read path.
--
-- A fresh database (no rows in task_usage) is exempt — there is no
-- history to backfill, and rollup_task_usage_hourly() (registered as a
-- pg_cron job by the operator) will populate task_usage_hourly from the
-- first event forward via its updated_at watermark window.
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    v_watermark TIMESTAMPTZ;
    v_max_event TIMESTAMPTZ;
    v_lag       INTERVAL := INTERVAL '1 hour';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM task_usage LIMIT 1) THEN
        RETURN;
    END IF;

    SELECT watermark_at INTO v_watermark
      FROM task_usage_hourly_rollup_state
     WHERE id = 1;

    IF v_watermark IS NULL THEN
        RAISE EXCEPTION
            'refusing to drop legacy daily rollups: task_usage_hourly_rollup_state row is missing — apply migrations 100-102 first, then run cmd/backfill_task_usage_hourly';
    END IF;

    SELECT MAX(COALESCE(updated_at, created_at)) INTO v_max_event FROM task_usage;

    -- A successful cmd/backfill_task_usage_hourly stamps watermark_at to
    -- `now() - 5 min`; once pg_cron is registered the worker keeps it
    -- within a similar window. If the watermark trails the latest event
    -- by more than v_lag, one of these went wrong:
    --   * the backfill was never run (watermark stuck at 1970-01-01),
    --   * the backfill was interrupted before stampWatermark ran,
    --   * someone hand-seeded task_usage_hourly without stamping,
    --   * pg_cron has been off long enough to drift past the cap.
    -- In every case, dropping the legacy rollups now would remove the
    -- only read path for buckets the hourly pipeline has not proven it
    -- owns yet.
    IF v_watermark < v_max_event - v_lag THEN
        RAISE EXCEPTION
            'refusing to drop legacy daily rollups: task_usage_hourly_rollup_state.watermark_at (%) trails task_usage latest event (%) by more than % — backfill is incomplete or pg_cron is not running. Run cmd/backfill_task_usage_hourly (and let pg_cron catch up) before re-running migrate (see SELF-HOST UPGRADE ORDER in cmd/backfill_task_usage_hourly/main.go).',
            v_watermark, v_max_event, v_lag;
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- Unschedule the legacy pg_cron jobs first (no-op when pg_cron is absent
-- or the job was never registered).
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
        PERFORM cron.unschedule('rollup_task_usage_daily')
          FROM cron.job WHERE jobname = 'rollup_task_usage_daily';
        PERFORM cron.unschedule('rollup_task_usage_dashboard_daily')
          FROM cron.job WHERE jobname = 'rollup_task_usage_dashboard_daily';
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- task_usage_dashboard_daily pipeline (migration 084).
-- ---------------------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_issue_project_dirty_dashboard ON issue;
DROP TRIGGER IF EXISTS trg_tu_dirty_dashboard           ON task_usage;
DROP TRIGGER IF EXISTS trg_issue_delete_dirty_dashboard ON issue;
DROP TRIGGER IF EXISTS trg_atq_dirty_dashboard          ON agent_task_queue;

DROP FUNCTION IF EXISTS task_usage_dashboard_rollup_lag_seconds();
DROP FUNCTION IF EXISTS rollup_task_usage_dashboard_daily();
DROP FUNCTION IF EXISTS rollup_task_usage_dashboard_daily_window(TIMESTAMPTZ, TIMESTAMPTZ);
DROP FUNCTION IF EXISTS enqueue_task_usage_dashboard_dirty_for_issue_project();
DROP FUNCTION IF EXISTS enqueue_task_usage_dashboard_dirty_for_issue_delete();
DROP FUNCTION IF EXISTS enqueue_task_usage_dashboard_dirty_for_tu();
DROP FUNCTION IF EXISTS enqueue_task_usage_dashboard_dirty_for_atq();

DROP TABLE IF EXISTS task_usage_dashboard_dirty;
DROP TABLE IF EXISTS task_usage_dashboard_rollup_state;
DROP TABLE IF EXISTS task_usage_dashboard_daily;

-- ---------------------------------------------------------------------------
-- task_usage_daily pipeline (migrations 073 / 077 / 082).
-- ---------------------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_tu_dirty_rollup  ON task_usage;
DROP TRIGGER IF EXISTS trg_atq_dirty_rollup ON agent_task_queue;

DROP FUNCTION IF EXISTS task_usage_rollup_lag_seconds();
DROP FUNCTION IF EXISTS rollup_task_usage_daily();
DROP FUNCTION IF EXISTS rollup_task_usage_daily_window(TIMESTAMPTZ, TIMESTAMPTZ);
DROP FUNCTION IF EXISTS enqueue_task_usage_daily_dirty_for_tu();
DROP FUNCTION IF EXISTS enqueue_task_usage_daily_dirty_for_atq();

DROP TABLE IF EXISTS task_usage_daily_dirty;
DROP TABLE IF EXISTS task_usage_rollup_state;
DROP TABLE IF EXISTS task_usage_daily;

```

## server/go/migrations/104_drop_runtime_timezone.up.sql

```sql
-- Drop agent_runtime.timezone (Operational tz). The timezone architecture
-- collapsed from 3 layers to 2: Scheduling (autopilot_trigger.timezone) and
-- Viewing (user.timezone). The runtime's physical tz had exactly one
-- consumer -- the hour-of-day heatmap -- which now renders in the viewer's
-- tz like every other report.
ALTER TABLE agent_runtime DROP COLUMN timezone;

```

## server/go/migrations/105_issue_metadata.up.sql

```sql
-- Per-issue custom metadata: a small JSONB KV map agents use to record
-- pipeline state (PR number, pipeline_status, waiting_on, …) that doesn't
-- fit cleanly into the structured issue fields.
--
-- Application-level validation (handler) enforces key regex, key count
-- cap, and primitive-only values. The DB CHECKs below are defense-in-depth
-- against migrations or direct SQL writes that bypass the API surface.
ALTER TABLE issue ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE issue ADD CONSTRAINT issue_metadata_is_object
    CHECK (jsonb_typeof(metadata) = 'object');

ALTER TABLE issue ADD CONSTRAINT issue_metadata_size_limit
    CHECK (pg_column_size(metadata) <= 8192);

-- GIN with jsonb_path_ops: smaller index, faster `@>` containment.
-- We only need containment queries (no `?` existence), so the path-ops
-- variant is the right trade.
CREATE INDEX idx_issue_metadata_gin ON issue USING GIN (metadata jsonb_path_ops);

```

## server/go/migrations/106_member_user_workspace_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_member_user_workspace ON member(user_id, workspace_id);

```

## server/go/migrations/107_comment_system_author.up.sql

```sql
-- Allow platform-generated rows in the comment table. Used by the
-- child-done parent-notification path (MUL-2538) so the platform can post a
-- top-level comment on the parent issue without attributing it to a member
-- or agent. system rows use a zero UUID for author_id (the column is still
-- NOT NULL).
ALTER TABLE comment DROP CONSTRAINT IF EXISTS comment_author_type_check;
ALTER TABLE comment ADD CONSTRAINT comment_author_type_check
    CHECK (author_type IN ('member', 'agent', 'system'));

```

## server/go/migrations/108_task_token.up.sql

```sql
-- task_token replaces the historical practice of injecting the daemon
-- owner's WORKPAL_TOKEN (a workspace owner/admin PAT) into the agent
-- process. That practice gave the agent full owner privileges via
-- whatever credential the daemon happened to be using, which made
-- agent-resource secrets reachable from the agent (MUL-2600).
--
-- The daemon now mints a short-lived task-scoped token at task-claim
-- time and injects THAT into the agent. The server treats `mat_`
-- tokens as authoritative for actor identity (agent + task), so a
-- request from the agent process is recognised as actor=agent
-- regardless of whether the agent strips or forges X-Agent-ID /
-- X-Task-ID headers. Owner-only endpoints (`/api/agents/{id}/env`,
-- env-management CLI) consequently 403 on agent traffic.
CREATE TABLE task_token (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash TEXT NOT NULL,
    -- Bound triple: the only identity the agent can ever claim from
    -- this token. user_id is the daemon owner (kept so member-shaped
    -- read access still resolves correctly when the agent does
    -- legitimate reads), agent_id and task_id are server-derived.
    task_id UUID NOT NULL REFERENCES agent_task_queue(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_task_token_hash ON task_token(token_hash);
CREATE INDEX idx_task_token_task ON task_token(task_id);

```

## server/go/migrations/109_agent_task_waiting_local_directory.up.sql

```sql
-- Adds the `waiting_local_directory` task status used by the daemon when a
-- task targets a project_resource of type `local_directory` whose path is
-- already held by another in-flight task. The daemon claims the row
-- (dispatched), discovers the path is busy, transitions to
-- waiting_local_directory, and only flips to running once it has the path
-- lock. This is the daemon → server protocol surface for the UI to render
-- "等待本地目录释放" instead of letting the row sit silently in dispatched.
--
-- wait_reason carries a short human-readable hint (e.g. the path being
-- waited on) that the UI can display alongside the status. It is set when
-- the row enters waiting_local_directory and cleared when it leaves.

ALTER TABLE agent_task_queue DROP CONSTRAINT IF EXISTS agent_task_queue_status_check;
ALTER TABLE agent_task_queue ADD CONSTRAINT agent_task_queue_status_check
    CHECK (status IN ('queued', 'dispatched', 'running', 'waiting_local_directory', 'completed', 'failed', 'cancelled'));

ALTER TABLE agent_task_queue ADD COLUMN IF NOT EXISTS wait_reason TEXT;

```

## server/go/migrations/109_drop_agent_skills_local.up.sql

```sql
-- Clean up the unreleased per-agent local skill toggle. Fresh/prod databases
-- that never applied 108_agent_skills_local are unchanged, while dev/staging
-- databases that tested it converge back to the reverted schema.
ALTER TABLE agent DROP COLUMN IF EXISTS skills_local;

```

## server/go/migrations/109_issue_pull_request_close_intent.up.sql

```sql
-- Persist whether a PR ↔ issue link was created with explicit closing intent
-- (a "Closes/Fixes/Resolves PREFIX-N" keyword in the PR title or body). The
-- webhook auto-advance gate consults this column so a link-only sibling PR
-- closing later still resolves an issue that an earlier closing-keyword PR
-- had blocked from advancing.
ALTER TABLE issue_pull_request
    ADD COLUMN close_intent BOOLEAN NOT NULL DEFAULT FALSE;

```

## server/go/migrations/109_lark_integration.up.sql

```sql
-- Lark (飞书) Bot integration: per-agent PersonalAgent installations,
-- user/chat bindings, inbound dedup + drop audit, outbound card mapping,
-- and short-lived member binding tokens.
--
-- Scope notes (mirror description §4.8 boundaries):
--   * `chat_session` is reused as-is — Lark routes through a separate
--     `lark_chat_session_binding` rather than adding a `metadata` JSONB
--     column to chat_session.
--   * Outbound card-message mapping is *task/message* scoped, not session
--     scoped, so multiple runs on the same chat_session don't stomp each
--     other's cards.
--   * `app_secret` is stored encrypted; the application layer encrypts
--     before writing and decrypts on read (no DB-side decryption helper).
--   * `lark_inbound_audit` is the only writable surface for events that
--     fail identity check or group-mention filter — it stores routing /
--     identity / drop_reason / timestamp ONLY, never message body.

-- =====================
-- lark_installation
-- =====================
-- One row per (workspace, agent) — each Workpal Agent owns at most one
-- Lark PersonalAgent Bot. `app_secret_encrypted` is the ciphertext
-- produced by the application-layer secretbox helper; never plaintext.
CREATE TABLE lark_installation (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id          UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    agent_id              UUID NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    app_id                TEXT NOT NULL,
    -- Ciphertext of the Lark app secret. Application-layer secretbox.
    -- DB never sees plaintext; a dump leaks ciphertext only.
    app_secret_encrypted  BYTEA NOT NULL,
    tenant_key            TEXT,
    bot_open_id           TEXT NOT NULL,
    installer_user_id     UUID NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    status                TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'revoked')),
    -- WS ownership lease: only the server instance holding a non-expired
    -- lease may keep the WebSocket open for this installation. Used to
    -- prevent duplicate consumption when multiple replicas are deployed.
    ws_lease_token        TEXT,
    ws_lease_expires_at   TIMESTAMPTZ,
    installed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, agent_id),
    UNIQUE (app_id),
    -- Composite key target for the composite FK on lark_user_binding
    -- (installation_id, workspace_id) — guarantees a binding's workspace
    -- always matches the workspace of its installation.
    UNIQUE (id, workspace_id)
);

CREATE INDEX idx_lark_installation_workspace ON lark_installation(workspace_id);
CREATE INDEX idx_lark_installation_agent ON lark_installation(agent_id);
-- Used by the lease scanner to find leases due for renewal / takeover.
CREATE INDEX idx_lark_installation_lease ON lark_installation(ws_lease_expires_at)
    WHERE status = 'active';

-- =====================
-- lark_user_binding
-- =====================
-- Maps a Lark `open_id` to a Workpal user, per-installation. open_id is
-- per-app, so the same Lark user has different open_ids across different
-- installations — the binding is therefore keyed on (installation, open_id),
-- not open_id alone. `union_id` is captured opportunistically for future
-- cross-installation identity merging (Phase 2) but is not authoritative
-- in MVP.
--
-- Two structural invariants protect §4.3's "unbound or non-workspace
-- members never leak content into chat_session" rule from drifting if
-- the application layer regresses:
--
--   1. The composite FK on (installation_id, workspace_id) targets
--      lark_installation(id, workspace_id), so a binding row cannot
--      claim a workspace different from its installation's workspace.
--
--   2. The composite FK on (workspace_id, workpal_user_id) targets
--      member(workspace_id, user_id) with ON DELETE CASCADE, so when a
--      Workpal user is removed from the workspace the stale Lark
--      binding is removed in the same transaction. There is no path
--      where lark_user_binding can outlive workspace membership.
CREATE TABLE lark_user_binding (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     UUID NOT NULL,
    workpal_user_id  UUID NOT NULL,
    installation_id  UUID NOT NULL,
    lark_open_id     TEXT NOT NULL,
    union_id         TEXT,
    bound_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (installation_id, lark_open_id),
    -- Installation ↔ workspace integrity. Composite FK guarantees the
    -- binding's workspace_id matches the installation's workspace_id.
    CONSTRAINT lark_user_binding_installation_fk
        FOREIGN KEY (installation_id, workspace_id)
        REFERENCES lark_installation(id, workspace_id)
        ON DELETE CASCADE,
    -- Workspace membership integrity. Composite FK guarantees the
    -- (workspace_id, workpal_user_id) pair still exists in member; when
    -- the user is removed from the workspace, the binding cascades away.
    CONSTRAINT lark_user_binding_member_fk
        FOREIGN KEY (workspace_id, workpal_user_id)
        REFERENCES member(workspace_id, user_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_lark_user_binding_user
    ON lark_user_binding(workpal_user_id, workspace_id);
CREATE INDEX idx_lark_user_binding_workspace_open
    ON lark_user_binding(workspace_id, lark_open_id);

-- =====================
-- lark_chat_session_binding
-- =====================
-- One Lark chat (`chat_id`) ↔ one Workpal `chat_session`. The Lark side
-- doesn't distinguish p2p vs group at the routing layer, but we keep
-- `lark_chat_type` for product behavior (group sessions only ingest
-- @-Bot / reply-Bot messages; p2p ingests everything).
CREATE TABLE lark_chat_session_binding (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_session_id   UUID NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
    installation_id   UUID NOT NULL REFERENCES lark_installation(id) ON DELETE CASCADE,
    lark_chat_id      TEXT NOT NULL,
    lark_chat_type    TEXT NOT NULL
        CHECK (lark_chat_type IN ('p2p', 'group')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (installation_id, lark_chat_id),
    UNIQUE (chat_session_id)
);

CREATE INDEX idx_lark_chat_session_binding_session
    ON lark_chat_session_binding(chat_session_id);

-- =====================
-- lark_inbound_message_dedup
-- =====================
-- Idempotency for Lark inbound events. WebSocket reconnects can replay
-- recently-delivered events; we keep 24h of message_ids to short-circuit
-- replays before any business logic runs. A periodic vacuum job (separate
-- migration / cron) trims rows older than ~24h.
--
-- Two-phase semantics with owner fencing (see ClaimLarkInboundDedup /
-- MarkLarkInboundDedupProcessed / ReleaseLarkInboundDedup in
-- queries/lark.sql):
--
--   processed_at IS NULL  → in-flight claim. The dispatcher holds a
--     row but has not yet reached a durable outcome (audit-drop row
--     persisted, OR chat_message + session touched). If the worker
--     crashes here the row is re-claimable after the staleness TTL,
--     so a replay does not get permanently swallowed.
--
--   processed_at IS NOT NULL → terminal. The message_id has reached a
--     durable outcome; future replays are dropped as duplicates
--     regardless of staleness.
--
--   claim_token → owner fence. Each Claim mints a fresh UUID; Mark and
--     Release only succeed when the supplied token matches the row's
--     current value. This closes two windows that staleness-TTL alone
--     leaves open:
--
--       (1) Stale-reclaim race. Worker A claims with token T_A; it
--           runs slowly past the 60s TTL but is still alive. Worker B
--           re-takes the claim with a new token T_B. A reaches the
--           chat_message+Mark transaction; the token-fenced Mark
--           returns zero rows because the live token is now T_B, so
--           A's tx ROLLS BACK and no second chat_message lands. B's
--           run is the sole writer.
--
--       (2) Mark window. The dispatcher Marks the dedup row INSIDE
--           the same tx as the chat_message + session touch, so the
--           durable write and the Mark commit (or roll back)
--           atomically. There is no "committed chat_message but not
--           yet Marked" window for a crash or retry to exploit.
--
-- Together: "first-attempt EnsureChatSession or AppendUserMessage
-- infra error → second attempt gets duplicate-dropped" is prevented by
-- Release (claim is dropped on rollback); "stale reclaim while
-- original worker is alive" and "process crash between durable commit
-- and Mark" are prevented by owner fencing + same-tx Mark.
CREATE TABLE lark_inbound_message_dedup (
    message_id    TEXT PRIMARY KEY,
    received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at  TIMESTAMPTZ,
    claim_token   UUID NOT NULL DEFAULT gen_random_uuid()
);

CREATE INDEX idx_lark_inbound_dedup_received
    ON lark_inbound_message_dedup(received_at);

-- =====================
-- lark_inbound_audit
-- =====================
-- Non-content audit log for events that DID arrive but were intentionally
-- dropped (group message without @, unbound user, non-workspace member,
-- duplicate, etc.). NEVER stores message body — only routing + identity
-- + drop_reason + timestamp. Used for ops debugging, abuse detection, and
-- proving the "non-bound users cannot leak content into chat_session"
-- invariant from §4.7 of the design.
CREATE TABLE lark_inbound_audit (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id   UUID REFERENCES lark_installation(id) ON DELETE SET NULL,
    lark_chat_id      TEXT,
    event_type        TEXT NOT NULL,
    lark_event_id     TEXT,
    lark_message_id   TEXT,
    -- Open-ended TEXT (not an enum) so new drop reasons can be added in
    -- application code without a schema migration. Convention: snake_case.
    -- Known values today: unbound_user, non_workspace_member,
    -- not_addressed_in_group, duplicate, revoked_installation, invalid_event.
    drop_reason       TEXT NOT NULL,
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_lark_inbound_audit_installation
    ON lark_inbound_audit(installation_id, received_at DESC);
CREATE INDEX idx_lark_inbound_audit_reason
    ON lark_inbound_audit(drop_reason, received_at DESC);

-- =====================
-- lark_outbound_card_message
-- =====================
-- Maps a Workpal task (or session bootstrap "thinking…" card) to the
-- Lark interactive card message we're patching. Per-task, not per-session
-- — a chat_session can host many runs and a session-level field would
-- create card aliasing bugs. `task_id` may be NULL for the initial
-- bootstrap card before a task is created; the partial UNIQUE index
-- guarantees task↔card is 1:1 once a task exists.
CREATE TABLE lark_outbound_card_message (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_session_id        UUID NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
    task_id                UUID REFERENCES agent_task_queue(id) ON DELETE SET NULL,
    lark_chat_id           TEXT NOT NULL,
    lark_card_message_id   TEXT NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'streaming', 'final', 'error')),
    last_patched_at        TIMESTAMPTZ,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_lark_outbound_card_task
    ON lark_outbound_card_message(task_id)
    WHERE task_id IS NOT NULL;
CREATE INDEX idx_lark_outbound_card_session
    ON lark_outbound_card_message(chat_session_id, created_at DESC);

-- =====================
-- lark_binding_token
-- =====================
-- Short-lived (≤ 15 min), single-use token for the "you're not bound yet,
-- click here" flow that links a Lark `open_id` to a Workpal user. The
-- hash (not the raw token) is stored so a DB leak doesn't grant binding
-- capability. Replay is blocked by `consumed_at IS NOT NULL`.
CREATE TABLE lark_binding_token (
    token_hash       TEXT PRIMARY KEY,
    workspace_id     UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    installation_id  UUID NOT NULL REFERENCES lark_installation(id) ON DELETE CASCADE,
    lark_open_id     TEXT NOT NULL,
    expires_at       TIMESTAMPTZ NOT NULL,
    consumed_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Belt-and-braces with the application-layer cap (lark.BindingTokenTTL
    -- = 15 minutes). The CHECK refuses any row whose lifetime exceeds the
    -- product cap, so a misconfigured caller or a hand-inserted SQL row
    -- cannot quietly mint a longer-lived binding token. Keep this value
    -- in sync with lark.BindingTokenTTL.
    CONSTRAINT lark_binding_token_ttl_cap
        CHECK (expires_at <= created_at + INTERVAL '15 minutes')
);

CREATE INDEX idx_lark_binding_token_installation
    ON lark_binding_token(installation_id, expires_at);

```

## server/go/migrations/110_autopilot_trigger_event_filters.up.sql

```sql
-- Add event_filters to autopilot_trigger so webhook triggers can declare
-- which events/actions they care about. NULL means "accept all" (backward
-- compatible). JSONB shape: [{"event": "workflow_run", "actions": ["completed"]}, …]
ALTER TABLE autopilot_trigger
    ADD COLUMN event_filters JSONB;

```

## server/go/migrations/111_issue_origin_lark_chat.up.sql

```sql
-- Extend issue.origin_type to allow the Lark `/issue` command path to stamp
-- issues with origin_type='lark_chat' + origin_id=<chat_session.id>. Without
-- this entry in the CHECK list, every /issue dispatch on Lark fails with
-- SQLSTATE 23514 and the connector exits with infra error — see Bohan's
-- live-env repro in MUL-2671 review where one /issue in a row tripped the
-- check three times, each crash dragging the WS connector down + Lark
-- retrying the same event into the next crash.
ALTER TABLE issue DROP CONSTRAINT IF EXISTS issue_origin_type_check;
ALTER TABLE issue ADD CONSTRAINT issue_origin_type_check
    CHECK (origin_type IN ('autopilot', 'quick_create', 'lark_chat'));

```

## server/go/migrations/111_workspace_avatar.up.sql

```sql
ALTER TABLE workspace ADD COLUMN avatar_url TEXT;

```

## server/go/migrations/112_issue_dates_to_date.up.sql

```sql
-- Issue start_date / due_date are calendar days: a user picks a day (the
-- pickers have no time-of-day input), so "Mar 1" must mean Mar 1 for everyone
-- regardless of timezone. Storing them as TIMESTAMPTZ folded the writer's
-- local midnight into a UTC instant, shifting the displayed day by the local
-- offset in non-UTC timezones (GH #3618 / MUL-2925). DATE carries no time or
-- timezone, so the picked day is preserved as-is.
--
-- Existing rows are truncated at the UTC day boundary, matching what the Gantt
-- already showed for them. `AT TIME ZONE 'UTC'` pins the conversion to UTC
-- explicitly so it does not depend on the migration session's TimeZone setting
-- (a bare `::date` cast would be session-timezone dependent). The original
-- local-day intent of legacy rows is unrecoverable from a bare instant, so this
-- is the best-effort conversion.
ALTER TABLE issue
    ALTER COLUMN start_date TYPE DATE USING (start_date AT TIME ZONE 'UTC')::date,
    ALTER COLUMN due_date TYPE DATE USING (due_date AT TIME ZONE 'UTC')::date;

```

## server/go/migrations/112_lark_installation_bot_union_id.up.sql

```sql
-- Add bot_union_id to lark_installation so the WS inbound decoder can
-- match group-chat @-mentions against the bot's stable cross-app identity
-- (union_id) instead of the per-app open_id.
--
-- Why this column exists: Bohan's live-env triage on MUL-2671 showed that
-- in a group chat where two Workpal-installed bots are bound, Lark's
-- `mentions[].id.open_id` field on `im.message.receive_v1` is structurally
-- inverse to /open-apis/bot/v3/info's `bot.open_id`. The bot whose WS
-- receives the event sees its OWN payload-form open_id when the OTHER
-- bot was @-mentioned, and a different open_id when itself was the
-- target. The only payload field consistent across both perspectives is
-- `union_id` — see the diag-log capture in MUL-2671 review.
--
-- Nullable on purpose: installations created before this migration won't
-- have a union_id until the registration service backfills them (next
-- run of GetBotInfo or a one-shot operator backfill). The decoder
-- short-circuits to its previous open_id-only match when bot_union_id IS
-- NULL, so pre-migration rows continue to work as they did before. New
-- installs populate it during finishSuccess.
ALTER TABLE lark_installation
    ADD COLUMN bot_union_id TEXT;

```

## server/go/migrations/113_lark_inbound_dedup_per_installation.up.sql

```sql
-- Re-scope lark_inbound_message_dedup to (installation_id, message_id).
--
-- The original schema keyed dedup on `message_id` alone. In a Lark group
-- chat where the same workspace has multiple Workpal bots installed, each
-- bot's WS receives the SAME `message_id` from Lark — and both supervisors
-- legitimately need to claim, evaluate AddressedToBot from their own
-- bot's perspective, and either ingest (if @-ed) or drop as
-- not_addressed_in_group (if the OTHER bot was @-ed). With a single
-- shared dedup row, whichever WS claims first locks the row, and the
-- bot that was actually @-ed gets dropped as `duplicate` before it can
-- evaluate the mention. See MUL-2671 multi-bot routing triage.
--
-- The dedup table is short-lived (24h TTL via PurgeLarkInboundDedup);
-- existing rows can be dropped on the way through — there's no
-- meaningful product state in them, only transient idempotency cache.
DROP TABLE IF EXISTS lark_inbound_message_dedup;

CREATE TABLE lark_inbound_message_dedup (
    installation_id  UUID NOT NULL REFERENCES lark_installation(id) ON DELETE CASCADE,
    message_id       TEXT NOT NULL,
    received_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at     TIMESTAMPTZ,
    claim_token      UUID NOT NULL DEFAULT gen_random_uuid(),
    PRIMARY KEY (installation_id, message_id)
);

CREATE INDEX idx_lark_inbound_dedup_received
    ON lark_inbound_message_dedup(received_at);

```

## server/go/migrations/113_sys_cron_executions.up.sql

```sql
-- Schema for the DB-backed execution-record scheduler (MUL-2957). One row
-- represents a single planned execution of a registered system job for a
-- single scope at a single canonical UTC `plan_time` bucket — the row is
-- both the distributed lease and the audit log entry.
--
-- Design source: docs/db-backed-execution-scheduler-rfc.md.
--
-- Key invariants:
--
--   * The unique key (job_name, scope_kind, scope_id, plan_time) is the
--     only thing standing between two app instances and a double-run.
--     `scope_kind` / `scope_id` default to 'global' so global jobs land
--     on the same uniqueness slot without using NULL semantics.
--
--   * Status uses `TEXT + CHECK` instead of a real enum so adding a state
--     later is a CHECK swap, not an enum migration. There is no `STALE`
--     state — stale is `status='RUNNING' AND stale_after < now()`, which
--     keeps lease theft a single UPDATE.
--
--   * Every mutation that targets a live lease (heartbeat, terminal
--     write) MUST match `id = $id AND lease_token = $token AND
--     status = 'RUNNING'`. A runner that lost its lease (stolen by a
--     stale-steal, or already finalised by a sibling) sees
--     RowsAffected = 0 and stops, so it cannot rewrite a newer attempt's
--     state to SUCCESS / FAILED.
--
--   * `attempt` and `max_attempts` are bounded by CHECK so a buggy
--     handler cannot "escape" the retry envelope by writing
--     attempt > max_attempts.
--
-- This migration creates the table and the few indexes the steady-state
-- scheduler queries need (claim-by-key, find-stale-RUNNING, recent
-- failures, retention prune). It does NOT register any jobs — those are
-- declared in Go and inserted on demand by the scheduler.

CREATE TABLE sys_cron_executions (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name       TEXT        NOT NULL,
    scope_kind     TEXT        NOT NULL DEFAULT 'global',
    scope_id       TEXT        NOT NULL DEFAULT 'global',
    plan_time      TIMESTAMPTZ NOT NULL,

    -- Lifecycle. status ∈ {RUNNING, SUCCESS, FAILED}; stale is computed
    -- from RUNNING + stale_after, never materialised as its own state.
    status         TEXT        NOT NULL,
    attempt        INTEGER     NOT NULL DEFAULT 1,
    max_attempts   INTEGER     NOT NULL DEFAULT 3,
    next_retry_at  TIMESTAMPTZ,

    -- Lease ownership. lease_token is rotated on every claim/steal, so a
    -- runner whose lease was stolen cannot write terminal status — its
    -- UPDATE matches zero rows.
    runner_id      TEXT,
    lease_token    UUID        NOT NULL DEFAULT gen_random_uuid(),
    heartbeat_at   TIMESTAMPTZ,
    stale_after    TIMESTAMPTZ,

    -- Audit fields. Small structured `result` only — bulky output goes to
    -- structured logs, not into this table.
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    duration_ms    INTEGER,
    rows_affected  BIGINT,
    result         JSONB       NOT NULL DEFAULT '{}'::jsonb,

    error_code     TEXT,
    error_msg      TEXT,

    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_sys_cron_status
        CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    CONSTRAINT chk_sys_cron_attempt
        CHECK (attempt >= 1 AND max_attempts >= attempt),
    CONSTRAINT chk_sys_cron_duration
        CHECK (duration_ms IS NULL OR duration_ms >= 0),
    CONSTRAINT uq_sys_cron_execution
        UNIQUE (job_name, scope_kind, scope_id, plan_time)
);

-- Latest-plan lookup per (job, scope). The scheduler reads this to
-- decide whether the latest plan is already done or in flight; the
-- prune job and `latest-success` lag computation use the same key.
CREATE INDEX idx_sys_cron_exec_job_plan
    ON sys_cron_executions (job_name, scope_kind, scope_id, plan_time DESC);

-- Find leases that have gone stale without scanning the whole RUNNING
-- set. Partial because non-RUNNING rows never need to be considered.
CREATE INDEX idx_sys_cron_exec_running_stale
    ON sys_cron_executions (stale_after)
    WHERE status = 'RUNNING';

-- "Recent FAILED for this job" — used by alerting and by the retry
-- decision, which needs the most recent FAILED row to compare against
-- max_attempts and next_retry_at.
CREATE INDEX idx_sys_cron_exec_failed_recent
    ON sys_cron_executions (job_name, plan_time DESC)
    WHERE status = 'FAILED';

-- Retention prune scans by terminal `finished_at`; index is partial
-- because RUNNING rows are kept by the stale policy, not the retention
-- policy.
CREATE INDEX idx_sys_cron_exec_finished
    ON sys_cron_executions (finished_at)
    WHERE status IN ('SUCCESS', 'FAILED');

```

## server/go/migrations/114_agent_task_queue_running_started_at_index.up.sql

```sql
-- Covers sampler reads over running tasks:
--   * task_stuck: status = 'running' AND started_at < now() - interval '30 minutes'
--   * task_running: the running half of the in-flight task count
--
-- agent_task_queue is hot, so this must stay in its own single-statement
-- migration and must use CONCURRENTLY. The migration runner executes files
-- outside an explicit transaction; keeping CONCURRENTLY isolated avoids
-- Postgres' implicit transaction block for multi-statement query strings.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_running_started_at
    ON agent_task_queue (started_at)
    WHERE status = 'running';

```

## server/go/migrations/115_agent_runtime_last_seen_at_index.up.sql

```sql
-- Covers sampler reads over runtime heartbeats:
--   * runtime_online: last_seen_at > now() - online window
--   * runtime_heartbeat_age: last_seen_at > now() - 15 minutes ORDER BY last_seen_at DESC
--
-- agent_runtime heartbeat writes are frequent, so this must stay in its own
-- single-statement migration and must use CONCURRENTLY.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_runtime_last_seen_at
    ON agent_runtime (last_seen_at);

```

## server/go/migrations/116_lark_installation_region.up.sql

```sql
-- Add a per-installation `region` so one Workpal deployment can serve
-- BOTH mainland Feishu (open.feishu.cn / accounts.feishu.cn) and Lark
-- international (open.larksuite.com / accounts.larksuite.com) at the same
-- time. Before this column the open-platform host was a single
-- deployment-wide value (the WORKPAL_LARK_HTTP_BASE_URL /
-- WORKPAL_LARK_CALLBACK_BASE_URL env knobs, defaulting to open.feishu.cn),
-- so a given deployment could talk to only one cloud at a time.
--
-- The device-flow installer already auto-detects the tenant: Lark emits
-- user_info.tenant_brand="lark" mid-poll and RegistrationService swaps the
-- accounts host to accounts.larksuite.com. finishSuccess now persists that
-- detected region here, and every outbound REST + WebSocket call resolves
-- its open-platform host from this column via InstallationCredentials.Region.
--
-- NOT NULL DEFAULT 'feishu' is the safe backfill: every installation that
-- exists today was created against mainland Feishu (the only host the old
-- code reached without an env override), so 'feishu' is correct for all
-- pre-migration rows. The CHECK mirrors the lark.Region enum in
-- server/go/internal/integrations/lark/types.go — keep the two in lockstep.
ALTER TABLE lark_installation
    ADD COLUMN region TEXT NOT NULL DEFAULT 'feishu'
        CHECK (region IN ('feishu', 'lark'));

```

## server/go/migrations/117_agent_task_queue_initiator_user_id.up.sql

```sql
-- Capture the real task initiator (the requester behind this run) on chat
-- tasks at enqueue time. chat_session.creator_id is NOT a reliable initiator:
-- Lark group sessions deliberately set the creator to the installer (a stable
-- workspace identity that survives group-member churn), not the person who sent
-- the triggering message. Storing the actual sender here lets the daemon brief
-- attribute the run to the right person instead of the installer/owner.
--
-- NULL for non-chat tasks and for chat tasks queued before this column existed;
-- the brief simply omits the `## Task Initiator` section in that case. See
-- MUL-2645.
--
-- Plain UUID, no FK to "user": adding a foreign key here also takes a lock on
-- the (hot) "user" table at migration time, which made this ALTER time out on a
-- busy production deploy. The column only feeds a best-effort name/email lookup
-- at claim time (a stale id just yields no initiator section), so referential
-- integrity is not load-bearing. Migration 118 drops the FK on environments
-- that already applied the original constraint-bearing version of this file.
ALTER TABLE agent_task_queue
    ADD COLUMN initiator_user_id UUID;

```

## server/go/migrations/118_agent_task_queue_initiator_user_id_drop_fk.up.sql

```sql
-- Converge environments that already applied the original constraint-bearing
-- version of migration 117 (which added `initiator_user_id` with a foreign key
-- to "user"). Those environments skip the now-edited 117 by version, so the FK
-- still exists there; this drops it so every environment ends up with a plain
-- `initiator_user_id` column and no FK.
--
-- The FK to the hot "user" table is what made 117 time out on a busy deploy, and
-- the column only feeds a best-effort name/email lookup at claim time, so the
-- constraint is not needed. DROP CONSTRAINT only touches catalog metadata (a
-- brief lock on agent_task_queue, no table scan, no lock on "user"). IF EXISTS
-- makes this a no-op where 117 already ran in its FK-free form. See MUL-2645.
ALTER TABLE agent_task_queue
    DROP CONSTRAINT IF EXISTS agent_task_queue_initiator_user_id_fkey;

```

## server/go/migrations/119_user_created_at_index.up.sql

```sql
-- Index on "user".created_at to support ordering/filtering users by signup time.
--
-- "user" is a reserved word so it stays double-quoted. The migration runner
-- executes files outside an explicit transaction, so CONCURRENTLY is kept in
-- its own single-statement migration to avoid Postgres' implicit transaction
-- block for multi-statement query strings.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_created_at
    ON "user" (created_at);

```

## server/go/migrations/120_autopilot_subscriber.up.sql

```sql
-- Template list of workspace members auto-subscribed to every issue spawned
-- by the autopilot. Members-only for now (broaden the CHECK to expand).
-- No foreign keys or cascades — autopilot existence and workspace membership
-- are both enforced in the application layer (the autopilot delete handler
-- removes these rows in the same transaction; membership is checked at the API
-- boundary via isWorkspaceEntity), per the repo rule. Mirrors issue_subscriber's
-- app-level user_id handling.
CREATE TABLE autopilot_subscriber (
    autopilot_id UUID NOT NULL,
    user_type    TEXT NOT NULL CHECK (user_type IN ('member')),
    user_id      UUID NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (autopilot_id, user_type, user_id)
);

-- Reverse-lookup index for "which autopilots auto-subscribe this member?";
-- the PK can't answer that since autopilot_id is its leading column.
CREATE INDEX idx_autopilot_subscriber_user
    ON autopilot_subscriber (user_type, user_id);

ALTER TABLE issue_subscriber DROP CONSTRAINT issue_subscriber_reason_check;
ALTER TABLE issue_subscriber ADD CONSTRAINT issue_subscriber_reason_check
    CHECK (reason IN ('creator', 'assignee', 'commenter', 'mentioned', 'manual', 'autopilot'));

```

## server/go/migrations/120_comment_source_task_id.up.sql

```sql
-- Trace pointer to the agent_task_queue row that produced this comment, used by
-- the "retry failed agent comment" affordance. No FK on source_task_id: the
-- referenced task can be GC'd independently of the comment it produced, and the
-- relationship is resolved in the application layer (a missing task simply means
-- the source is no longer retryable). Matches the repo rule that foreign keys
-- and cascades are handled by the app, not the database.
ALTER TABLE comment
  ADD COLUMN source_task_id UUID;

```

## server/go/migrations/120_github_pending_installation.up.sql

```sql
-- Temporarily stores installation webhook account metadata when GitHub sends
-- installation.created before the setup callback has bound installation_id to
-- a workspace. No foreign keys: the workspace binding is resolved later by the
-- setup callback.
CREATE TABLE github_pending_installation (
    installation_id BIGINT PRIMARY KEY,
    account_login   TEXT NOT NULL CHECK (account_login <> ''),
    account_type    TEXT NOT NULL DEFAULT 'User'
        CHECK (account_type IN ('User', 'Organization')),
    account_avatar_url TEXT,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/120_runtime_profile.up.sql

```sql
-- Custom Runtime, PR1 (schema only). See MUL-3284 / GitHub issue #3667.
--
-- Adds the workspace-level `runtime_profile` table (the shared, team-visible
-- definition of a "custom runtime" — e.g. an in-house Codex wrapper) and gives
-- `agent_runtime` a stable `profile_id` so the same daemon can host multiple
-- runtimes of the same protocol family.
--
-- Referential integrity policy (house rule): this migration does NOT add any
-- new database foreign keys or ON DELETE cascades. `workspace_id`,
-- `created_by` and `agent_runtime.profile_id` are plain UUID columns; the
-- relationships they model are enforced in the application layer, not by the
-- database. In particular, deleting a runtime_profile must clean up its
-- associated agent_runtime instance rows in application code (PR2's profile
-- delete path) — the database will no longer cascade that for us.
--
-- Scope is deliberately additive only:
--   * The legacy `UNIQUE (workspace_id, daemon_id, provider)` constraint on
--     agent_runtime is left INTACT so the existing registration upsert
--     (`ON CONFLICT (workspace_id, daemon_id, provider)` in runtime.sql) keeps
--     resolving its arbiter. Converting that key into a partial index
--     (WHERE profile_id IS NULL) and teaching the upsert to be profile-aware
--     is PR2's registration work, not this migration's.
--   * `profile_id` is NULL for every existing/built-in runtime row, so the new
--     partial unique index does not constrain any current data.
--
-- Iron rule honored here at the schema level: the profile does NOT carry a
-- generic per-agent args field. Per-agent launch args continue to live on
-- `agent.custom_args`. The only args column is `fixed_args` — the fixed
-- arguments that EVERY agent on this runtime must inherit to enter a
-- compatible mode (advanced/optional, defaults to an empty array).

CREATE TABLE runtime_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Owning workspace. Plain UUID; integrity (and cleanup on workspace
    -- delete) is enforced in the application layer, not by a DB FK.
    workspace_id UUID NOT NULL,
    display_name TEXT NOT NULL,
    -- protocol_family must stay in lockstep with the agent.New() switch in
    -- server/go/pkg/agent/agent.go. A profile may only be based on a backend
    -- Workpal already officially supports and tests.
    protocol_family TEXT NOT NULL CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'gemini',
        'pi',
        'cursor',
        'kimi',
        'kiro',
        'antigravity'
    )),
    command_name TEXT NOT NULL,
    description TEXT,
    fixed_args JSONB NOT NULL DEFAULT '[]',
    visibility TEXT NOT NULL DEFAULT 'workspace' CHECK (visibility IN ('workspace', 'private')),
    -- Creating user. Plain UUID, nullable; no DB FK.
    created_by UUID,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, display_name)
);

CREATE INDEX idx_runtime_profile_workspace ON runtime_profile(workspace_id);

-- Stable profile identity on the runtime instance row. NULL = built-in runtime
-- (registered the legacy way); non-NULL = a registered instance of a custom
-- profile. Plain UUID with no DB FK: the link to runtime_profile, and the
-- cleanup of these rows when a profile is deleted, is the application layer's
-- responsibility (PR2).
ALTER TABLE agent_runtime
    ADD COLUMN profile_id UUID;

-- Custom-runtime uniqueness: one instance per (workspace, daemon, profile).
-- Partial so it never touches built-in rows (profile_id IS NULL) and never
-- conflicts with the legacy (workspace_id, daemon_id, provider) constraint.
CREATE UNIQUE INDEX agent_runtime_workspace_daemon_profile_key
    ON agent_runtime (workspace_id, daemon_id, profile_id)
    WHERE profile_id IS NOT NULL;

```

## server/go/migrations/121_agent_runtime_provider_partial_unique.up.sql

```sql
-- Custom Runtime, PR2 (registration extension). See MUL-3284 / GitHub #3667.
--
-- PR1 (migration 120) added agent_runtime.profile_id and a partial unique index
-- for custom-runtime instances, but deliberately left the legacy
-- UNIQUE (workspace_id, daemon_id, provider) constraint intact so the existing
-- registration upsert kept working. That non-partial constraint blocks a
-- built-in runtime (profile_id IS NULL) and a custom runtime of the SAME
-- protocol family (provider) from coexisting on one daemon.
--
-- PR2 makes registration profile-aware, so we now convert that legacy key into
-- a PARTIAL unique index scoped to built-in rows only (profile_id IS NULL).
-- Combined with 120's partial index on (workspace_id, daemon_id, profile_id)
-- WHERE profile_id IS NOT NULL, this lets a single daemon host the built-in
-- codex AND any number of custom codex-based profiles without collision, while
-- still enforcing one built-in runtime per (workspace, daemon, provider).
--
-- The matching upserts now spell out the predicate in their ON CONFLICT
-- arbiter (see pkg/db/queries/runtime.sql): built-in registration targets
-- (workspace_id, daemon_id, provider) WHERE profile_id IS NULL; custom
-- registration targets (workspace_id, daemon_id, profile_id) WHERE
-- profile_id IS NOT NULL.

ALTER TABLE agent_runtime
    DROP CONSTRAINT agent_runtime_workspace_id_daemon_id_provider_key;

CREATE UNIQUE INDEX agent_runtime_workspace_daemon_provider_key
    ON agent_runtime (workspace_id, daemon_id, provider)
    WHERE profile_id IS NULL;

```

## server/go/migrations/122_lark_chat_session_binding_thread_reply.up.sql

```sql
-- Thread-aware outbound: remember the most recent inbound trigger
-- message (and the Lark topic / thread it belongs to, if any) per chat
-- binding so the decoupled outbound patcher can thread its reply back
-- into the originating 话题 (thread) instead of always posting a fresh
-- message at the chat level.
--
-- The outbound side is event-driven and disconnected from the inbound
-- message: it only knows the chat_session → lark_chat_session_binding
-- (i.e. the lark_chat_id). Persisting the latest trigger here is what
-- lets EventChatDone resolve a reply target without plumbing the
-- message id through the whole task lifecycle.
--
-- Both columns are nullable:
--   * last_lark_message_id is the message_id the reply quotes / replies
--     to (Lark's reply endpoint keys off it).
--   * last_lark_thread_id is the message's thread_id; Lark only sends a
--     thread_id for messages that are part of a topic, so a NULL/empty
--     value means "the last trigger was a normal chat message" and the
--     outbound keeps the existing chat-level send behavior. Only when a
--     thread_id is present does the patcher switch to a thread reply.
ALTER TABLE lark_chat_session_binding
    ADD COLUMN last_lark_message_id TEXT,
    ADD COLUMN last_lark_thread_id  TEXT;

```

## server/go/migrations/122_task_handoff_note.up.sql

```sql
-- Handoff note: a first-class, optional free-text instruction attached when an
-- issue is assigned/promoted to an agent or squad (MUL-3375). The daemon
-- renders it into the run's opening prompt and issue_context.md via a dedicated
-- "assignment handoff" branch — NOT by fabricating a comment or reusing
-- trigger_comment_id. NULL means "no handoff note" (today's behavior).
ALTER TABLE agent_task_queue ADD COLUMN handoff_note TEXT;

```

## server/go/migrations/123_issue_stage.up.sql

```sql
-- Per-issue `stage` ordinal: groups sub-issues sharing the same parent into
-- ordered barrier groups. NULL = unstaged (the issue does not participate in
-- staged grouping). Stage is interpreted relative to siblings under the same
-- parent_issue_id; a value on a top-level issue is inert.
--
-- The child-done -> parent notification + assignee wake fires only when a
-- stage barrier closes — i.e. every child in the lowest unfinished stage has
-- reached a terminal status (done/cancelled). Unstaged sibling sets behave as
-- a single implicit stage, so the wake fires once when the last child
-- finishes rather than on every child. See
-- server/go/internal/handler/issue_child_done.go (stageBarrierClosed).
--
-- Stages are 1-based; the CHECK keeps the column clean (NULL or >= 1) so the
-- "unstaged" sentinel stays unambiguous.
ALTER TABLE issue ADD COLUMN stage INTEGER CHECK (stage IS NULL OR stage >= 1);

```

## server/go/migrations/124_autopilot_run_planned_at.up.sql

```sql
-- Adds planned_at + a partial unique constraint on (trigger_id, planned_at) to
-- autopilot_run. The column anchors each run to the canonical UTC planned fire
-- time of its triggering occurrence; the unique index is the dispatch-layer
-- idempotency guard for scheduled triggers.
--
-- Why we need it (MUL-3551):
--
--   * The primary idempotency for scheduled dispatch lives one layer up, in
--     `sys_cron_executions` (job_name, scope_kind, scope_id, plan_time). A
--     successful claim on that table is what gates running the handler.
--   * BUT: if a runner claims a plan_time, starts dispatch (creating an
--     autopilot_run row + an issue + an agent_task_queue row), then dies
--     before writing terminal SUCCESS, the row goes stale → a sibling runner
--     can steal the lease and re-enter the handler with the SAME plan_time.
--     Without a row-level guard the second attempt would create a duplicate
--     autopilot_run / issue / task.
--   * This index makes that double-create a primary-key conflict, so the
--     stale-steal path can detect "this plan_time already produced a run"
--     and reuse it instead of creating a duplicate.
--
-- Partial-unique is correct here because:
--
--   * Manual triggers and webhook triggers leave planned_at NULL (they have
--     no canonical fire time). The constraint must not apply to them.
--   * Pre-existing autopilot_run rows are all (planned_at IS NULL) — no
--     backfill needed, no migration risk.
--
-- The DEFAULT NULL keeps the existing trigger paths (manual / webhook / api
-- source) untouched; only DispatchAutopilotForPlan writes a non-NULL value.

ALTER TABLE autopilot_run
    ADD COLUMN planned_at TIMESTAMPTZ;

CREATE UNIQUE INDEX uq_autopilot_run_trigger_planned
    ON autopilot_run (trigger_id, planned_at)
    WHERE trigger_id IS NOT NULL AND planned_at IS NOT NULL;

```

## server/go/migrations/124_channel_generalization.up.sql

```sql
-- Generalize the Feishu/Lark-specific integration tables into
-- platform-agnostic channel_* tables (MUL-3515, parent MUL-3506). Each
-- lark_* table gains a `channel_type` discriminator and moves its
-- platform-specific identifiers/config into a JSONB `config` column; the
-- cross-platform columns stay flat. Existing Feishu rows are backfilled
-- with channel_type='feishu'.
--
-- Two hard rules from the design:
--
--   * NO foreign keys and NO cascades (MUL-3515 §4). The lark_* tables
--     leaned on composite FKs to enforce "a binding's workspace matches
--     its installation" and "a binding dies when workspace membership is
--     revoked / a chat_session is deleted". Those integrity rules now
--     live in the application layer (the cutover PR adds the membership
--     check + cleanup). The columns are kept so the app can still join,
--     but the database enforces nothing.
--
--   * The lark_* tables are NOT dropped here — that happens in a later
--     migration once the Go cutover has landed, so this migration can
--     ship green on its own. This migration only ADDS channel_* and
--     copies the data forward.
--
--   * ROLLOUT. This backfill is a one-time copy and the Lark hub is an
--     in-process goroutine, so a cutover has TWO independent invariants:
--       (a) channel_* must exist BEFORE any new (channel_*) build serves the
--           HTTP paths that touch it — installation list/install/revoke,
--           chat-session delete, member revoke — or those paths 500.
--       (b) the OLD (lark_*) hub and the NEW (channel_*) hub must never run at
--           once: each would claim the same Feishu bot's WS lease on its own
--           table and open a duplicate connection, double-processing inbound
--           events (duplicate messages / /issue / runs). The two table sets
--           never cross-deduplicate.
--
--     SELF-HOST (Docker Compose / Helm) satisfies both automatically and needs
--     NO flags or manual steps. The backend entrypoint runs `migrate up`
--     before the server starts, so channel_* exists before the new build
--     serves (a); the deployment is single-replica `Recreate`, so the old pod
--     (and its hub) fully stops before the new pod starts (b). A normal
--     version upgrade is a clean cutover. Only a self-host re-tuned to
--     multi-replica RollingUpdate needs the prd procedure below.
--
--     PRD (rolling workpal-api, maxUnavailable:0) overlapped old and new pods.
--     A one-time WORKPAL_LARK_HUB_DISABLED park-switch existed during the
--     cutover to hold a hub dormant while the API stayed up, so only one hub
--     was ever live (invariant b). That cutover is complete and the switch has
--     since been removed (MUL-3515); this note is kept as history. Rollback to
--     a pre-cutover build is not lossless once the new hub has written Feishu
--     state into channel_*.
--
-- app_secret_encrypted is BYTEA; it is carried into the JSONB config as a
-- base64 string. PostgreSQL's encode(...,'base64') MIME-wraps the output
-- with a newline every 76 chars, and a secretbox-sealed app secret (~72
-- bytes) exceeds that, so we strip the newlines: Go's encoding/json decodes
-- a base64 string into a []byte field with base64.StdEncoding, which rejects
-- embedded newlines. Stripping keeps the bytea -> JSON -> []byte round-trip
-- symmetric (the Go writer emits unwrapped base64 too) and the ciphertext is
-- never stored in plaintext.

-- =====================
-- channel_installation
-- =====================
CREATE TABLE channel_installation (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id          UUID NOT NULL,
    agent_id              UUID NOT NULL,
    channel_type          TEXT NOT NULL,
    -- Platform-specific identifiers/config. For feishu:
    --   app_id, app_secret_encrypted (base64), tenant_key, bot_open_id,
    --   bot_union_id, region.
    config                JSONB NOT NULL DEFAULT '{}'::jsonb,
    status                TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'revoked')),
    ws_lease_token        TEXT,
    ws_lease_expires_at   TIMESTAMPTZ,
    installer_user_id     UUID NOT NULL,
    installed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- One installation per (agent, channel_type): an agent may connect more
    -- than one IM at once (feishu + slack + ...), but only one of each kind.
    -- The old lark_installation had UNIQUE(workspace_id, agent_id) because
    -- feishu was the only channel; with a channel_type discriminator the
    -- natural generalization adds it to the key. In the current feishu-only
    -- world this is behaviorally identical (one row per agent). If the
    -- product later wants "one agent, at most one IM regardless of type",
    -- that is an application-layer rule (MUL-3515 §4), not a DB constraint.
    UNIQUE (workspace_id, agent_id, channel_type)
);

CREATE INDEX idx_channel_installation_workspace ON channel_installation(workspace_id);
CREATE INDEX idx_channel_installation_agent ON channel_installation(agent_id);
CREATE INDEX idx_channel_installation_lease ON channel_installation(ws_lease_expires_at)
    WHERE status = 'active';
-- Routing key. Inbound events carry only the platform app identifier
-- (Feishu app_id); the dispatcher routes on (channel_type, app_id). The
-- functional unique index replaces the old global UNIQUE(app_id) and is
-- scoped per channel_type. Rows without an app_id (a future channel that
-- routes differently) store JSON null here, and Postgres allows many
-- NULLs in a unique index, so they do not collide.
CREATE UNIQUE INDEX idx_channel_installation_type_appid
    ON channel_installation(channel_type, (config ->> 'app_id'));

INSERT INTO channel_installation (
    id, workspace_id, agent_id, channel_type, config, status,
    ws_lease_token, ws_lease_expires_at, installer_user_id,
    installed_at, created_at, updated_at
)
SELECT
    id, workspace_id, agent_id, 'feishu',
    jsonb_strip_nulls(jsonb_build_object(
        'app_id',               app_id,
        'app_secret_encrypted', replace(encode(app_secret_encrypted, 'base64'), E'\n', ''),
        'tenant_key',           tenant_key,
        'bot_open_id',          bot_open_id,
        'bot_union_id',         bot_union_id,
        'region',               region
    )),
    status, ws_lease_token, ws_lease_expires_at, installer_user_id,
    installed_at, created_at, updated_at
FROM lark_installation;

-- =====================
-- channel_user_binding
-- =====================
-- channel_user_id is the platform-native, per-installation user id
-- (Feishu open_id). union_id and any other secondary identity goes in
-- config. The member-FK that used to make a row's existence proof of
-- workspace membership is gone; the cutover PR validates membership in
-- the identity check and prunes bindings on member removal.
CREATE TABLE channel_user_binding (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     UUID NOT NULL,
    workpal_user_id  UUID NOT NULL,
    installation_id  UUID NOT NULL,
    channel_type     TEXT NOT NULL,
    channel_user_id  TEXT NOT NULL,
    config           JSONB NOT NULL DEFAULT '{}'::jsonb,
    bound_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (installation_id, channel_user_id)
);

CREATE INDEX idx_channel_user_binding_user
    ON channel_user_binding(workpal_user_id, workspace_id);
CREATE INDEX idx_channel_user_binding_workspace_user
    ON channel_user_binding(workspace_id, channel_user_id);

INSERT INTO channel_user_binding (
    id, workspace_id, workpal_user_id, installation_id,
    channel_type, channel_user_id, config, bound_at
)
SELECT
    id, workspace_id, workpal_user_id, installation_id,
    'feishu', lark_open_id,
    jsonb_strip_nulls(jsonb_build_object('union_id', union_id)),
    bound_at
FROM lark_user_binding;

-- =====================
-- channel_chat_session_binding
-- =====================
CREATE TABLE channel_chat_session_binding (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_session_id   UUID NOT NULL,
    installation_id   UUID NOT NULL,
    channel_type      TEXT NOT NULL,
    channel_chat_id   TEXT NOT NULL,
    chat_type         TEXT NOT NULL
        CHECK (chat_type IN ('p2p', 'group')),
    -- Most-recent inbound trigger, so the decoupled outbound patcher can
    -- thread its reply back into the originating topic. Nullable; a NULL
    -- thread id keeps the chat-level send path.
    last_message_id   TEXT,
    last_thread_id    TEXT,
    config            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (installation_id, channel_chat_id),
    UNIQUE (chat_session_id)
);

CREATE INDEX idx_channel_chat_session_binding_session
    ON channel_chat_session_binding(chat_session_id);

INSERT INTO channel_chat_session_binding (
    id, chat_session_id, installation_id, channel_type,
    channel_chat_id, chat_type, last_message_id, last_thread_id, created_at
)
SELECT
    id, chat_session_id, installation_id, 'feishu',
    lark_chat_id, lark_chat_type, last_lark_message_id, last_lark_thread_id, created_at
FROM lark_chat_session_binding;

-- =====================
-- channel_inbound_message_dedup
-- =====================
-- Two-phase idempotency with owner fencing, unchanged in shape from
-- lark_inbound_message_dedup (keyed per installation + message). Transient
-- 24h cache; copied forward for completeness.
CREATE TABLE channel_inbound_message_dedup (
    installation_id  UUID NOT NULL,
    message_id       TEXT NOT NULL,
    received_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at     TIMESTAMPTZ,
    claim_token      UUID NOT NULL DEFAULT gen_random_uuid(),
    PRIMARY KEY (installation_id, message_id)
);

CREATE INDEX idx_channel_inbound_dedup_received
    ON channel_inbound_message_dedup(received_at);

INSERT INTO channel_inbound_message_dedup (
    installation_id, message_id, received_at, processed_at, claim_token
)
SELECT installation_id, message_id, received_at, processed_at, claim_token
FROM lark_inbound_message_dedup;

-- =====================
-- channel_inbound_audit
-- =====================
-- Non-content drop audit. installation_id is nullable (the old ON DELETE
-- SET NULL is now just a nullable column the app may leave NULL).
CREATE TABLE channel_inbound_audit (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id     UUID,
    channel_type        TEXT NOT NULL,
    channel_chat_id     TEXT,
    event_type          TEXT NOT NULL,
    channel_event_id    TEXT,
    channel_message_id  TEXT,
    drop_reason         TEXT NOT NULL,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_channel_inbound_audit_installation
    ON channel_inbound_audit(installation_id, received_at DESC);
CREATE INDEX idx_channel_inbound_audit_reason
    ON channel_inbound_audit(drop_reason, received_at DESC);

INSERT INTO channel_inbound_audit (
    id, installation_id, channel_type, channel_chat_id, event_type,
    channel_event_id, channel_message_id, drop_reason, received_at
)
SELECT
    id, installation_id, 'feishu', lark_chat_id, event_type,
    lark_event_id, lark_message_id, drop_reason, received_at
FROM lark_inbound_audit;

-- =====================
-- channel_outbound_card_message
-- =====================
CREATE TABLE channel_outbound_card_message (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_session_id          UUID NOT NULL,
    task_id                  UUID,
    channel_type             TEXT NOT NULL,
    channel_chat_id          TEXT NOT NULL,
    channel_card_message_id  TEXT NOT NULL,
    status                   TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'streaming', 'final', 'error')),
    last_patched_at          TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_channel_outbound_card_task
    ON channel_outbound_card_message(task_id)
    WHERE task_id IS NOT NULL;
CREATE INDEX idx_channel_outbound_card_session
    ON channel_outbound_card_message(chat_session_id, created_at DESC);

INSERT INTO channel_outbound_card_message (
    id, chat_session_id, task_id, channel_type, channel_chat_id,
    channel_card_message_id, status, last_patched_at, created_at
)
SELECT
    id, chat_session_id, task_id, 'feishu', lark_chat_id,
    lark_card_message_id, status, last_patched_at, created_at
FROM lark_outbound_card_message;

-- =====================
-- channel_binding_token
-- =====================
CREATE TABLE channel_binding_token (
    token_hash       TEXT PRIMARY KEY,
    workspace_id     UUID NOT NULL,
    installation_id  UUID NOT NULL,
    channel_type     TEXT NOT NULL,
    channel_user_id  TEXT NOT NULL,
    expires_at       TIMESTAMPTZ NOT NULL,
    consumed_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Keep the product TTL cap in lockstep with channel.BindingTokenTTL
    -- (15 minutes), same as the old lark_binding_token CHECK.
    CONSTRAINT channel_binding_token_ttl_cap
        CHECK (expires_at <= created_at + INTERVAL '15 minutes')
);

CREATE INDEX idx_channel_binding_token_installation
    ON channel_binding_token(installation_id, expires_at);

INSERT INTO channel_binding_token (
    token_hash, workspace_id, installation_id, channel_type,
    channel_user_id, expires_at, consumed_at, created_at
)
SELECT
    token_hash, workspace_id, installation_id, 'feishu',
    lark_open_id, expires_at, consumed_at, created_at
FROM lark_binding_token;

```

## server/go/migrations/124_task_prepare_lease.up.sql

```sql
ALTER TABLE agent_task_queue
  ADD COLUMN prepare_lease_expires_at TIMESTAMPTZ;

```

## server/go/migrations/125_agent_task_queue_dispatched_prepare_index.up.sql

```sql
-- Covers reclaim scans over dispatched tasks while allowing prepare lease checks.
--
-- agent_task_queue is hot, so this must stay in its own single-statement
-- migration and must use CONCURRENTLY. Keeping CONCURRENTLY isolated avoids
-- Postgres' implicit transaction block for multi-statement query strings.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_dispatched_prepare
    ON agent_task_queue (runtime_id, priority DESC, dispatched_at ASC)
    WHERE status = 'dispatched' AND started_at IS NULL;

```

## server/go/migrations/126_runtime_profile_drop_gemini.up.sql

```sql
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

-- Enforce the new whitelist for future writes without blocking upgrades for
-- workspaces that already have historical Gemini custom runtime profiles.
ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'kiro',
        'antigravity'
    )) NOT VALID;

```

## server/go/migrations/127_issue_pull_request_reference_only.up.sql

```sql
-- Persist whether a PR ↔ issue link is justified ONLY by a bare mention of the
-- issue identifier in the PR description (body), with no closing keyword and no
-- reference in the PR title or branch name. The auto-link layer stays generous
-- and still records the link row (so close_intent can be tracked and downgraded
-- across edits), but a reference-only link is hidden from the issue's PR list:
-- a passing "Related MUL-1" / "Follow up in MUL-1" mention should not surface
-- the PR as if it were a working PR for that issue.
--
-- Defaults to FALSE so pre-existing links keep showing until their PR's next
-- webhook re-evaluates the reference.
ALTER TABLE issue_pull_request
    ADD COLUMN reference_only BOOLEAN NOT NULL DEFAULT FALSE;

```

## server/go/migrations/127_task_squad_id.up.sql

```sql
-- agent_task_queue.squad_id records the squad a leader-task belongs to. The
-- daemon uses it at claim time to locate the squad whose briefing (Operating
-- Protocol + Roster + Instructions) should be injected onto the leader agent's
-- instructions, instead of inferring the squad by reverse-looking-up
-- "which squad is this agent the leader of" (which is ambiguous when one
-- agent leads multiple squads).
--
-- No FK to squad(id) on purpose: agent_task_queue is a hot, high-write task
-- queue, and we don't want squad maintenance (archive / hard-delete) to take
-- cross-table locks against it. If a squad is hard-deleted and a stale UUID
-- lingers here, the daemon's GetSquadInWorkspace lookup simply returns no row
-- and the claim path skips injection (err != nil branch) — exactly the same
-- observable behavior as "injection condition not matched". No stale briefing
-- is ever emitted.
ALTER TABLE agent_task_queue
    ADD COLUMN squad_id UUID NULL;

-- Partial index over leader-task rows only: small, high hit-rate. It serves
-- admin / debug queries ("which leader tasks is this squad currently
-- running"). The daemon claim path does NOT use it — that goes through the
-- task_id primary-key path.
CREATE INDEX agent_task_queue_squad_id_idx
    ON agent_task_queue (squad_id)
    WHERE squad_id IS NOT NULL;

```

## server/go/migrations/127_user_composio_connection.up.sql

```sql
-- Composio integration (Stage 2 MVP): one row per user-connected Composio
-- account. The row is the local mirror of a Composio "connected account" so the
-- product can list / disconnect connections and build per-user MCP sessions
-- without round-tripping Composio on every read.
--
-- No foreign keys / cascades by design: Workpal enforces cross-table
-- relationships at the application layer (see migration 118 dropping the
-- agent_task_queue.initiator_user_id FK). user_id is a "user".id but is left
-- unconstrained here so a user delete does not require a migration-ordered
-- cascade across integration tables.
--
-- composio_user_id always equals the Workpal user_id.String() — the
-- application keeps that mapping as an invariant so a Composio session can be
-- created from the Workpal user id alone. It is stored explicitly so a future
-- change to the mapping does not silently break already-connected accounts.
CREATE TABLE user_composio_connection (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID NOT NULL,
    toolkit_slug         TEXT NOT NULL,
    auth_config_id       TEXT NOT NULL,
    connected_account_id TEXT NOT NULL,
    composio_user_id     TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'active',
    connected_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, connected_account_id)
);

-- The hot read path is "active connections for this user" (list endpoint and
-- MCP session builder both filter on user_id + status).
CREATE INDEX user_composio_connection_user_status_idx
    ON user_composio_connection(user_id, status);

-- Webhook / callback paths look a row up by its Composio connected_account_id.
CREATE INDEX user_composio_connection_account_idx
    ON user_composio_connection(connected_account_id);

```

## server/go/migrations/128_agent_task_queue_runtime_mcp_overlay.up.sql

```sql
-- Per-task MCP overlay computed at task enqueue (dispatch) time, layered on
-- top of agent.mcp_config when the daemon prepares the execution environment.
--
-- Stage 3 of the Composio epic (MUL-3721 / MUL-3715): the Composio integration
-- writes a fresh `{"mcpServers": {"composio": {"type": "http", "url": "...",
-- "headers": {"Authorization": "Bearer ..."}}}}` here for every task whose
-- initiator user has at least one active connection. The daemon claim
-- handler merges this on top of agent.mcp_config (overlay wins on name
-- collisions because it carries the live, user-scoped MCP session URL).
--
-- The value is short-lived: it carries a bearer token that becomes useless
-- once the task ends, so we wipe it on every terminal state transition via
-- the trigger below. Worst case a still-active task row keeps the token for
-- the duration of the run, mode-0600 in DB and never logged.
ALTER TABLE agent_task_queue
    ADD COLUMN runtime_mcp_overlay JSONB NULL;

COMMENT ON COLUMN agent_task_queue.runtime_mcp_overlay IS
    'Per-task MCP servers computed at dispatch time, merged on top of agent.mcp_config. Currently used by Composio integration to inject the initiator user''s session URL. Cleared after task completes via trg_clear_runtime_mcp_overlay.';

-- Auto-clear the overlay the moment the task enters any terminal state, so
-- the row in the queue never keeps a stale bearer beyond the live run. This
-- is a defense-in-depth measure on top of how short the Composio session
-- token already is — clearing here means a future audit of the table never
-- finds bearers attached to rows that finished hours/days ago.
--
-- Trigger-based rather than per-query SET clauses because the terminal
-- transitions live in ~12 different sqlc queries (CompleteAgentTask,
-- FailAgentTask, FailStaleTasks, ExpireStaleQueuedTasks, FailTasksFor
-- OfflineRuntimes, RecoverOrphanedTasksForRuntime, plus six Cancel*
-- variants); a trigger is a single source of truth that future queries
-- can't bypass.
CREATE OR REPLACE FUNCTION clear_runtime_mcp_overlay_on_terminal_state()
RETURNS TRIGGER AS $$
BEGIN
    -- Only act on actual transitions INTO a terminal state from a non-terminal
    -- one, and only when there is something to wipe. Re-touching an already-
    -- terminal row (or a row whose overlay is already NULL) leaves the
    -- column unchanged and the trigger is a cheap no-op.
    IF NEW.status IN ('completed', 'failed', 'cancelled')
       AND OLD.status IS DISTINCT FROM NEW.status
       AND NEW.runtime_mcp_overlay IS NOT NULL THEN
        NEW.runtime_mcp_overlay := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_clear_runtime_mcp_overlay ON agent_task_queue;
CREATE TRIGGER trg_clear_runtime_mcp_overlay
    BEFORE UPDATE OF status ON agent_task_queue
    FOR EACH ROW
    EXECUTE FUNCTION clear_runtime_mcp_overlay_on_terminal_state();

```

## server/go/migrations/128_autopilot_collaborator.up.sql

```sql
-- Explicit write grants for autopilots: lets an autopilot's creator (or a
-- workspace owner/admin) authorize specific workspace members to manage the
-- autopilot, beyond the implicit "creator ∪ owner/admin" set. A member listed
-- here is treated as a writer — they can edit, delete, trigger, replay
-- deliveries, and manage triggers/webhook secrets (MUL-3807).
--
-- No foreign keys or cascades — autopilot existence and workspace membership
-- are enforced in the application layer (the autopilot delete handler removes
-- these rows in the same transaction; membership is checked at the API
-- boundary), per the repo rule. Mirrors autopilot_subscriber.
CREATE TABLE autopilot_collaborator (
    autopilot_id UUID NOT NULL,
    user_type    TEXT NOT NULL CHECK (user_type IN ('member')),
    user_id      UUID NOT NULL,
    granted_by   UUID NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (autopilot_id, user_type, user_id)
);

-- Reverse-lookup index for "which autopilots can this member write?" — the PK
-- can't answer that since autopilot_id is its leading column.
CREATE INDEX idx_autopilot_collaborator_user
    ON autopilot_collaborator (user_type, user_id);

```

## server/go/migrations/128_comment_routing_escalation.up.sql

```sql
ALTER TABLE agent_task_queue
    ADD COLUMN escalation_for_task_id UUID,
    ADD COLUMN fire_at TIMESTAMPTZ;

ALTER TABLE agent_task_queue
    DROP CONSTRAINT agent_task_queue_status_check,
    ADD CONSTRAINT agent_task_queue_status_check
        CHECK (status IN (
            'queued',
            'dispatched',
            'running',
            'completed',
            'failed',
            'cancelled',
            'waiting_local_directory',
            'deferred'
        ));

CREATE INDEX idx_agent_task_queue_deferred_fire
    ON agent_task_queue (runtime_id, fire_at)
    WHERE status = 'deferred';

CREATE INDEX idx_agent_task_queue_escalation_for
    ON agent_task_queue (escalation_for_task_id)
    WHERE escalation_for_task_id IS NOT NULL;

```

## server/go/migrations/129_agent_composio_allowlist_and_task_originator.up.sql

```sql
-- Stage 3.1 of the Composio epic (MUL-3869, parent MUL-3721): turn the default
-- behaviour from "all-on" into "Composio MCP is only mounted when (a) the
-- agent's owner has explicitly allowlisted toolkits AND (b) the run originator
-- at the top of the trigger chain is that same owner".
--
-- Two columns ship together because the dispatch decision needs both:
--   * agent.composio_toolkit_allowlist — which toolkits the agent is allowed
--     to surface; NULL or [] = no MCP overlay regardless of who triggers.
--   * agent_task_queue.originator_user_id — the top-of-chain human originator
--     for THIS task, inherited across agent @-mention fanout. The dispatch
--     hook gates on (originator == agent.owner_id) so an agent never gets
--     another user's Composio session even if that other user @-mentions it.

-- ----------------------------------------------------------------------------
-- agent.composio_toolkit_allowlist
-- ----------------------------------------------------------------------------
ALTER TABLE agent
    ADD COLUMN composio_toolkit_allowlist TEXT[] NULL;

COMMENT ON COLUMN agent.composio_toolkit_allowlist IS
    'Composio toolkit slugs this agent is allowed to mount as MCP. NULL or empty array = no MCP. Only effective when the run originator matches agent.owner_id; see migration 129 + MUL-3869 / MUL-3721. Stored as TEXT[] so the dispatch path can intersect against the originator''s active connections with a single SQL ANY() filter, no JSON parse on the hot path.';

-- ----------------------------------------------------------------------------
-- agent_task_queue.originator_user_id
-- ----------------------------------------------------------------------------
--
-- Distinct from initiator_user_id (migration 117): initiator is whoever
-- physically sent the triggering message — which for an agent fan-out is
-- ANOTHER AGENT, not a human — and is set today only for chat tasks. The
-- Composio overlay decision needs the HUMAN at the top of the chain so we
-- never inadvertently project a human's connected apps into a run that
-- person did not start. Hence a dedicated column whose contract is "the
-- originator is always a 'user' row (or NULL when none can be attributed,
-- e.g. autopilot/system runs)".
--
-- No FK to "user" by design (matches initiator_user_id and the
-- comment.source_task_id pattern): foreign keys on hot-path queue tables
-- have lock implications on busy production deploys, and the column only
-- feeds best-effort overlay decisions — a stale id simply degrades to "no
-- overlay", never a corrupt run.
ALTER TABLE agent_task_queue
    ADD COLUMN originator_user_id UUID NULL;

COMMENT ON COLUMN agent_task_queue.originator_user_id IS
    'Top-of-chain human originator for this run. For human-triggered tasks (comment by a member, chat, quick-create) equals that member. For agent-fanout tasks (agent A @-mentions agent B) inherited from the parent task''s originator_user_id via comment.source_task_id. NULL when no human is in the chain (autopilot, system-driven). Used by the Composio MCP overlay dispatch to require originator == agent.owner_id; see migration 129 + MUL-3869.';

-- Dispatch reads originator_user_id for every overlay decision; a partial
-- index on the non-NULL subset keeps the working set small (autopilot and
-- pre-stage-3.1 rows stay out of the index entirely).
CREATE INDEX agent_task_queue_originator_user_id_idx
    ON agent_task_queue(originator_user_id)
    WHERE originator_user_id IS NOT NULL;

```

## server/go/migrations/130_agent_invocation_permission.up.sql

```sql
-- Agent invocation permission system, V1 (MUL-3963, parent MUL-3715 Composio epic).
--
-- Splits "who may TRIGGER/INVOKE an agent" out of the overloaded `visibility`
-- column into an explicit, extensible model:
--
--   * agent.permission_mode: 'private' | 'public_to'
--       - private   -> only the agent owner may invoke. Workspace admin does
--         NOT bypass this any more (that was the privacy hole described in the
--         issue: an admin could invoke someone's private agent and read their
--         mailbox via that agent's Composio connections).
--       - public_to -> an owner-configured allow-list of invocation targets
--         (see agent_invocation_target) decides who may invoke. Targets stack:
--         one agent may combine a workspace target + specific members + (future)
--         teams; canInvokeAgent admits an actor matching ANY target (OR).
--
--   * agent_invocation_target: the allow-list rows for public_to agents.
--       - target_type = 'workspace' -> every workspace member may invoke.
--       - target_type = 'member'    -> only the specific user may invoke.
--       - target_type = 'team'      -> reserved for the future team concept;
--         stored but NOT effective in V1 (no team membership source yet).
--
-- `visibility` is intentionally left in place and kept in sync as a DERIVED
-- legacy field by the API layer (private/public_to-member-only -> 'private',
-- public_to-workspace -> 'workspace'), so old clients never see a permission
-- WIDENING. All new trigger/dispatch decisions read permission_mode + targets
-- via canInvokeAgent; visibility is no longer an authorization source.

-- ----------------------------------------------------------------------------
-- agent.permission_mode
-- ----------------------------------------------------------------------------
ALTER TABLE agent
    ADD COLUMN permission_mode TEXT NOT NULL DEFAULT 'private'
        CHECK (permission_mode IN ('private', 'public_to'));

COMMENT ON COLUMN agent.permission_mode IS
    'Agent invocation permission mode (MUL-3963). private = owner only; public_to = allow-list in agent_invocation_target. Replaces visibility as the authorization source for triggering runs; visibility is now a derived legacy field. Default private = deny-by-default.';

-- ----------------------------------------------------------------------------
-- agent_invocation_target
-- ----------------------------------------------------------------------------
--
-- NO foreign keys by design (Workpal migration rule, matching the MUL-3515 §4
-- channel_* generalization): relationships are maintained in the application
-- layer, not by the database. Concretely:
--   * agent_id  — cleaned up alongside agent hard-deletes
--     (DeleteAgentInvocationTargetsByArchivedRuntimeAgents runs before
--     DeleteArchivedAgentsByRuntime in the runtime-delete tx). Agents are
--     normally soft-archived, so rows persist across archive/restore.
--   * created_by / member target_id — pruned on member removal via
--     DeleteAgentInvocationTargetsByMember inside the revoke-member tx, so a
--     re-invited user does not inherit stale invocation grants.
--
-- target_id is polymorphic (workspace_id / user_id / future team_id) so it
-- carries NO FK anyway. For 'workspace' rows we store the agent's workspace_id
-- (rather than NULL) so the UNIQUE(agent_id, target_type, target_id) constraint
-- dedups cleanly — Postgres treats NULLs as distinct, which would otherwise
-- allow duplicate workspace rows. member/team rows must carry a target_id.
CREATE TABLE agent_invocation_target (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id    UUID NOT NULL,
    target_type TEXT NOT NULL CHECK (target_type IN ('workspace', 'member', 'team')),
    target_id   UUID NOT NULL,
    created_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_id, target_type, target_id)
);

COMMENT ON TABLE agent_invocation_target IS
    'Allow-list of who may invoke a public_to agent (MUL-3963). One row per (agent, target_type, target); targets stack and canInvokeAgent OR-matches. workspace rows store the agent workspace_id in target_id; member rows store the user id; team rows are reserved and inert in V1. Rows only matter when agent.permission_mode = public_to. No DB foreign keys: agent_id / created_by / member target_id relationships are maintained in the application layer (see migration comment).';

CREATE INDEX agent_invocation_target_agent_id_idx
    ON agent_invocation_target(agent_id);

-- Reverse lookup: member-target cleanup on user removal, and "which agents can
-- this member invoke" style filters.
CREATE INDEX agent_invocation_target_target_idx
    ON agent_invocation_target(target_type, target_id);

-- ----------------------------------------------------------------------------
-- Backfill from legacy visibility (lossless migration)
-- ----------------------------------------------------------------------------
--   visibility = 'private'   -> permission_mode = 'private' (column default), no target
--   visibility = 'workspace' -> permission_mode = 'public_to' + one workspace target
UPDATE agent SET permission_mode = 'public_to' WHERE visibility = 'workspace';

INSERT INTO agent_invocation_target (agent_id, target_type, target_id, created_by)
SELECT id, 'workspace', workspace_id, NULL
FROM agent
WHERE visibility = 'workspace'
ON CONFLICT (agent_id, target_type, target_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- Refresh two Composio-era column comments to the MUL-3963 rules (the overlay
-- now FOLLOWS invocation permission and uses the agent OWNER's connection; the
-- old "originator must equal owner" gate is gone). These COMMENT ON COLUMN
-- statements also drive the sqlc-generated doc comments in models.go.
-- ----------------------------------------------------------------------------
COMMENT ON COLUMN agent.composio_toolkit_allowlist IS
    'Composio toolkit slugs this agent is allowed to mount as MCP. NULL or empty array = no MCP overlay. Mounted for any run that passes the agent invocation-permission gate (MUL-3963); the overlay uses the agent OWNER''s active Composio connection, so sharing the agent (public_to) shares these apps with whoever may invoke it. No longer gated on originator == owner. Stored as TEXT[] so the dispatch path can intersect against the owner''s active connections with a single SQL ANY() filter.';

COMMENT ON COLUMN agent_task_queue.originator_user_id IS
    'Top-of-chain human originator for this run. For human-triggered tasks (comment by a member, chat, quick-create) equals that member. For agent-fanout tasks inherited from the parent task''s originator_user_id via comment.source_task_id. NULL when no human is in the chain (autopilot, system-driven). Used by canInvokeAgent to judge A2A by the originator; the Composio overlay now follows invocation permission and uses the agent owner''s connection, so this is audit/attribution + A2A gating, NOT a Composio owner==originator gate (MUL-3963).';

```

## server/go/migrations/131_issue_origin_slack_chat.up.sql

```sql
-- Extend issue.origin_type to allow the Slack `/issue` command paths (both the
-- message-prefix form and the slash command) to stamp issues with
-- origin_type='slack_chat'. The Slack integration shipped this origin label
-- (originSlackChat) but no migration ever added it to the CHECK list, so every
-- Slack /issue create tripped SQLSTATE 23514 and IssueService.Create failed —
-- surfaced end-to-end by the /issue slash command (MUL-3908). Mirrors 111
-- (lark_chat), which fixed the identical gap for Lark.
ALTER TABLE issue DROP CONSTRAINT IF EXISTS issue_origin_type_check;
ALTER TABLE issue ADD CONSTRAINT issue_origin_type_check
    CHECK (origin_type IN ('autopilot', 'quick_create', 'lark_chat', 'slack_chat'));

```

## server/go/migrations/132_agent_task_queue_runtime_connected_apps.up.sql

```sql
-- Non-secret task-scoped metadata for MCP overlays. runtime_mcp_overlay holds
-- the actual server URL/headers; this column holds the semantic app mapping
-- the daemon can render into the agent brief, e.g. "Notion via MCP server
-- composio".
ALTER TABLE agent_task_queue
    ADD COLUMN runtime_connected_apps JSONB NULL;

COMMENT ON COLUMN agent_task_queue.runtime_connected_apps IS
    'Non-secret per-task connected app metadata corresponding to runtime_mcp_overlay, used by the daemon brief to tell agents which app capabilities are mounted. Cleared with runtime_mcp_overlay after task completion.';

-- Extend the existing cleanup trigger so completed rows do not retain either
-- the secret overlay or the owner integration footprint.
CREATE OR REPLACE FUNCTION clear_runtime_mcp_overlay_on_terminal_state()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('completed', 'failed', 'cancelled')
       AND OLD.status IS DISTINCT FROM NEW.status
       AND (NEW.runtime_mcp_overlay IS NOT NULL OR NEW.runtime_connected_apps IS NOT NULL) THEN
        NEW.runtime_mcp_overlay := NULL;
        NEW.runtime_connected_apps := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

```

## server/go/migrations/133_github_installation_multi_workspace.up.sql

```sql
-- Allow one GitHub App installation to bind to multiple workspaces.
--
-- Previously UNIQUE(installation_id) forced a single workspace per installation.
-- Connecting the same GitHub account/org in a second workspace ran the
-- CreateGitHubInstallation upsert, whose ON CONFLICT (installation_id) silently
-- overwrote the first workspace's binding row (#4823). Widening the uniqueness
-- key to (workspace_id, installation_id) lets each workspace keep its own row,
-- and webhook delivery is routed per-repo via the workspace.repos registry.
ALTER TABLE github_installation
    DROP CONSTRAINT github_installation_installation_id_key;

ALTER TABLE github_installation
    ADD CONSTRAINT github_installation_workspace_id_installation_id_key
    UNIQUE (workspace_id, installation_id);

-- The dropped UNIQUE(installation_id) also provided the index behind webhook
-- lookups by installation_id. The new composite constraint is keyed on
-- workspace_id first, so it cannot serve a bare installation_id lookup — add a
-- standalone index to keep that path fast.
CREATE INDEX IF NOT EXISTS idx_github_installation_installation_id
    ON github_installation(installation_id);

```

## server/go/migrations/134_runtime_profile_add_qoder.up.sql

```sql
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

-- Widen the whitelist to include Qoder so Qoder CN (`qoderclicn`) users can base
-- a custom runtime profile on the existing Qoder backend (launches
-- `<command> --yolo --acp`) instead of misrouting through Kiro/ACP with
-- incompatible arguments (#4883). NOT VALID mirrors migration 126 so a
-- historical Gemini row it intentionally tolerated does not block the upgrade.
ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'kiro',
        'antigravity',
        'qoder'
    )) NOT VALID;

```

## server/go/migrations/135_comment_workspace_index.up.sql

```sql
-- Supporting btree index on comment.workspace_id for the search handler.
--
-- Context (MUL-4059): The search handler's WHERE clause contains a
-- correlated `EXISTS` subquery over `comment` that Postgres routinely
-- rewrites into a *hashed* subplan — the subquery is evaluated once and
-- the results are hashed for lookup by the outer scan. That rewrite is
-- an optimization when the subquery is cheap; it becomes a pathology
-- when the subquery scans the entire `comment` table filtered only by
-- LIKE, because for common tokens (e.g. "search", "agent") the bigm/trgm
-- GIN index matches hundreds of thousands of rows across every
-- workspace. Confirmed on prd against `workpal-prod`: a search for
-- '%search%' returned 536,761 comment bigm hits, spilled work_mem into a
-- lossy bitmap (`Heap Blocks: exact=48297 lossy=164696`), rechecked 1.9M
-- rows, and the outer query took 32.3 s despite indexes being present.
--
-- The fix is two-part:
--   1. Query-level: buildSearchQuery now adds `c.workspace_id = $wsParam`
--      to every comment subquery. With the workspace_id as a compile-time
--      constant (same parameter as the outer WHERE), the planner can
--      collapse the hashed set to this workspace's comments only.
--   2. Index-level: this migration. Without a btree index on
--      comment.workspace_id, the pushed-down filter still triggers a
--      Seq Scan on `comment`; with it, the planner picks an Index Scan
--      or Bitmap AND with the bigm/trgm content index.
--
-- Verified on a local repro that mirrors the prd hot workspace
-- (5k issues in the target workspace, 100k comments in a sibling
-- workspace all containing "search"): the query plan drops from
-- 60 ms (hashed global scan) to 1.8 ms (subplan uses this index).
-- Prd extrapolation: 32.3 s → tens of milliseconds.
--
-- This CREATE INDEX is deliberately unwrapped. The whole point of
-- MUL-4059 was that migrations 032 / 033 / 036 hid CREATE INDEX inside
-- `DO $$ ... EXCEPTION WHEN OTHERS $$` blocks, so on any environment
-- where pg_bigm was absent the migration "succeeded" while quietly
-- creating no indexes at all — the exact silent-skip pattern that took
-- prd search down. This index is the critical support for the fix, not
-- an optional CJK bonus, so a real failure (disk full, permission denied,
-- schema drift) MUST abort the migration and fail
-- deployment, not slip through as a green success. CONCURRENTLY avoids
-- blocking writes on the hot comment table while the index builds; this
-- file must stay single-statement because Postgres rejects CREATE INDEX
-- CONCURRENTLY in a transaction or multi-command string.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_comment_workspace
    ON comment (workspace_id);

```

## server/go/migrations/136_runtime_profile_add_traecli.up.sql

```sql
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

-- Widen the whitelist to include Trae (`traecli`). Trae already has a New()
-- backend, launch header (`traecli acp serve`) and provider branding, but was
-- missing from the protocol_family whitelist, so custom runtime profiles based
-- on Trae were rejected and it never appeared in the family picker (#4945).
-- NOT VALID mirrors migrations 126/134 so a historical Gemini row they
-- intentionally tolerated does not block the upgrade.
ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'kiro',
        'antigravity',
        'qoder',
        'traecli'
    )) NOT VALID;

```

## server/go/migrations/137_search_index_pg_trgm_extension.up.sql

```sql
-- Install pg_trgm for the fallback trigram search indexes added in the next
-- migrations. Keep this separate from CREATE INDEX CONCURRENTLY files:
-- Postgres rejects concurrent index builds in a multi-statement migration.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

```

## server/go/migrations/138_issue_title_trgm_index.up.sql

```sql
-- Fallback GIN index for SearchIssues title LIKE matches when pg_bigm is not
-- available. This must stay as a single-statement migration because CREATE
-- INDEX CONCURRENTLY cannot run inside a transaction or multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_title_trgm
    ON issue USING gin (LOWER(title) gin_trgm_ops);

```

## server/go/migrations/139_issue_description_trgm_index.up.sql

```sql
-- Fallback GIN index for SearchIssues description LIKE matches when pg_bigm is
-- not available. Single-statement file required for CREATE INDEX CONCURRENTLY.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_description_trgm
    ON issue USING gin (LOWER(COALESCE(description, '')) gin_trgm_ops);

```

## server/go/migrations/140_comment_content_trgm_index.up.sql

```sql
-- Fallback GIN index for SearchIssues comment content LIKE matches when
-- pg_bigm is not available. Single-statement file required for CREATE INDEX
-- CONCURRENTLY.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_comment_content_trgm
    ON comment USING gin (LOWER(content) gin_trgm_ops);

```

## server/go/migrations/141_project_title_trgm_index.up.sql

```sql
-- Fallback GIN index for SearchProjects title LIKE matches when pg_bigm is not
-- available. Single-statement file required for CREATE INDEX CONCURRENTLY.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_project_title_trgm
    ON project USING gin (LOWER(title) gin_trgm_ops);

```

## server/go/migrations/142_project_description_trgm_index.up.sql

```sql
-- Fallback GIN index for SearchProjects description LIKE matches when pg_bigm
-- is not available. Single-statement file required for CREATE INDEX
-- CONCURRENTLY.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_project_description_trgm
    ON project USING gin (LOWER(COALESCE(description, '')) gin_trgm_ops);

```

## server/go/migrations/143_agent_task_queue_chat_pending_v2.up.sql

```sql
-- Fix a partial-index predicate mismatch on agent_task_queue (MUL-4159).
--
-- Migration 040 created idx_agent_task_queue_chat_pending with the predicate
-- `status IN ('queued', 'dispatched', 'running')`. Migration 109 later added a
-- fourth in-flight status, `waiting_local_directory`, and both pending chat
-- queries (GetPendingChatTask, ListPendingChatTasksByCreator) now filter on all
-- four statuses. Postgres only uses a partial index when it can prove the query
-- predicate is a subset of the index predicate; the extra status made the old
-- index an unusable candidate, so those queries degraded to a Seq Scan on
-- agent_task_queue (or a non-optimal FK path), which is the root cause of the
-- high DB load on this path.
--
-- This v2 index restores index coverage by including all four in-flight
-- statuses. The column list (chat_session_id, created_at DESC) is unchanged so
-- it keeps serving the single-session GetPendingChatTask lookup as well.
--
-- The old index is dropped in a separate migration (144) after this one has
-- built and been verified in EXPLAIN, per the repo convention of never mixing
-- multiple CONCURRENTLY statements in one migration. This file must stay
-- single-statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_chat_pending_v2
    ON agent_task_queue (chat_session_id, created_at DESC)
    WHERE chat_session_id IS NOT NULL
      AND status IN ('queued', 'dispatched', 'running', 'waiting_local_directory');

```

## server/go/migrations/144_drop_agent_task_queue_chat_pending_v1.up.sql

```sql
-- Drop the superseded partial index from migration 040 (MUL-4159).
--
-- idx_agent_task_queue_chat_pending_v2 (migration 143) covers all four
-- in-flight statuses and the same (chat_session_id, created_at DESC) column
-- list, so it fully serves both GetPendingChatTask and
-- ListPendingChatTasksByCreator. The old three-status index is now dead weight
-- on the write path and can be removed once 143 is verified via EXPLAIN.
--
-- Split into its own migration so this file holds a single CONCURRENTLY
-- statement (repo convention); CREATE/DROP INDEX CONCURRENTLY cannot run inside
-- a transaction or multi-command string.
DROP INDEX CONCURRENTLY IF EXISTS idx_agent_task_queue_chat_pending;

```

## server/go/migrations/145_agent_runtime_custom_name.up.sql

```sql
-- Adds an optional user-facing custom name for a runtime (MUL-4217).
-- custom_name overrides the daemon-proposed `name` for display only; NULL
-- falls back to `name`. Deliberately NOT written by the registration /
-- heartbeat upserts (which do name = EXCLUDED.name on every beat), so a
-- user's custom name is never clobbered by the daemon.
--
-- No index: the column is only ever read as part of a full-row runtime fetch
-- and never appears in a WHERE / ORDER BY, so it needs none. Adding a
-- nullable column with no default is a fast catalog-only change.
ALTER TABLE agent_runtime ADD COLUMN custom_name TEXT;

```

## server/go/migrations/149_issue_origin_agent_create.up.sql

```sql
-- Extend issue.origin_type to allow an agent's ordinary `issue create` to stamp
-- the new issue with origin_type='agent_create' + origin_id=<agent_task_queue.id>
-- (the acting task that created it). This is the load-bearing link that lets
-- resolveOriginatorForIssueTask inherit the top-of-chain human originator for
-- any run derived from the new issue (assignment / squad-leader). Without it an
-- agent-created issue was left unattributed, so downstream A2A mentions from
-- those runs failed the canInvokeAgent gate against private agents (MUL-4305).
-- Mirrors the quick_create link (060) — same origin_id semantics (an
-- agent_task_queue row), different label because this is the normal create path
-- rather than the daemon quick-create flow.
ALTER TABLE issue DROP CONSTRAINT IF EXISTS issue_origin_type_check;
ALTER TABLE issue ADD CONSTRAINT issue_origin_type_check
    CHECK (origin_type IN ('autopilot', 'quick_create', 'lark_chat', 'slack_chat', 'agent_create'));

```

## server/go/migrations/150_agent_task_coalesced_comments.up.sql

```sql
-- Guarantee at-least-once processing of user comments (MUL-4195).
--
-- Historically a new comment that arrived while an agent already had a
-- queued/dispatched task for the same (issue, agent) was silently DROPPED by
-- the HasPendingTaskForIssueAndAgent dedup: only the first comment's
-- trigger_comment_id survived, and the follow-up instruction was lost with no
-- visible trace. That is a correctness bug for comments, which — unlike chat —
-- are deliberate, addressed, persisted user input that must never vanish.
--
-- coalesced_comment_ids records the comments that were FOLDED INTO a
-- not-yet-started task instead of being dropped. The task's trigger_comment_id
-- is repointed to the newest comment (so the injected prompt shows the latest
-- deliberate instruction) while this array preserves every earlier comment the
-- single run must still address. It is also surfaced on the task API so the UI
-- can show exactly which comments a run covered.
--
-- Default '{}' (empty array, never NULL) so existing rows and every non-merge
-- enqueue path keep working untouched.
ALTER TABLE agent_task_queue
    ADD COLUMN IF NOT EXISTS coalesced_comment_ids UUID[] NOT NULL DEFAULT '{}';

```

## server/go/migrations/151_chat_read_cursor.up.sql

```sql
-- IM-style unread: keep the old `unread_since` flag for rolling deploy /
-- rollback compatibility while adding a read cursor `last_read_at`. Unread is
-- now derived as the *count* of assistant messages after the cursor, so the chat
-- list can show a real number (like an IM conversation) instead of a single dot.
ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS unread_since TIMESTAMPTZ;
ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS last_read_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Preserve existing unread state during the switch: a session currently flagged
-- unread gets its cursor placed just before the first unread reply, so those
-- messages still count. `unread_since` is the arrival time of the first unread
-- assistant message.
UPDATE chat_session
   SET last_read_at = unread_since - interval '1 microsecond'
 WHERE unread_since IS NOT NULL;

```

## server/go/migrations/152_chat_pinned_agent.up.sql

```sql
-- Per-user "quick agent" pins for the Chat list: a curated, ordered set of
-- agents the user keeps at the top of the conversation list for one-tap new
-- chats. Kept separate from the generic `pinned_item` table (issues/projects)
-- so it doesn't leak into the sidebar's pinned section.
CREATE TABLE IF NOT EXISTS chat_pinned_agent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    user_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    position FLOAT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, user_id, agent_id)
);

ALTER TABLE chat_pinned_agent
    DROP CONSTRAINT IF EXISTS chat_pinned_agent_workspace_id_fkey,
    DROP CONSTRAINT IF EXISTS chat_pinned_agent_user_id_fkey,
    DROP CONSTRAINT IF EXISTS chat_pinned_agent_agent_id_fkey;

```

## server/go/migrations/153_chat_pinned_agent_user_ws_index.up.sql

```sql
-- Single-statement migration: CREATE INDEX CONCURRENTLY cannot run inside a
-- transaction or a multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_pinned_agent_user_ws
    ON chat_pinned_agent (workspace_id, user_id, position);

```

## server/go/migrations/154_chat_agent_intro.up.sql

```sql
-- Flags a chat_session auto-created when its agent was created, so its first
-- turn is a proactive self-introduction from the agent. Such a session carries
-- NO visible user message: the intro run is driven server-side (see the chat
-- prompt in server/go/internal/daemon/prompt.go) so the thread reads as the agent
-- messaging its creator first, not the creator prompting the agent.
ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS is_agent_intro BOOLEAN NOT NULL DEFAULT FALSE;

```

## server/go/migrations/155_chat_session_pinned.up.sql

```sql
-- Per-conversation pin for the Chat list: a user can pin a chat so it stays
-- at the top of their conversation list, above the activity-sorted rest.
-- `pinned_at` doubles as the sort key within the pinned group (most-recently
-- pinned first) and as the boolean flag (NULL = not pinned). Sessions are
-- already per-creator, so no extra user dimension is needed.
ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS pinned_at TIMESTAMPTZ;

```

## server/go/migrations/156_chat_session_pinned_index.up.sql

```sql
-- Partial index over pinned rows only: the pinned group is small, and the list
-- query orders by pinned_at within a single (workspace, creator) scan.
--
-- Single-statement migration: CREATE INDEX CONCURRENTLY cannot run inside a
-- transaction or a multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_session_pinned
    ON chat_session (creator_id, workspace_id, pinned_at DESC)
    WHERE pinned_at IS NOT NULL;

```

## server/go/migrations/157_agent_task_delivered_comments.up.sql

```sql
-- Record the comment ids that were actually embedded in a daemon claim.
--
-- coalesced_comment_ids is the enqueue plan, not proof of delivery: daemons
-- predating coalesced-comments-v1 ignore the structured fields. Keeping a
-- separate delivered set lets completion reconciliation replay every comment
-- that the claiming daemon did not receive.
ALTER TABLE agent_task_queue
    ADD COLUMN IF NOT EXISTS delivered_comment_ids UUID[] NOT NULL DEFAULT '{}';

-- Active tasks created before this migration always received their primary
-- trigger through trigger_comment_content. We deliberately do not backfill
-- coalesced ids: an older daemon may have ignored them, and a duplicate replay
-- is safer than silently losing a deliberate instruction.
UPDATE agent_task_queue
SET delivered_comment_ids = ARRAY[trigger_comment_id]
WHERE trigger_comment_id IS NOT NULL
  AND status IN ('dispatched', 'running', 'waiting_local_directory');

```

## server/go/migrations/158_agent_task_queue_chat_input_task_id.up.sql

```sql
-- Direct-chat input ownership (MUL-4351).
--
-- chat_input_task_id makes each web/mobile direct-chat task the immutable owner
-- of the user-message batch it must consume. A fresh direct-send task sets this
-- to its own id in the same transaction that creates the user message
-- (chat_message.task_id = task.id), so a later claim loads exactly that batch
-- instead of scanning "trailing user messages after the last assistant row".
--
-- An auto-retry child inherits its parent's chat_input_task_id, so the whole
-- retry chain keeps consuming the original root input batch and never re-reads
-- a message that arrived after the batch was sealed.
--
-- NULL means "legacy row or channel (Slack/Lark) task": those keep using the
-- trailing-message selector, so a rolling deploy never replays channel history
-- and pre-migration direct rows behave exactly as before. No FK / cascade — the
-- application layer owns this reference, matching the repo's no-FK rule.
ALTER TABLE agent_task_queue ADD COLUMN IF NOT EXISTS chat_input_task_id UUID;

```

## server/go/migrations/159_chat_message_message_kind.up.sql

```sql
-- Explicit terminal outcome kind for chat messages (MUL-4351).
--
-- 'message'      — an ordinary user/assistant message (the default; every
--                  existing row and every legacy client sees this).
-- 'no_response'  — the agent completed a direct-chat turn without any text
--                  reply. This is a visible, deliberate terminal outcome: the
--                  turn boundary is now owned by chat_input_task_id, not by the
--                  presence of an assistant row, so we no longer need to fake a
--                  blank bubble to advance the conversation. The frontend
--                  renders a localized "no text reply this turn" state while old
--                  clients fall back to the non-empty English content we still
--                  store on the row.
--
-- Additive and app-validated: no CHECK constraint / FK / cascade so new kinds
-- can be introduced without a migration and unknown values degrade to 'message'
-- on older readers.
ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS message_kind TEXT NOT NULL DEFAULT 'message';

```

## server/go/migrations/160_chat_message_input_owner_index.up.sql

```sql
-- Index the task-owned input-batch lookup added in MUL-4351.
--
-- The direct-chat claim path loads its input with
--   SELECT * FROM chat_message WHERE task_id = $1 AND role = 'user' ORDER BY created_at
-- (ListChatInputMessages), keyed on the task's chat_input_task_id. Before this
-- there was no index on chat_message.task_id at all (only the
-- chat_session_id/created_at index from migration 033), so the lookup would seq
-- scan. This partial index covers exactly the user-message batch reads and the
-- existing task_id-keyed writes (LinkChatMessageToTask,
-- DeleteUserChatMessageByTask) without indexing assistant rows.
--
-- Single-statement migration: CREATE INDEX CONCURRENTLY cannot run inside a
-- transaction or a multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_message_input_owner
    ON chat_message (task_id, created_at)
    WHERE role = 'user';

```

## server/go/migrations/161_agent_skill_enabled.up.sql

```sql
ALTER TABLE agent_skill
ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT TRUE;

```

## server/go/migrations/162_resource_labels.up.sql

```sql
-- Generalise the existing issue-label catalog into three independent
-- workspace namespaces. Existing rows remain issue labels; agent and skill
-- labels use the same management primitives without sharing vocabulary.

ALTER TABLE issue_label
    ADD COLUMN resource_type TEXT NOT NULL DEFAULT 'issue'
        CHECK (resource_type IN ('issue', 'agent', 'skill')),
    ADD COLUMN description TEXT NOT NULL DEFAULT '';

CREATE TABLE agent_to_label (
    agent_id UUID NOT NULL,
    label_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (agent_id, label_id)
);

CREATE TABLE skill_to_label (
    skill_id UUID NOT NULL,
    label_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (skill_id, label_id)
);

```

## server/go/migrations/163_agent_builder.up.sql

```sql
ALTER TABLE agent
ADD COLUMN kind TEXT NOT NULL DEFAULT 'user'
    CHECK (kind IN ('user', 'system')),
ADD COLUMN system_key TEXT;

```

## server/go/migrations/164_attachment_task_id.up.sql

```sql
-- Task-scoped attachment ownership. An agent producing an image/file for a
-- chat reply uploads it during the run tagged with the producing task; on task
-- completion the server binds the task's still-unclaimed rows to the assistant
-- chat_message it synthesizes (see BindChatAttachmentsToMessage).
--
-- task_id is a TRANSIENT binding handle, not a durable relationship: it is
-- written once at upload (against a task the upload handler has already
-- validated) and read only during that task's own completion. The durable
-- owner is chat_message_id. We deliberately add NO foreign key here:
--   - No referential integrity is needed — the sole writer validates the task
--     before setting the column, so a dangling/garbage value cannot get in.
--   - No cascade cleanup is needed — orphan uploads (task_id set,
--     chat_message_id NULL) are already reaped when their chat_session is
--     deleted, via attachment.chat_session_id's own ON DELETE CASCADE. There is
--     no app-layer path that hard-deletes agent_task_queue rows, so an
--     ON DELETE action here would never fire in practice; adding an FK on the
--     hot attachment table would only add write overhead and a cascade
--     dependency the app does not rely on.
-- IF NOT EXISTS makes this self-heal on databases that applied it under its
-- pre-#5307 number (161). The renumber to 164 changed the schema_migrations
-- key, so the runner re-applies the renamed file on those DBs; without the
-- guard the bare ADD COLUMN aborts with 42701 ("column already exists") and
-- blocks every later migration (GH #5307's note; the dev deploy that hit it).
-- Sibling 165 already uses CREATE INDEX ... IF NOT EXISTS for the same reason.
ALTER TABLE attachment
  ADD COLUMN IF NOT EXISTS task_id UUID;

-- The task_id lookup index is built CONCURRENTLY in the next migration.
-- CREATE INDEX CONCURRENTLY cannot share a transaction or multi-command
-- string with the ADD COLUMN above (see 138_issue_title_trgm_index).

```

## server/go/migrations/165_attachment_task_id_index.up.sql

```sql
-- Lookup index for BindChatAttachmentsToMessage (find a task's still-unbound
-- rows on chat-task completion). Single-statement + CONCURRENTLY: CREATE INDEX
-- CONCURRENTLY cannot run in a transaction or multi-command string (see
-- 138_issue_title_trgm_index). Partial on task_id IS NOT NULL — only in-flight,
-- not-yet-bound uploads qualify, so the index stays tiny.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_attachment_task
  ON attachment(task_id)
  WHERE task_id IS NOT NULL;

```

## server/go/migrations/166_project_dates.up.sql

```sql
-- Project start_date / due_date make a Project a schedulable planning object
-- alongside its issues: a planned start plus a deadline. These mirror
-- issue.start_date / issue.due_date after migration 112 — calendar days stored
-- as DATE, carrying no time-of-day or timezone, so "Mar 1" means Mar 1 for
-- every viewer regardless of their local offset (see GH #3618 / MUL-2925).
-- Backs MUL-4388 / GH #5227. Nullable, no default: adding a nullable column is
-- a metadata-only change with no table rewrite.
ALTER TABLE project
    ADD COLUMN start_date DATE,
    ADD COLUMN due_date DATE;

```

## server/go/migrations/167_resource_label_namespace_index.up.sql

```sql
-- This is intentionally a single statement: concurrent index creation cannot
-- run in a transaction or a multi-command migration.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS issue_label_workspace_type_name_lower_idx
    ON issue_label (workspace_id, resource_type, LOWER(name));

```

## server/go/migrations/168_resource_label_type_index.up.sql

```sql
-- This is intentionally a single statement: concurrent index creation cannot
-- run in a transaction or a multi-command migration.
CREATE INDEX CONCURRENTLY IF NOT EXISTS issue_label_workspace_type_idx
    ON issue_label (workspace_id, resource_type);

```

## server/go/migrations/169_agent_label_lookup_index.up.sql

```sql
-- This is intentionally a single statement: concurrent index creation cannot
-- run in a transaction or a multi-command migration.
CREATE INDEX CONCURRENTLY IF NOT EXISTS agent_to_label_label_idx
    ON agent_to_label(label_id);

```

## server/go/migrations/170_skill_label_lookup_index.up.sql

```sql
-- This is intentionally a single statement: concurrent index creation cannot
-- run in a transaction or a multi-command migration.
CREATE INDEX CONCURRENTLY IF NOT EXISTS skill_to_label_label_idx
    ON skill_to_label(label_id);

```

## server/go/migrations/171_drop_legacy_label_namespace_index.up.sql

```sql
-- The replacement namespace index is created in migration 167 before this
-- legacy index is removed. Keep this a single statement for online safety.
DROP INDEX CONCURRENTLY IF EXISTS issue_label_workspace_name_lower_idx;

```

## server/go/migrations/172_agent_system_identity_index.up.sql

```sql
-- This is intentionally a single statement: concurrent index creation cannot
-- run in a transaction or a multi-command migration.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS agent_system_identity_unique
    ON agent (workspace_id, owner_id, runtime_id, system_key)
    WHERE system_key IS NOT NULL;

```

## server/go/migrations/173_remove_resource_label_foreign_keys.up.sql

```sql
-- A short-lived pre-release deployment may already have applied the original
-- migration 162. Remove those database cascades before this release enables
-- resource labels; application transactions own cleanup from this point on.
ALTER TABLE agent_to_label DROP CONSTRAINT IF EXISTS agent_to_label_agent_id_fkey;
ALTER TABLE agent_to_label DROP CONSTRAINT IF EXISTS agent_to_label_label_id_fkey;
ALTER TABLE skill_to_label DROP CONSTRAINT IF EXISTS skill_to_label_skill_id_fkey;
ALTER TABLE skill_to_label DROP CONSTRAINT IF EXISTS skill_to_label_label_id_fkey;

```

## server/go/migrations/174_legacy_label_index_rollback_prep.up.sql

```sql
-- Forward no-op. This migration exists only to sequence a rollback step:
-- its down removes the agent/skill rows from issue_label before 171.down
-- rebuilds the workspace-wide unique name index. Because down migrations
-- apply high->low, keeping this delete in the highest-numbered resource
-- label migration guarantees the non-issue rows are gone before both
-- 171.down (index rebuild) and 162.down (drops resource_type). There is
-- nothing to do on the way up.
SELECT 1;

```

## server/go/migrations/175_runtime_profile_add_deveco.up.sql

```sql
-- Add 'deveco' (DevEco Code, Huawei's coding agent for HarmonyOS, built on the
-- OpenCode engine) to the runtime_profile protocol_family whitelist. Mirrors the
-- drop/re-add NOT VALID pattern from migrations 126/134/136 so historical rows
-- are not revalidated. Kept in lockstep with agent.SupportedTypes and agent.New()
-- (see server/go/pkg/agent/agent.go).
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'kiro',
        'antigravity',
        'qoder',
        'traecli',
        'deveco'
    )) NOT VALID;

```

## server/go/migrations/176_webhook_delivery_worker.up.sql

```sql
-- Durable webhook dispatch state. The HTTP handler only admits the delivery;
-- a database-leased worker owns downstream autopilot dispatch.
--
-- Keep the idempotency anchor deliberately free of a foreign key. The code
-- already validates the referenced delivery, while avoiding a new FK keeps
-- deploys and rollback independent of existing webhook_delivery cascades.
ALTER TABLE webhook_delivery
    ADD COLUMN IF NOT EXISTS available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS lease_token UUID,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dispatch_attempts INTEGER NOT NULL DEFAULT 0;

ALTER TABLE autopilot_run
    ADD COLUMN IF NOT EXISTS webhook_delivery_id UUID;

```

## server/go/migrations/177_autopilot_run_webhook_delivery_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_autopilot_run_webhook_delivery
    ON autopilot_run(webhook_delivery_id)
    WHERE webhook_delivery_id IS NOT NULL;

```

## server/go/migrations/178_webhook_delivery_queue_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_delivery_queue
    ON webhook_delivery(available_at, created_at)
    WHERE status = 'queued';

```

## server/go/migrations/179_runtime_profile_add_grok.up.sql

```sql
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

-- Widen the whitelist to include Grok Build CLI (`grok`), driven over ACP via
-- `grok agent --always-approve stdio` (#2895). Builds on migration 175's shape
-- (which added `deveco`), so both stay in the whitelist. NOT VALID mirrors
-- migrations 126/134/136/175 so a historical Gemini row they intentionally
-- tolerated does not block the upgrade.
ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'kiro',
        'antigravity',
        'qoder',
        'traecli',
        'deveco',
        'grok'
    )) NOT VALID;

```

## server/go/migrations/180_task_chat_finalize_deferred.up.sql

```sql
-- #5219: cancellation-time chat finalization can race the daemon's transcript
-- flush. When a started chat task is cancelled while its transcript is still
-- empty, the empty/non-empty judgment is deferred until the daemon acks its
-- flush (or a sweeper grace period expires). This column is both the pending
-- marker and the grace-period clock; clearing it doubles as the atomic claim
-- that keeps the ack path and the sweeper from finalizing the same task twice.
--
-- The sweeper index lives in migration 181: agent_task_queue is a hot table,
-- so the index build must run CONCURRENTLY in its own single-statement file.
ALTER TABLE agent_task_queue ADD COLUMN IF NOT EXISTS chat_finalize_deferred_at TIMESTAMPTZ;

```

## server/go/migrations/181_task_chat_finalize_deferred_index.up.sql

```sql
-- Partial index over pending deferred finalizations only: the sweeper scans
-- for rows past the grace period, and the pending set is tiny (cancelled
-- started-but-empty chat tasks awaiting a daemon ack).
--
-- Single-statement migration: CREATE INDEX CONCURRENTLY cannot run inside a
-- transaction or a multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_chat_finalize_deferred
    ON agent_task_queue (chat_finalize_deferred_at)
    WHERE chat_finalize_deferred_at IS NOT NULL;

```

## server/go/migrations/182_chat_draft_restore.up.sql

```sql
-- Durable draft restore for deferred cancellations (#5219). When a cancelled
-- chat task's transcript settles as empty, the triggering user message is
-- deleted and its content must return to the creator's composer. The
-- chat:cancel_finalized broadcast is best-effort, so the restore is persisted
-- here and served by a creator-authorized endpoint: a client that was offline
-- across the event fetches it on the next session open and consumes it
-- (DELETE) once applied.
--
-- No foreign keys: new tables enforce their relationships in the application
-- layer (MUL-3515). DeleteChatSession prunes this table inside its transaction,
-- alongside the channel_* tables it already prunes there.
--
-- id is the deleted user chat message's id: globally unique (it was a
-- chat_message PK), stable for client-side dedup, and one restore per task is
-- guaranteed by the atomic deferred-finalize claim.
--
-- The chat_session_id lookup index lives in migration 183: every production
-- index is built CONCURRENTLY in its own single-statement file.
CREATE TABLE chat_draft_restore (
    id              UUID PRIMARY KEY,
    chat_session_id UUID NOT NULL,
    task_id         UUID NOT NULL,
    content         TEXT NOT NULL,
    -- Detached attachment rows the restored draft re-binds; resolved to full
    -- attachment responses (URL policy included) at read time.
    attachment_ids  UUID[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/183_chat_draft_restore_index.up.sql

```sql
-- Lookup index for chat_draft_restore.chat_session_id: the creator-authorized
-- read (ListChatDraftRestoresBySession) and the DeleteChatSession / workspace /
-- runtime cascade-path prunes all filter by chat_session_id.
--
-- Single-statement migration: CREATE INDEX CONCURRENTLY cannot run inside a
-- transaction or a multi-command string. Split from the table in migration 182
-- so every production index build runs CONCURRENTLY.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_draft_restore_session
    ON chat_draft_restore (chat_session_id);

```

## server/go/migrations/184_agent_task_attribution.up.sql

```sql
-- Human Attribution, Phase 1 foundation (MUL-4302, parent MUL-4274; upstream
-- discussion GH #5108). Every agent run must be traceable to exactly one
-- accountable human, and that attribution must be EXPLAINABLE: a report has to
-- state not just WHO but at WHICH waterfall level the human was resolved
-- (direct action, delegation copy, comment-source chain, autopilot rule owner,
-- or degraded owner fallback). Today agent_task_queue.originator_user_id records
-- the human but carries no provenance — a NULL originator could equally mean
-- "autopilot" or "we failed to resolve a human who exists", and the two must be
-- distinguishable for the compliance/coverage story.
--
-- This migration adds the provenance + lineage columns that the Attribution
-- Resolver stamps at enqueue time. It deliberately does NOT change the value or
-- semantics of originator_user_id, which feeds authorization decisions
-- (canInvokeAgent A2A gate, Composio overlay history) — per the design axiom
-- "attribution is on-behalf-of, never blame and never authorization"
-- (MUL-4302 §1.3). These columns are audit/visibility metadata only.
--
-- Constraints honored (MUL-4302 §7 + workspace DB rules): NO foreign keys, NO
-- cascades (integrity is resolved in the application layer), and NO CHECK
-- constraint on the source enum so that a newly-modeled trigger path can add a
-- source label without a schema migration. All columns are nullable with no
-- default so the ALTER is a fast metadata-only change on the hot queue table
-- (no table rewrite, no long lock).

-- originator_source: which waterfall level resolved originator_user_id for this
-- run. One of: 'direct_human', 'delegation', 'comment_source', 'rule_owner',
-- 'owner_fallback', 'backfill', 'unattributed'. TEXT with no CHECK on purpose
-- (see header). NULL only on rows that predate this migration.
ALTER TABLE agent_task_queue
    ADD COLUMN originator_source TEXT NULL;

COMMENT ON COLUMN agent_task_queue.originator_source IS
    'Waterfall level that resolved originator_user_id for this run: direct_human | delegation | comment_source | rule_owner | owner_fallback | backfill | unattributed. Audit/visibility metadata only — never consulted for authorization. TEXT with no CHECK so new trigger paths can add a source without a migration (MUL-4302 §7). NULL on pre-migration rows.';

-- delegated_from_task_id: for source='delegation', the parent task whose
-- accountable human was COPIED onto this run (agent A @-mentions agent B, or an
-- agent creates a sub-issue). The chain root stays stable and copying the value
-- (not walking the chain) keeps delegation cycles harmless (MUL-4302 §3.2).
-- No FK by design; a stale id degrades to "evidence not resolvable", never a
-- corrupt run.
ALTER TABLE agent_task_queue
    ADD COLUMN delegated_from_task_id UUID NULL;

COMMENT ON COLUMN agent_task_queue.delegated_from_task_id IS
    'For originator_source=delegation: the parent task whose accountable human was copied onto this run. Value is copied, not chained, so delegation cycles are harmless (MUL-4302 §3.2). No FK; app-layer integrity only.';

-- retry_of_task_id / rerun_of_task_id: the design requires retry and rerun to be
-- kept strictly apart in reporting (MUL-4302 §5). parent_task_id already links
-- system auto-retries, but it is overloaded and does not distinguish the two.
--   * retry_of_task_id — system transient-failure retry; INHERITS the parent's
--     attribution unchanged (not a new attribution event).
--   * rerun_of_task_id — human manual rerun of a historical task; a NEW
--     direct_human attribution to the person who clicked rerun, with lineage
--     preserved back to the original task.
-- Both no-FK, nullable.
ALTER TABLE agent_task_queue
    ADD COLUMN retry_of_task_id UUID NULL;

COMMENT ON COLUMN agent_task_queue.retry_of_task_id IS
    'System transient-failure retry lineage: the task this run re-attempts. Inherits the parent attribution unchanged. Kept distinct from rerun_of_task_id so retry vs rerun report separately (MUL-4302 §5). No FK.';

ALTER TABLE agent_task_queue
    ADD COLUMN rerun_of_task_id UUID NULL;

COMMENT ON COLUMN agent_task_queue.rerun_of_task_id IS
    'Human manual-rerun lineage: the historical task a member re-ran. The rerun itself is a NEW direct_human attribution to the rerunning member; this column preserves the link to the original (MUL-4302 §5). No FK.';

-- rule_version_id: for source='rule_owner', the published autopilot rule version
-- whose publisher is the accountable human. The rule-version snapshot table and
-- its wiring land in a later Phase 1 increment; the column ships now so the
-- resolver contract and the queue schema are stable. No FK, nullable.
ALTER TABLE agent_task_queue
    ADD COLUMN rule_version_id UUID NULL;

COMMENT ON COLUMN agent_task_queue.rule_version_id IS
    'For originator_source=rule_owner: the published autopilot rule version snapshot whose publisher is the accountable human. No FK; snapshot table wiring lands in a later Phase 1 increment (MUL-4302 §3.4/§7).';

-- trigger_evidence_kind / trigger_evidence_ref_id: the direct cause of the run,
-- so every attribution can jump to its evidence (which comment, which assign,
-- which rule version, which external event). kind is a free TEXT tag
-- ('comment' | 'issue_assignment' | 'autopilot_run' | 'rule_version' | 'rerun'
-- | ...); ref_id points at that row. trigger_comment_id / autopilot_run_id
-- still exist for their existing consumers — this pair is the uniform,
-- kind-tagged evidence handle the attribution UI will link from (MUL-4302 §2).
ALTER TABLE agent_task_queue
    ADD COLUMN trigger_evidence_kind TEXT NULL;

COMMENT ON COLUMN agent_task_queue.trigger_evidence_kind IS
    'Uniform kind tag for the direct cause of this run (comment | issue_assignment | autopilot_run | rule_version | rerun | ...), paired with trigger_evidence_ref_id. Free TEXT so new evidence kinds need no migration (MUL-4302 §2).';

ALTER TABLE agent_task_queue
    ADD COLUMN trigger_evidence_ref_id UUID NULL;

COMMENT ON COLUMN agent_task_queue.trigger_evidence_ref_id IS
    'The row id referenced by trigger_evidence_kind (a comment id, autopilot_run id, rule_version id, source task id, ...). No FK; resolvable per-kind in the app layer (MUL-4302 §2).';

```

## server/go/migrations/185_agent_task_accountable_user.up.sql

```sql
-- Human Attribution, Phase 1 — split the accountable human off originator_user_id
-- (MUL-4302, decided by Bohan on the MUL-4302 thread).
--
-- Migration 184 stamped provenance (originator_source, evidence, lineage) ONTO
-- originator_user_id, treating that one column as both "who authorized this run"
-- and "who is accountable for it". Those are two different questions with two
-- different lifetimes, and collapsing them onto one column is a latent hazard:
--
--   * originator_user_id is an AUTHORIZATION input. canInvokeAgent (the A2A gate)
--     and the Composio overlay read it to decide "whose permission is this run
--     acting under". It is legitimately NULL when no human lent their authority
--     (autopilot schedule/webhook, or a chain that resolves to no human). NULL is
--     the authorization system's only way to say "this run carries no human
--     permission" — the owner-can-invoke-own-agent branch in canInvokeAgent means
--     that forging a non-NULL owner here would turn every unresolved run into a
--     fully-privileged one (fail-open). So this column must stay unforgeable.
--
--   * accountable_user_id is an AUDIT / visibility / cost output. The design axiom
--     (MUL-4302 §1) requires it to be resolvable for every run, degrading to the
--     rule publisher (rule_owner) or agent owner (owner_fallback) when no human is
--     in the trigger chain. Its "never NULL for a precise attribution" property is
--     descriptive (a best-effort label), never a grant of permission.
--
-- This migration adds the dedicated audit column. Authorization continues to read
-- ONLY originator_user_id; audit / UI / usage read accountable_user_id + source +
-- evidence. The one-way invariant the resolver enforces and §11 tests:
--
--     originator_user_id IS NOT NULL  ⟹  accountable_user_id = originator_user_id
--
-- Divergence happens only when originator_user_id IS NULL (no human authorized the
-- run) — there the audit side may still name a degraded accountable human while
-- authorization correctly says "no one". Wiring the divergent sources (rule_owner,
-- owner_fallback) is a later Phase 1 increment; this migration lands the column and
-- the mirror-write so that split has a home without ever touching the authz path.
--
-- Constraints (MUL-4302 §7 + workspace DB rules): NO foreign key, NO cascade
-- (integrity is resolved in the application layer). Nullable with no default so the
-- ALTER is a fast metadata-only change on the hot queue table (no rewrite, no long
-- lock).
--
-- NULL does NOT mean "pre-migration row" here. Unlike originator_source (which
-- every new enqueue path now stamps non-NULL, migration 184), accountable_user_id
-- is legitimately NULL on NEW rows too, whenever the row's audit source resolved
-- no human yet: run_only autopilot writes originator_source='unattributed' with a
-- NULL accountable until rule_owner lands, and any classified-unattributed path is
-- the same. So NULL means "no accountable human resolved" — a pre-migration row OR
-- a new not-yet-resolved / unattributed audit source — and readers must NOT treat
-- NULL as pre-migration-only when reasoning about the invariant.
ALTER TABLE agent_task_queue
    ADD COLUMN accountable_user_id UUID NULL;

COMMENT ON COLUMN agent_task_queue.accountable_user_id IS
    'The one human accountable for this run, for audit / visibility / cost only — NEVER consulted for authorization (that is originator_user_id). Invariant: when originator_user_id IS NOT NULL, this equals it; the two diverge only when originator_user_id IS NULL (autopilot rule_owner / degraded owner_fallback name an accountable human while authorization carries none). No FK, no cascade (MUL-4302 §1/§7). NULL means no accountable human was resolved: a pre-migration row, OR a NEW row whose audit source is not-yet-resolved / unattributed (e.g. run_only autopilot until rule_owner lands) — NOT pre-migration only.';

```

## server/go/migrations/186_autopilot_rule_version.up.sql

```sql
-- Human Attribution, Phase 1 — autopilot rule_owner snapshot table (MUL-4302 §3.4/§7).
--
-- An autopilot trigger (schedule / webhook / manual) enqueues a run that NO human
-- authorized in the moment, so its authorization originator_user_id stays NULL. But
-- the run is still accountable to a human for audit / cost: the member who last
-- PUBLISHED the rule that fired it. "Publish" = a substantive action (create, enable,
-- resume, or a change to the trigger condition / execution target / task
-- instructions); cosmetic edits (rename, description) do NOT transfer accountability.
--
-- Each substantive publish appends one immutable row here, recording who published
-- and a summary of the effective config at that moment. At dispatch time the resolver
-- reads the autopilot's ACTIVE (latest) version and stamps the run:
-- originator_source='rule_owner', accountable_user_id=published_by_id, and
-- agent_task_queue.rule_version_id=<this row>. Authorization is untouched — this is
-- the audit side of the accountable/originator split.
--
-- Immutable + append-only: a new publish never UPDATEs a prior row, so a run's
-- rule_version_id always resolves to the exact config/publisher that was live when it
-- fired, even after the rule is later re-published or the publisher leaves.
--
-- Constraints (MUL-4302 §7 + workspace DB rules): NO foreign key, NO cascade —
-- integrity is resolved in the application layer. published_by_id is nullable
-- (system-published rules have no member); a NULL publisher degrades the run to
-- 'unattributed' rather than fabricating a human.
CREATE TABLE IF NOT EXISTS autopilot_rule_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    autopilot_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    published_by_type TEXT NOT NULL,
    published_by_id UUID NULL,
    config_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Application-layer integrity only: proactively drop any *_fkey a tool might add,
-- matching the workspace no-FK / no-cascade rule (see 152_chat_pinned_agent).
ALTER TABLE autopilot_rule_version
    DROP CONSTRAINT IF EXISTS autopilot_rule_version_autopilot_id_fkey,
    DROP CONSTRAINT IF EXISTS autopilot_rule_version_workspace_id_fkey,
    DROP CONSTRAINT IF EXISTS autopilot_rule_version_published_by_id_fkey;

COMMENT ON TABLE autopilot_rule_version IS
    'Append-only snapshot of autopilot rule publishes (MUL-4302 §3.4). One row per substantive publish (create / enable / resume / trigger-condition / target / instructions change), recording the publisher + effective-config summary. Dispatch resolves the latest row for an autopilot as the run''s rule_owner accountable human. No FK, no cascade.';

```

## server/go/migrations/187_autopilot_rule_version_index.up.sql

```sql
-- Single-statement migration: CREATE INDEX CONCURRENTLY cannot run inside a
-- transaction or a multi-command string.
--
-- Dispatch resolves an autopilot's ACTIVE rule version as "the newest row for this
-- (workspace, autopilot)", so index on (workspace_id, autopilot_id, created_at DESC)
-- to serve GetActiveAutopilotRuleVersion's ORDER BY created_at DESC LIMIT 1 without
-- a scan as the append-only table grows.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_autopilot_rule_version_active
    ON autopilot_rule_version (workspace_id, autopilot_id, created_at DESC);

```

## server/go/migrations/188_workspace_attribution_fail_closed.up.sql

```sql
-- Human Attribution, Phase 1 — per-workspace fail-closed policy (MUL-4302 §1/§3.5).
--
-- The accountable-human waterfall degrades to owner_fallback (accountable = agent
-- owner) when no precise human resolves, so every run has an accountable human by
-- default. Compliance/enterprise workspaces can instead opt into FAIL-CLOSED: a run
-- that cannot be attributed to a precise human is NOT enqueued rather than falling
-- back to the owner — better to block an unattributable run than to run it under a
-- degraded label.
--
-- Default FALSE preserves today's behavior (owner_fallback) for every existing
-- workspace. Adding a NOT NULL boolean WITH a constant default is a fast
-- metadata-only change on modern Postgres (no table rewrite).
ALTER TABLE workspace
    ADD COLUMN attribution_fail_closed BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN workspace.attribution_fail_closed IS
    'When TRUE, an agent run that resolves to no precise accountable human (would be owner_fallback) is refused at enqueue instead of degrading to the agent owner (MUL-4302 §3.5). Default FALSE = owner_fallback. Never affects authorization (originator_user_id).';

```

## server/go/migrations/189_autopilot_trigger_publisher.up.sql

```sql
-- Human Attribution — per-trigger responsible publisher (MUL-4302; Bohan + Elon).
-- An autopilot schedule/webhook run is accountable to the human RESPONSIBLE for the
-- firing trigger's current effective configuration — initially whoever created the
-- trigger, then TRANSFERRED to whoever later makes a substantive edit that governs
-- it (the trigger's own cron / filter / enabled state, or an autopilot-level
-- target / instructions / enable change that affects all of its triggers). This models
-- the "current effective automation version's responsible publisher" resolved PER
-- firing trigger, so editing one trigger never reassigns responsibility for another.
--
-- Stored on the trigger row (not derived from the autopilot-scoped rule_version)
-- precisely so per-trigger granularity holds. The resolver reads it as
-- source=trigger_owner (accountable = this member, originator NULL — a scheduled /
-- webhook fire carries no human authorization at fire time; the same authz-safe
-- divergence as rule_owner).
--
-- Constraints (MUL-4302 §7 + workspace DB rules): NO foreign key, NO cascade
-- (integrity is app-layer), nullable with no default so the ALTER is a fast
-- metadata-only change. published_by_type is 'member' | 'agent'; only a 'member'
-- publisher becomes the accountable human — an 'agent'-published trigger degrades to
-- rule_owner like any other agent action. NULL means no publisher recorded (a
-- trigger predating this migration), which degrades to rule_owner then owner_fallback.
ALTER TABLE autopilot_trigger
    ADD COLUMN published_by_type TEXT NULL;

ALTER TABLE autopilot_trigger
    ADD COLUMN published_by_id UUID NULL;

COMMENT ON COLUMN autopilot_trigger.published_by_type IS
    'Actor type of the trigger''s current responsible publisher: member | agent. Set to the creator at creation and re-stamped to the editor on any substantive edit governing this trigger. Consumed only for attribution (source=trigger_owner) — never authorization. NULL on pre-migration triggers (MUL-4302).';

COMMENT ON COLUMN autopilot_trigger.published_by_id IS
    'The member/agent currently responsible for this trigger''s effective config (creator, then last substantive editor). For a member this is the accountable human of runs the trigger fires (source=trigger_owner). No FK, app-layer integrity. NULL on pre-migration triggers, which degrade to rule_owner (MUL-4302).';

```

## server/go/migrations/190_agent_task_attribution_invariant_check.up.sql

```sql
-- Human Attribution — enforce the one-way invariant at the DB layer (MUL-4302;
-- decided by Bohan + Elon on the MUL-4302 thread). The application collapses
-- originator == accountable at a single chokepoint (finalizeAttribution) and every
-- write path takes both from the same attribution.Result — but the #5192 comment-
-- coalescing merge proved that ANOTHER feature's code can silently bypass that
-- chokepoint and leave originator=B / accountable=A. A cross-column CHECK is exactly
-- the class of bug this guards: any future write that breaks the invariant fails at
-- enqueue time rather than silently mis-attributing an audited run.
--
--     originator_user_id IS NOT NULL  ⟹  accountable_user_id = originator_user_id
--
-- This is NOT the source-enum CHECK the earlier ruling forbade (that ban existed so
-- a new source label needs no migration); this locks a two-column equality, not an
-- enumerable value, and carries no FK / cascade.
--
-- UPGRADE SAFETY — the `originator_source IS NULL` clause exempts legacy-writer /
-- unbackfilled-lineage rows (Bohan chose the two-phase rollout on the MUL-4302 thread;
-- raised by Elon). `NOT VALID` skips the initial scan, but Postgres STILL checks a
-- pre-existing row whenever a later UPDATE touches it — even an UPDATE that leaves the
-- attribution columns alone. Cross-deployment stale queued/running tasks predate
-- `185_agent_task_accountable_user`, so they carry (originator_user_id set,
-- accountable_user_id NULL); their next claim / complete / cancel by the new backend
-- would fail a bare invariant CHECK.
--
-- `originator_source` was added by `184` with no default/backfill, so a NULL there does
-- NOT strictly mean "row predates the migration" — it means the row was written by a
-- writer that does not populate attribution: (a) rows created before this PR's
-- migrations; (b) during a rolling deploy, NEW rows an older, not-yet-replaced backend
-- INSERTs against the migrated schema; (c) a retry clone that inherits a legacy row's
-- NULL lineage. All three are exactly the rows the transition must let keep flowing,
-- and all resolve to "no attribution recorded", so exempting them is correct. Every
-- attribution-aware write goes through finalizeAttribution, which always stamps a
-- non-NULL source, so those rows stay under the FULL equality CHECK. Phase 3 backfills
-- the exempt rows (real source + reconciled accountable), then drops this constraint
-- and re-adds the strict form (without the exemption) + VALIDATE.
--
-- This does NOT reopen the #5192 bug class: that merge — and every real enqueue /
-- coalesce path — stamps originator_source non-NULL, so an (originator=B,
-- accountable=A) bypass is still rejected. Only the source-NULL (legacy-writer /
-- unbackfilled) shape is exempt.
--
-- Added NOT VALID so the constraint is a fast metadata-only add on the hot queue table
-- (no full-table ACCESS EXCLUSIVE scan); it enforces on every new INSERT/UPDATE
-- immediately.
--
-- The `accountable_user_id IS NOT NULL AND` guard is load-bearing: a bare
-- `accountable_user_id = originator_user_id` would let (originator=X, accountable=NULL)
-- slip through — SQL evaluates `NULL = X` to UNKNOWN, and a CHECK passes on anything
-- that is not FALSE. The bypass we most need to catch (originator set, accountable
-- left NULL) is exactly that shape, so the NULL must be rejected explicitly.
ALTER TABLE agent_task_queue
    ADD CONSTRAINT agent_task_queue_accountable_matches_originator
    CHECK (
        originator_source IS NULL
        OR originator_user_id IS NULL
        OR (accountable_user_id IS NOT NULL AND accountable_user_id = originator_user_id)
    )
    NOT VALID;

```

## server/go/migrations/191_issue_properties.up.sql

```sql
-- Custom issue properties (MUL-4463).
--
-- Two-part model:
--   1. issue_property — workspace-level property definitions (the catalog),
--      structurally a sibling of issue_label.
--   2. issue.properties — JSONB value bag on each issue keyed by property
--      definition UUID, structurally a sibling of issue.metadata. Values are
--      typed per the definition and validated in the handler; keys are UUIDs
--      so definition renames never require value migrations.
--
-- Definitions are archived (archived_at), never deleted — historical values
-- stay resolvable. The active-definition cap (20/workspace) and per-type value
-- validation live in the handler.

CREATE TABLE issue_property (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('text', 'number', 'select', 'multi_select', 'date', 'checkbox', 'url')),
    description TEXT NOT NULL DEFAULT '',
    -- select / multi_select: {"options": [{"id", "name", "color"}]}; {} for other types.
    config JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(config) = 'object'),
    position FLOAT NOT NULL DEFAULT 0,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE issue ADD COLUMN properties JSONB NOT NULL DEFAULT '{}'::jsonb;
-- NOT VALID + VALIDATE keeps the ACCESS EXCLUSIVE lock instantaneous; the
-- validation pass then runs under SHARE UPDATE EXCLUSIVE without blocking
-- writes (zero-downtime deploys, review round 3).
ALTER TABLE issue ADD CONSTRAINT issue_properties_is_object
    CHECK (jsonb_typeof(properties) = 'object') NOT VALID;
ALTER TABLE issue VALIDATE CONSTRAINT issue_properties_is_object;
-- Larger than metadata's 8KB: multi_select arrays and text values are bigger
-- than metadata primitives, but the bag is still bounded by the definition cap.
ALTER TABLE issue ADD CONSTRAINT issue_properties_size_limit
    CHECK (pg_column_size(properties) <= 16384) NOT VALID;
ALTER TABLE issue VALIDATE CONSTRAINT issue_properties_size_limit;
-- All indexes live in follow-up, single-statement migrations because CREATE
-- INDEX CONCURRENTLY cannot share a migration with other statements. The GIN
-- index is in 192; the issue_property indexes are in 194 and 195.

```

## server/go/migrations/192_issue_properties_gin_index.up.sql

```sql
-- Containment index for custom-property value filtering (MUL-4463).
-- Separate single-statement migration: CREATE INDEX CONCURRENTLY cannot run
-- inside a transaction or share a migration, and a non-concurrent build would
-- block writes on the hot issue table for the duration of the scan.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_properties_gin
    ON issue USING GIN (properties jsonb_path_ops);

```

## server/go/migrations/193_issue_property_drop_workspace_fk.up.sql

```sql
-- A short-lived pre-release build created this foreign key in migration 191.
-- Fresh databases no longer create it; this idempotent cleanup brings databases
-- that applied the earlier migration back to the application-owned lifecycle.
ALTER TABLE issue_property
    DROP CONSTRAINT IF EXISTS issue_property_workspace_id_fkey;

```

## server/go/migrations/194_issue_property_workspace_name_index.up.sql

```sql
-- Enforce case-insensitive property-name uniqueness without blocking writes.
-- Keep this as the migration's only statement: PostgreSQL rejects CREATE INDEX
-- CONCURRENTLY inside a transaction or multi-command string.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_property_ws_name
    ON issue_property (workspace_id, LOWER(name));

```

## server/go/migrations/195_issue_property_workspace_index.up.sql

```sql
-- Support workspace-scoped property listing and counts without blocking writes.
-- Keep this as the migration's only statement: PostgreSQL rejects CREATE INDEX
-- CONCURRENTLY inside a transaction or multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_property_workspace
    ON issue_property (workspace_id);

```

## server/go/migrations/196_issue_property_icon.up.sql

```sql
-- Optional catalog icon key for workspace custom property definitions. The empty
-- string represents no icon so existing rows and older clients keep their
-- current appearance. PostgreSQL can add this constant default without a
-- table rewrite.
ALTER TABLE issue_property
    ADD COLUMN icon TEXT NOT NULL DEFAULT '';

```

## server/go/migrations/197_agent_task_attribution_strict_constraint.up.sql

```sql
-- Human Attribution rollout, phase 2: install the strict one-way invariant
-- alongside migration 190's transitional constraint (MUL-4302).
--
-- Migration 190 temporarily exempted rows with originator_source IS NULL so
-- active legacy tasks and stale writers could survive the rolling deployment.
-- Those rows have now been backfilled out of band. Install the strict form
-- under a temporary name first so it starts protecting new writes immediately
-- while the existing constraint remains in place.
--
-- Keep this ADD separate from migration 198's full-table VALIDATE. PostgreSQL
-- holds the ACCESS EXCLUSIVE lock taken here until the statement transaction
-- ends; combining both steps would unnecessarily block queue traffic for the
-- duration of the validation scan.
ALTER TABLE agent_task_queue
    ADD CONSTRAINT agent_task_queue_accountable_matches_originator_strict
    CHECK (
        originator_user_id IS NULL
        OR (
            accountable_user_id IS NOT NULL
            AND accountable_user_id = originator_user_id
        )
    )
    NOT VALID;

```

## server/go/migrations/198_agent_task_attribution_strict_constraint_validate.up.sql

```sql
-- Validate the strict shadow constraint only after the attribution backfill has
-- completed. This takes a SHARE UPDATE EXCLUSIVE lock while scanning the table,
-- which permits normal INSERT/UPDATE/DELETE traffic to continue.
--
-- Any remaining row where originator_user_id is set but accountable_user_id is
-- NULL or different causes this migration to fail closed. The validated shadow
-- replaces migration 190's transitional constraint in migration 199.
ALTER TABLE agent_task_queue
    VALIDATE CONSTRAINT agent_task_queue_accountable_matches_originator_strict;

```

## server/go/migrations/199_agent_task_attribution_legacy_exemption_remove.up.sql

```sql
-- The strict shadow constraint is validated, so migration 190's transitional
-- originator_source IS NULL exemption can now be removed. Both statements are
-- sent in one migration query and therefore commit atomically: readers never
-- observe the table without either constraint in place.
ALTER TABLE agent_task_queue
    DROP CONSTRAINT agent_task_queue_accountable_matches_originator;

ALTER TABLE agent_task_queue
    RENAME CONSTRAINT agent_task_queue_accountable_matches_originator_strict
    TO agent_task_queue_accountable_matches_originator;

```

## server/go/migrations/200_inbox_archived_listing_index.up.sql

```sql
-- Back the archived-inbox listing (MUL-3736). The only inbox_item index is
-- idx_inbox_recipient (recipient_type, recipient_id, read), which carries
-- neither workspace_id nor archived nor created_at, so the archived list would
-- scan and sort every notification the recipient ever received. Keep this as
-- the migration's only statement: PostgreSQL rejects CREATE INDEX CONCURRENTLY
-- inside a transaction or multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inbox_recipient_archived_created
    ON inbox_item (workspace_id, recipient_type, recipient_id, archived, created_at DESC);

```

## server/go/migrations/201_inbox_active_by_issue_index.up.sql

```sql
-- Partial index over ACTIVE rows keyed by issue (MUL-3736). Serves the
-- NOT EXISTS probe in ListArchivedInboxItems, which asks "does this issue still
-- have a non-archived row?" once per archived row, and the identically-filtered
-- ArchiveInboxByIssue / UnarchiveInboxByIssue writes. Partial on archived=false
-- so it stays small as the archive grows. Keep this as the migration's only
-- statement: PostgreSQL rejects CREATE INDEX CONCURRENTLY inside a transaction
-- or multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inbox_active_by_issue
    ON inbox_item (workspace_id, recipient_type, recipient_id, issue_id)
    WHERE archived = false;

```

## server/go/migrations/202_runtime_profile_add_qwen.up.sql

```sql
-- Add Qwen Code (`qwen`) to the built-in runtime profile protocol whitelist.
-- Kept in lockstep with agent.SupportedTypes and agent.New().  NOT VALID
-- preserves the historical-row tolerance used by the prior family additions.
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'kiro',
        'antigravity',
        'qoder',
        'traecli',
        'deveco',
        'grok',
        'qwen'
    )) NOT VALID;

```

## server/go/migrations/203_issue_workspace_assignee_index.up.sql

```sql
-- Server-side Table grouping filters by workspace before grouping assignees.
-- Keep the concurrent build isolated so writes to the hot issue table remain
-- available while existing workspaces are indexed.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_workspace_assignee
    ON issue (workspace_id, assignee_type, assignee_id);

```

## server/go/migrations/204_issue_workspace_parent_index.up.sql

```sql
-- Root/child Table branches always resolve hierarchy inside one workspace.
-- The existing parent-only index cannot prune another workspace first.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_workspace_parent
    ON issue (workspace_id, parent_issue_id);

```

## server/go/migrations/205_issue_workspace_position_index.up.sql

```sql
-- Serve the Table API's default keyset order without scanning and sorting the
-- entire workspace on every page.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_workspace_position
    ON issue (workspace_id, position, created_at DESC, id DESC);

```

## server/go/migrations/206_agent_disabled_runtime_skills.up.sql

```sql
ALTER TABLE agent
ADD COLUMN disabled_runtime_skills JSONB NOT NULL DEFAULT '[]'::jsonb;

```

## server/go/migrations/207_client_usage_daily.up.sql

```sql
CREATE TABLE client_usage_daily (
    user_id UUID NOT NULL,
    client_type TEXT NOT NULL CHECK (client_type IN ('web', 'desktop')),
    install_id UUID NOT NULL,
    activity_date DATE NOT NULL,
    workspace_id UUID,
    client_version TEXT NOT NULL,
    os TEXT NOT NULL,
    first_active_at TIMESTAMPTZ NOT NULL,
    last_active_at TIMESTAMPTZ NOT NULL,
    runtime_probed_at TIMESTAMPTZ,
    probe_result TEXT CHECK (probe_result IN ('success', 'error')),
    runtime_count INTEGER CHECK (runtime_count >= 0),
    provider_summary JSONB,
    online_count INTEGER CHECK (online_count >= 0),
    offline_count INTEGER CHECK (offline_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (first_active_at <= last_active_at),
    CHECK (
        (runtime_probed_at IS NULL AND probe_result IS NULL AND runtime_count IS NULL AND provider_summary IS NULL AND online_count IS NULL AND offline_count IS NULL)
        OR
        (runtime_probed_at IS NOT NULL AND probe_result = 'error' AND runtime_count IS NULL AND provider_summary IS NULL AND online_count IS NULL AND offline_count IS NULL)
        OR
        (runtime_probed_at IS NOT NULL AND probe_result = 'success' AND runtime_count IS NOT NULL AND provider_summary IS NOT NULL AND online_count IS NOT NULL AND offline_count IS NOT NULL AND online_count + offline_count = runtime_count AND jsonb_typeof(provider_summary) = 'object')
    )
);

```

## server/go/migrations/208_client_usage_daily_unique_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY client_usage_daily_identity_date_uidx ON client_usage_daily (user_id, client_type, install_id, activity_date);

```

## server/go/migrations/209_client_usage_daily_primary_key.up.sql

```sql
ALTER TABLE client_usage_daily ADD CONSTRAINT client_usage_daily_pkey PRIMARY KEY USING INDEX client_usage_daily_identity_date_uidx;

```

## server/go/migrations/210_client_usage_daily_query_index.up.sql

```sql
CREATE INDEX CONCURRENTLY client_usage_daily_activity_client_user_idx ON client_usage_daily (activity_date, client_type, user_id);

```

## server/go/migrations/211_client_usage_daily_workspace_index.up.sql

```sql
CREATE INDEX CONCURRENTLY client_usage_daily_workspace_idx ON client_usage_daily (workspace_id) WHERE workspace_id IS NOT NULL;

```

## server/go/migrations/212_agent_service_tier.up.sql

```sql
-- Per-agent Codex service-tier override. The value is the runtime-native
-- catalog ID reported by `codex debug models --bundled` (for example,
-- "priority", displayed by Codex as "Fast"). NULL means "inherit the local
-- Codex configuration / account default" and produces no RPC override.
ALTER TABLE agent ADD COLUMN service_tier TEXT;

```

## server/go/migrations/213_task_usage_authoritative_cost.up.sql

```sql
-- Provider-reported cost for a usage record, and the rollup columns needed to
-- mix it with rows that have none.
--
-- WHY: cost has always been derived client-side as tokens x a static rate.
-- That cannot express request-level pricing rules. xAI bills a Grok request at
-- 2x once its prompt reaches 200K tokens, and a `task_usage` row aggregates
-- every model call in a turn — so the stored token counts genuinely cannot say
-- which tier any individual request hit. Thresholding on the aggregate would
-- turn a bounded 50% under-estimate into an unbounded over-estimate. Grok
-- already returns its own price per turn (`_meta.usage.costUsdTicks`); store
-- it and the arithmetic stops being a guess.
--
-- UNIT: ticks of 1e-10 USD, as xAI reports them. An integer keeps sub-cent
-- turn costs exact end-to-end instead of drifting through float64. BIGINT
-- holds ~9.2e8 USD, which is not a reachable spend for one usage record.
--
-- NULL means "the provider reported no cost" — every pre-existing row, and
-- every provider that doesn't return one. Those rows keep being estimated from
-- the pricing table. No backfill: historical rows have no authoritative figure
-- to recover, and inventing one would be the same guess we're removing.
ALTER TABLE task_usage
    ADD COLUMN IF NOT EXISTS cost_usd_ticks BIGINT;

COMMENT ON COLUMN task_usage.cost_usd_ticks IS
    'Provider-reported cost in 1e-10 USD. NULL when the provider reports none; those rows are priced client-side from the static rate table.';

-- Rollup side. A single hourly bucket can mix rows that carry an authoritative
-- cost with rows that don't (two providers, or Grok before and after a CLI
-- upgrade). Summing only the authoritative side would silently under-report
-- the bucket, so the rollup carries both halves:
--
--   cost_usd_ticks        - sum over rows that HAVE a provider cost
--   uncosted_*_tokens     - tokens from rows that do NOT, i.e. exactly the
--                           tokens still needing a rate-table estimate
--
-- The consumer then reports `authoritative + estimate(uncosted tokens)`, which
-- degrades to today's behaviour when nothing in the bucket is authoritative.
-- The existing token columns keep their meaning (every row in the bucket) so
-- token displays are untouched.
--
-- The `uncosted_*` columns are NULLABLE WITH NO DEFAULT, and that is load-
-- bearing: NULL means "this bucket has never been recomputed since the split
-- existed", which is every pre-existing row. Readers COALESCE it to the
-- bucket's own token total, i.e. "estimate all of it" — exactly what those
-- rows did before. A `NOT NULL DEFAULT 0` would instead assert "nothing here
-- needs estimating" and collapse every historical bucket's cost to $0 until
-- the rollup happened to touch it again, which is why this migration does NOT
-- rewrite history to seed them: with NULL there is nothing to seed. A bare
-- ADD COLUMN is metadata-only, so this stays a fast DDL with no table rewrite,
-- no WAL churn, and no lock held proportional to table size.
--
-- The rollup writes concrete values for every bucket it recomputes, so rows
-- heal into the split naturally as they are touched.
--
-- `cost_usd_ticks` is NOT NULL DEFAULT 0 because 0 is the honest identity for
-- a sum of "no rows here were priced by their provider", which is true of
-- every historical bucket.
--
-- All additive, so the unique key, the dirty-queue key shape, and every
-- trigger in migration 102 are unaffected.
ALTER TABLE task_usage_hourly
    ADD COLUMN IF NOT EXISTS cost_usd_ticks              BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS uncosted_input_tokens       BIGINT,
    ADD COLUMN IF NOT EXISTS uncosted_output_tokens      BIGINT,
    ADD COLUMN IF NOT EXISTS uncosted_cache_read_tokens  BIGINT,
    ADD COLUMN IF NOT EXISTS uncosted_cache_write_tokens BIGINT;

COMMENT ON COLUMN task_usage_hourly.cost_usd_ticks IS
    'Sum of provider-reported cost (1e-10 USD) over the rows in this bucket that had one; 0 when none did.';
COMMENT ON COLUMN task_usage_hourly.uncosted_input_tokens IS
    'Input tokens from rows with no provider-reported cost — the portion still priced from the static rate table. NULL on buckets not yet recomputed since this column existed; readers COALESCE to input_tokens.';

-- Teach the rollup to populate them. Body is migration 102's, with the two
-- new expression groups in `recomputed` and the matching SET list on
-- conflict; everything else — dirty discovery, the empty-bucket delete, the
-- queue drain, the idempotency contract — is unchanged.
CREATE OR REPLACE FUNCTION rollup_task_usage_hourly_window(
    p_from TIMESTAMPTZ,
    p_to   TIMESTAMPTZ
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT;
BEGIN
    IF p_from >= p_to THEN
        RETURN 0;
    END IF;

    WITH
    dirty_from_updates AS (
        SELECT DISTINCT
            task_usage_hour_bucket(tu.created_at) AS bucket_hour,
            a.workspace_id                        AS workspace_id,
            atq.runtime_id                        AS runtime_id,
            atq.agent_id                          AS agent_id,
            i.project_id                          AS project_id,
            tu.provider                           AS provider,
            tu.model                              AS model
          FROM task_usage tu
          JOIN agent_task_queue atq ON atq.id      = tu.task_id
          JOIN agent            a   ON a.id        = atq.agent_id
          LEFT JOIN issue       i   ON i.id        = atq.issue_id
         WHERE atq.runtime_id IS NOT NULL
           AND (
                (tu.updated_at >= p_from AND tu.updated_at < p_to)
                -- Legacy updated_at-NULL rows; partial index from 078.
                OR (tu.updated_at IS NULL
                    AND tu.created_at >= p_from
                    AND tu.created_at <  p_to)
           )
    ),
    dirty_from_queue AS (
        SELECT bucket_hour, workspace_id, runtime_id, agent_id,
               project_id, provider, model
          FROM task_usage_hourly_dirty
         WHERE enqueued_at < p_to
    ),
    dirty_keys AS (
        SELECT * FROM dirty_from_updates
        UNION
        SELECT * FROM dirty_from_queue
    ),
    recomputed AS (
        SELECT
            dk.bucket_hour,
            dk.workspace_id,
            dk.runtime_id,
            dk.agent_id,
            dk.project_id,
            dk.provider,
            dk.model,
            SUM(tu.input_tokens)::bigint       AS input_tokens,
            SUM(tu.output_tokens)::bigint      AS output_tokens,
            SUM(tu.cache_read_tokens)::bigint  AS cache_read_tokens,
            SUM(tu.cache_write_tokens)::bigint AS cache_write_tokens,
            -- Authoritative half: only rows the provider priced.
            COALESCE(SUM(tu.cost_usd_ticks), 0)::bigint AS cost_usd_ticks,
            -- Estimated half: tokens from rows the provider did not price.
            COALESCE(SUM(tu.input_tokens)       FILTER (WHERE tu.cost_usd_ticks IS NULL), 0)::bigint AS uncosted_input_tokens,
            COALESCE(SUM(tu.output_tokens)      FILTER (WHERE tu.cost_usd_ticks IS NULL), 0)::bigint AS uncosted_output_tokens,
            COALESCE(SUM(tu.cache_read_tokens)  FILTER (WHERE tu.cost_usd_ticks IS NULL), 0)::bigint AS uncosted_cache_read_tokens,
            COALESCE(SUM(tu.cache_write_tokens) FILTER (WHERE tu.cost_usd_ticks IS NULL), 0)::bigint AS uncosted_cache_write_tokens,
            COUNT(DISTINCT tu.task_id)::bigint AS task_count,
            COUNT(*)::bigint                   AS event_count
          FROM dirty_keys dk
          JOIN agent_task_queue atq ON atq.runtime_id  = dk.runtime_id
                                    AND atq.agent_id    = dk.agent_id
          JOIN agent            a   ON a.id            = atq.agent_id
                                    AND a.workspace_id = dk.workspace_id
          LEFT JOIN issue       i   ON i.id            = atq.issue_id
          JOIN task_usage       tu  ON tu.task_id      = atq.id
                                    AND tu.provider    = dk.provider
                                    AND tu.model       = dk.model
                                    AND task_usage_hour_bucket(tu.created_at) = dk.bucket_hour
         WHERE (i.project_id IS NOT DISTINCT FROM dk.project_id)
         GROUP BY 1, 2, 3, 4, 5, 6, 7
    ),
    upserted AS (
        INSERT INTO task_usage_hourly AS d (
            bucket_hour, workspace_id, runtime_id, agent_id,
            project_id, provider, model,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            cost_usd_ticks,
            uncosted_input_tokens, uncosted_output_tokens,
            uncosted_cache_read_tokens, uncosted_cache_write_tokens,
            task_count, event_count
        )
        SELECT
            bucket_hour, workspace_id, runtime_id, agent_id,
            project_id, provider, model,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            cost_usd_ticks,
            uncosted_input_tokens, uncosted_output_tokens,
            uncosted_cache_read_tokens, uncosted_cache_write_tokens,
            task_count, event_count
          FROM recomputed
        ON CONFLICT ON CONSTRAINT uq_task_usage_hourly_key DO UPDATE
            SET input_tokens                = EXCLUDED.input_tokens,
                output_tokens               = EXCLUDED.output_tokens,
                cache_read_tokens           = EXCLUDED.cache_read_tokens,
                cache_write_tokens          = EXCLUDED.cache_write_tokens,
                cost_usd_ticks              = EXCLUDED.cost_usd_ticks,
                uncosted_input_tokens       = EXCLUDED.uncosted_input_tokens,
                uncosted_output_tokens      = EXCLUDED.uncosted_output_tokens,
                uncosted_cache_read_tokens  = EXCLUDED.uncosted_cache_read_tokens,
                uncosted_cache_write_tokens = EXCLUDED.uncosted_cache_write_tokens,
                task_count                  = EXCLUDED.task_count,
                event_count                 = EXCLUDED.event_count,
                updated_at                  = now()
        RETURNING 1
    ),
    deleted_empty AS (
        DELETE FROM task_usage_hourly d
         USING dirty_keys dk
         WHERE d.bucket_hour  = dk.bucket_hour
           AND d.workspace_id = dk.workspace_id
           AND d.runtime_id   = dk.runtime_id
           AND d.agent_id     = dk.agent_id
           AND d.project_id IS NOT DISTINCT FROM dk.project_id
           AND d.provider     = dk.provider
           AND d.model        = dk.model
           AND NOT EXISTS (
               SELECT 1 FROM recomputed r
                WHERE r.bucket_hour  = dk.bucket_hour
                  AND r.workspace_id = dk.workspace_id
                  AND r.runtime_id   = dk.runtime_id
                  AND r.agent_id     = dk.agent_id
                  AND r.project_id IS NOT DISTINCT FROM dk.project_id
                  AND r.provider     = dk.provider
                  AND r.model        = dk.model
           )
        RETURNING 1
    )
    SELECT (SELECT COUNT(*) FROM upserted) + (SELECT COUNT(*) FROM deleted_empty)
      INTO v_rows;

    DELETE FROM task_usage_hourly_dirty WHERE enqueued_at < p_to;

    RETURN v_rows;
END;
$$;

```

## server/go/migrations/214_chat_session_project.up.sql

```sql
-- Chat sessions may opt into one project's durable context. Keep this as a
-- soft reference: adding a foreign key would validate the established,
-- write-active chat_session table and take a cross-table lock during deploy.
-- Create/delete handlers serialize on the project row, project deletion clears
-- existing references, and daemon claim revalidates workspace ownership before
-- injecting any context.
--
-- IF NOT EXISTS because this migration was first shipped as 213_chat_session_project
-- and later renumbered to 214 (#5868, dodging a prefix collision). Environments
-- that already applied it under the old 213 name have the column but not the 214
-- version row, so the runner re-applies it under the new name; without the guard
-- that re-run fails with "column already exists" (SQLSTATE 42701) and blocks deploy.
ALTER TABLE chat_session
  ADD COLUMN IF NOT EXISTS project_id UUID;

```

## server/go/migrations/215_chat_session_project_index.up.sql

```sql
-- Project deletion clears chat-session references by project_id. Build this
-- partial index concurrently so the established chat_session write path stays
-- available throughout rollout. A single statement is required because
-- CREATE INDEX CONCURRENTLY cannot run inside a transaction.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_session_project
    ON chat_session (project_id)
    WHERE project_id IS NOT NULL;

```

## server/go/migrations/216_vcs_integration.up.sql

```sql
-- VCS (self-hosted Git provider: Forgejo, Gitea, GitLab) integration:
-- per-workspace token-based connections. Unlike the GitHub App model
-- (server/go/migrations/079), these providers have no app/installation concept —
-- each workspace stores its own instance URL plus an access token used for
-- API enrichment and a webhook secret used to verify inbound webhook signatures.
--
-- Both secrets are stored as base64-encoded secretbox ciphertext (never
-- plaintext). Decryption uses the WORKPAL_VCS_SECRET_KEY box wired in
-- cmd/server/router.go.
--
-- Mirrored pull requests and commit statuses are stored in vcs_pull_request
-- and vcs_commit_status tables, separate from GitHub tables.
--
-- Per the project migration rules these tables carry NO foreign keys or
-- cascades: relationships and dependent cleanup are resolved in application
-- code (DeleteVCSConnection, DeleteWorkspace, and DeleteIssue each sweep the
-- rows below in a single atomic statement). The inline UNIQUE / PRIMARY KEY
-- constraints stay — they back the ON CONFLICT upsert targets in vcs.sql.
-- Secondary indexes live in follow-up single-statement CREATE INDEX
-- CONCURRENTLY migrations (217-221), which cannot share a file with these
-- CREATE TABLEs.

CREATE TABLE IF NOT EXISTS vcs_connection (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id             UUID NOT NULL,
    provider                 TEXT NOT NULL DEFAULT 'forgejo'
        CHECK (provider IN ('forgejo', 'gitea', 'gitlab')),
    instance_url             TEXT NOT NULL,
    account_login            TEXT NOT NULL,
    access_token_encrypted   TEXT NOT NULL,
    webhook_secret_encrypted TEXT NOT NULL,
    connected_by_id          UUID,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, instance_url)
);

CREATE TABLE IF NOT EXISTS vcs_pull_request (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      UUID NOT NULL,
    connection_id     UUID NOT NULL,
    provider          TEXT NOT NULL DEFAULT 'forgejo'
        CHECK (provider IN ('forgejo', 'gitea', 'gitlab')),
    repo_owner        TEXT NOT NULL,
    repo_name         TEXT NOT NULL,
    pr_number         INTEGER NOT NULL,
    title             TEXT NOT NULL,
    state             TEXT NOT NULL
        CHECK (state IN ('open', 'closed', 'merged', 'draft')),
    html_url          TEXT NOT NULL,
    branch            TEXT,
    head_sha          TEXT NOT NULL DEFAULT '',
    author_login      TEXT,
    author_avatar_url TEXT,
    merged_at         TIMESTAMPTZ,
    closed_at         TIMESTAMPTZ,
    pr_created_at     TIMESTAMPTZ NOT NULL,
    pr_updated_at     TIMESTAMPTZ NOT NULL,
    additions         INTEGER NOT NULL DEFAULT 0,
    deletions         INTEGER NOT NULL DEFAULT 0,
    changed_files     INTEGER NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (connection_id, repo_owner, repo_name, pr_number)
);

CREATE TABLE IF NOT EXISTS issue_vcs_pull_request (
    issue_id        UUID NOT NULL,
    pull_request_id UUID NOT NULL,
    close_intent    BOOLEAN NOT NULL DEFAULT FALSE,
    -- reference_only marks a link justified ONLY by a bare body mention (no
    -- closing keyword and no title/branch reference). Mirrors the GitHub
    -- issue_pull_request column (migration 127): such links are hidden from the
    -- issue PR list and excluded from the close aggregate so a drive-by mention
    -- neither shows as a working PR nor blocks a genuine Closes sibling.
    reference_only  BOOLEAN NOT NULL DEFAULT FALSE,
    linked_by_type  TEXT,
    linked_by_id    UUID,
    linked_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (issue_id, pull_request_id)
);

CREATE TABLE IF NOT EXISTS vcs_commit_status (
    connection_id UUID NOT NULL,
    sha           TEXT NOT NULL,
    context       TEXT NOT NULL,
    state         TEXT NOT NULL,
    target_url    TEXT,
    description   TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (connection_id, sha, context)
);

```

## server/go/migrations/217_vcs_connection_workspace_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vcs_connection_workspace
    ON vcs_connection (workspace_id);

```

## server/go/migrations/218_vcs_pull_request_workspace_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vcs_pull_request_workspace
    ON vcs_pull_request (workspace_id);

```

## server/go/migrations/219_vcs_pull_request_connection_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vcs_pull_request_connection
    ON vcs_pull_request (connection_id);

```

## server/go/migrations/220_issue_vcs_pull_request_pr_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_vcs_pull_request_pr
    ON issue_vcs_pull_request (pull_request_id);

```

## server/go/migrations/221_vcs_commit_status_lookup_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vcs_commit_status_lookup
    ON vcs_commit_status (connection_id, sha);

```

## server/go/migrations/222_github_pr_api_snapshot.up.sql

```sql
-- MUL-5265: GitHub API snapshot for PR cards (Plan C).
--
-- The PR card's CI status and mergeability are now sourced from an
-- authenticated GitHub API snapshot (GraphQL pullRequest query) rather than
-- inferred from webhook check_suite events. Webhooks and page visits only
-- trigger a refresh; the API response is the single source of truth and is
-- written as one atomic batch replace per PR.
--
-- All new columns are nullable / defaulted so rows that pre-date the snapshot
-- (or deployments without a GitHub App private key, where the feature degrades
-- off) keep working: the card simply hides the CI / merge region until a
-- snapshot lands.

ALTER TABLE github_pull_request
    -- GraphQL `mergeable`: MERGEABLE / CONFLICTING / UNKNOWN. Answers only
    -- "is there a merge conflict". NULL until first snapshot.
    ADD COLUMN api_mergeable TEXT,
    -- GraphQL `mergeStateStatus`: CLEAN / DIRTY / BLOCKED / BEHIND / UNSTABLE /
    -- DRAFT / HAS_HOOKS / UNKNOWN. "Ready to merge" is derived ONLY from CLEAN.
    ADD COLUMN api_merge_state_status TEXT,
    -- GraphQL statusCheckRollup.state: SUCCESS / FAILURE / PENDING / ERROR /
    -- EXPECTED. NULL means statusCheckRollup was null → "no checks yet", which
    -- must never be rendered as passed.
    ADD COLUMN checks_rollup_state TEXT,
    -- The head SHA the snapshot was fetched for. Pinned so a slow response for
    -- an old head cannot overwrite a newer head's snapshot (head-SHA anti-stale
    -- write). Empty until first snapshot.
    ADD COLUMN snapshot_head_sha TEXT NOT NULL DEFAULT '',
    -- When the snapshot was fetched. Drives the TTL / page-visit refresh and the
    -- stale visual marker. NULL until first snapshot.
    ADD COLUMN snapshot_fetched_at TIMESTAMPTZ;

-- Per-check snapshot rows for a PR's current head. Replaced atomically (delete
-- all + insert) on every successful API fetch — no incremental inference. Both
-- GraphQL CheckRun and StatusContext contexts are normalized into this shape at
-- write time (see ghsnapshot.normalizeContext). Rows are addressed by
-- (pr_id, ordinal): two checks can share a name (matrix jobs, re-runs), so name
-- is not unique. The (pr_id, ordinal) UNIQUE index is created CONCURRENTLY in
-- the next migration (223) — no index (including a PRIMARY KEY's) may be built
-- non-concurrently in a migration, even on a new table (see CLAUDE.md), so the
-- table is created without a primary key and the unique index is added in its
-- own single-statement migration.
CREATE TABLE github_pull_request_check_run (
    pr_id             UUID    NOT NULL,
    head_sha          TEXT    NOT NULL,
    ordinal           INTEGER NOT NULL,
    name              TEXT    NOT NULL,
    -- Normalized lifecycle: 'queued' / 'in_progress' / 'completed'.
    status            TEXT    NOT NULL,
    -- Normalized conclusion: 'success' / 'failure' / 'neutral' / 'cancelled' /
    -- 'skipped' / 'timed_out' / 'action_required' / 'error' / ... ; NULL while
    -- the check is still running.
    conclusion        TEXT,
    details_url       TEXT,
    -- TRUE for legacy commit-status contexts (GraphQL StatusContext), FALSE for
    -- Checks API runs (GraphQL CheckRun). Kept for display / debugging.
    is_status_context BOOLEAN NOT NULL DEFAULT FALSE
);

```

## server/go/migrations/223_github_pr_check_run_pr_ordinal_index.up.sql

```sql
-- Single statement: CREATE UNIQUE INDEX CONCURRENTLY cannot run inside a
-- transaction or share a multi-command migration file. Split out from the table
-- creation in 222 so no index is built non-concurrently (CLAUDE.md rule applies
-- even to indexes on newly created tables, including a PRIMARY KEY's).
--
-- (pr_id, ordinal) is unique per snapshot — the atomic replace deletes all rows
-- for a pr_id then re-inserts with sequential ordinals — and this index also
-- serves the pr_id-prefix lookups used by the list aggregation and the
-- workspace/PR cleanup deletes.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS github_pull_request_check_run_pr_ordinal_idx
    ON github_pull_request_check_run (pr_id, ordinal);

```

## server/go/migrations/224_agent_task_session_rollout_missing.up.sql

```sql
-- Per-task signal that the daemon withheld this task's Codex session from the
-- (agent_id, issue_id) resume lookup because its rollout was never written to
-- the per-issue store (MUL-5305). When the next follow-up falls back to an
-- older good session, the claim reads this flag on the most recent terminal
-- task to still disclose that the most recent turn's context could not be
-- carried over (PriorSessionResumeUnavailable), preserving MUL-4424's
-- transparent-degradation contract. Default FALSE keeps every existing task
-- and every non-Codex task unaffected.
ALTER TABLE agent_task_queue
  ADD COLUMN session_rollout_missing BOOLEAN NOT NULL DEFAULT FALSE;

```

## server/go/migrations/225_chat_message_channel_media_pending.up.sql

```sql
ALTER TABLE chat_message
    ADD COLUMN channel_media_pending_until TIMESTAMPTZ;

```

## server/go/migrations/226_chat_message_channel_ingested.up.sql

```sql
-- Immutable provenance for channel-ingested (Feishu/Slack) user messages.
-- The cancel draft-restore path gates on this instead of the deletable
-- channel_chat_session_binding row: archiving a session or rebinding an
-- installation deletes the binding but must never expose the original
-- inbound messages to restore-deletion.
ALTER TABLE chat_message
    ADD COLUMN channel_ingested BOOLEAN NOT NULL DEFAULT FALSE;

```

## server/go/migrations/227_channel_media_pending_object.up.sql

```sql
-- Intent ledger for channel media objects (two-system atomicity, PR #5580).
-- A row is written BEFORE the object is uploaded and cleared inside the same
-- transaction that inserts the attachment rows, so "did my side effect
-- happen?" is never adjudicated inline: every ambiguous outcome (upload
-- error, unknown commit result, crash between upload and bind) simply leaves
-- the row for the asynchronous reconciler, which settles it long after any
-- in-flight PUT or COMMIT can still land.
--
-- state machine: 'pending' (intent recorded; bind may still claim it) →
-- 'deleting' (a reconciler holds the lease; bind must never attach this key) →
-- 'tombstoned' (the object was deleted, but the row is kept so late
-- materializations are re-deleted; see below).
-- The reconciler checks for a durable attachment reference only AFTER winning
-- the claim — at that point a bind can no longer succeed on the key, so the
-- check cannot race a late COMMIT. Every tombstone pass re-checks before
-- re-deleting: reclaiming an orphan must never outrank keeping an object an
-- attachment durably reads.
--
-- The tombstone exists because a DELETE cannot be ordered against a PUT the
-- client already abandoned: the store may still materialize that object after
-- the delete. Clearing the row immediately would leave such an object with no
-- ledger row and nothing to reclaim it, which would make the settle delay the
-- de-facto correctness barrier for the PUT/DELETE race. Instead the row stays
-- as a tombstone and the object is re-deleted on a widening schedule
-- (tombstone_pass-indexed), so a late materialization is caught by a later
-- pass.
-- storage_key is the logical primary key, attached in migration 229 via a
-- CONCURRENTLY-built unique index (228) per the repo convention that every
-- migration index — including a new table's unique index — is created
-- concurrently in its own single-statement migration (see 207-209 for the
-- same three-step pattern on client_usage_daily).
CREATE TABLE channel_media_pending_object (
    storage_key      TEXT NOT NULL,
    workspace_id     UUID NOT NULL,
    chat_message_id  UUID NOT NULL,
    storage_url      TEXT NOT NULL,
    -- Ops diagnostics only (per-installation debugging); no logic keys on it.
    installation_id  UUID,
    state            TEXT NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'deleting', 'tombstoned')),
    lease_token      UUID,
    lease_expires_at TIMESTAMPTZ,
    attempt          INT NOT NULL DEFAULT 0,
    next_attempt_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error       TEXT,
    -- Position in the tombstone re-delete schedule. Its own column rather
    -- than a marker inside last_error: a failed re-delete writes last_error,
    -- which would erase the schedule position and restart the walk, so a
    -- store failing intermittently could keep a tombstone alive forever.
    tombstone_pass   INT NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/228_channel_media_pending_object_key_index.up.sql

```sql
-- Unique index backing channel_media_pending_object's primary key (attached
-- in 228 USING INDEX) and the intent upsert's ON CONFLICT (storage_key).
-- Kept in its own single-statement migration so CONCURRENTLY runs outside an
-- implicit transaction block (repo convention; see migrations 119 and 208).
CREATE UNIQUE INDEX CONCURRENTLY channel_media_pending_object_storage_key_uidx
    ON channel_media_pending_object (storage_key);

```

## server/go/migrations/229_channel_media_pending_object_primary_key.up.sql

```sql
ALTER TABLE channel_media_pending_object
    ADD CONSTRAINT channel_media_pending_object_pkey PRIMARY KEY USING INDEX channel_media_pending_object_storage_key_uidx;

```

## server/go/migrations/230_channel_media_pending_object_claim_index.up.sql

```sql
-- Serves the reconciler's claim scan (state + due time). The migration runner
-- executes files outside an explicit transaction, so CONCURRENTLY is kept in
-- its own single-statement migration to avoid Postgres' implicit transaction
-- block for multi-statement query strings (same convention as migration 119).
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_channel_media_pending_object_claim
    ON channel_media_pending_object (state, next_attempt_at);

```

## server/go/migrations/231_agent_task_queue_terminal_completed_at_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- Every Usage-page dashboard rollup that reads agent_task_queue filters on
-- `status IN ('completed','failed') AND completed_at >= <cutoff>` and then
-- joins `agent` for the workspace scope — ListDashboardRunTimeDaily,
-- ListDashboardAgentRunTime, and the two failure rollups added for the
-- errors charts. agent_task_queue had no index on completed_at at all, so
-- each of those was a full scan of a table whose lifetime row count is
-- dominated by rows outside any 30-day window.
--
-- The partial predicate matches those queries' status filter verbatim so the
-- planner can prove index applicability, and it keeps the index off the
-- queued / dispatched / running rows that the hot dispatch path churns —
-- a row only enters this index once, when it reaches a terminal state.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_terminal_completed_at
    ON agent_task_queue (completed_at)
    WHERE status IN ('completed', 'failed');

```

## server/go/migrations/232_channel_media_pending_object_due_index.up.sql

```sql
-- The reconciler claims one row per statement, ordered by next_attempt_at
-- across all three states. Migration 230's index leads with state, so it
-- cannot serve that ordering: under backlog the planner falls back to a seq
-- scan plus an external merge sort, and FOR UPDATE blocks the bounded top-N
-- optimization, so every claim in a sweep pays the full sort. Ordering on
-- next_attempt_at alone lets the claim walk the index and stop at the first
-- due row. Same CONCURRENTLY-in-its-own-file convention as migration 230.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_channel_media_pending_object_due
    ON channel_media_pending_object (next_attempt_at);

```

## server/go/migrations/233_agent_task_queue_agent_terminal_latest_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- ListWorkspaceAgentTaskSnapshot needs "the latest terminal task per agent".
-- Neither existing index can serve that shape:
--   - idx_agent_task_queue_agent (agent_id, status) from 001_init has no
--     completed_at, so the planner still has to read and sort every terminal
--     row of every agent in the workspace.
--   - idx_agent_task_queue_terminal_completed_at (completed_at) from 231 is
--     completed_at-first, built for the cross-agent Usage time-window
--     rollups, so it cannot skip to one agent's newest row.
-- Both stay: they still serve those other read patterns.
--
-- This index leads with agent_id and then carries the snapshot's full tie-break
-- order, so the per-agent lookup becomes an ordered index scan with LIMIT 1
-- instead of a workspace-wide sort. The partial predicate matches the query's
-- status filter verbatim so the planner can prove applicability, and it keeps
-- the index off the queued / dispatched / running rows the hot dispatch path
-- churns — a row only enters this index once, when it reaches a terminal state.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_agent_terminal_latest
    ON agent_task_queue (agent_id, completed_at DESC NULLS LAST, created_at DESC, id DESC)
    WHERE status IN ('completed', 'failed');

```

## server/go/migrations/234_agent_task_queue_retired_session_id.up.sql

```sql
-- retired_session_id records an agent session this task proved unresumable and
-- that must never be handed to a later run, on ANY path.
--
-- The daemon already knew this and had no way to say it. A terminal report
-- carries one session_id, and an empty one meant both "no session to report"
-- and "forget the old session" — so after a fresh-session retry recovered a
-- turn, the poisoned id it retried away from stayed selectable: an older
-- completed row on the issue still pointed at it, and the chat_session pointer
-- still held it. The next run resumed the same dead transcript (GH #6066).
--
-- Nullable and write-once per row: set only when a run abandons a session it
-- was told to resume. NULL — the overwhelming majority of rows — means nothing
-- was retired. No index was added in this migration: every reader at the time
-- scoped by (agent_id, issue_id) or chat_session_id, and the retired set within
-- a scope was tiny. Migrations 349/350 later added terminal-resume and retired-
-- session indexes after production history made that assumption too costly.
ALTER TABLE agent_task_queue ADD COLUMN IF NOT EXISTS retired_session_id TEXT;

```

## server/go/migrations/235_chat_message_quick_actions.up.sql

```sql
ALTER TABLE chat_message
ADD COLUMN IF NOT EXISTS quick_actions JSONB NOT NULL DEFAULT '[]'::jsonb;

```

## server/go/migrations/236_agent_task_quick_actions_disabled.up.sql

```sql
ALTER TABLE agent_task_queue
ADD COLUMN IF NOT EXISTS quick_actions_disabled BOOLEAN NOT NULL DEFAULT false;

```

## server/go/migrations/237_quick_action.up.sql

```sql
-- Issue Quick Actions (MUL-5465).
--
-- A quick action is a workspace-level preset for "who to call and what to say"
-- on an existing issue. Clicking one renders `prompt` server-side and posts a
-- `quick_action` comment carrying the target's mention markup, which then runs
-- through the existing comment -> mention -> task trigger path. There is no
-- separate dispatch engine: permission (canInvokeAgent), attribution, squad
-- leader routing, the execution log, and pending-task coalescing are all
-- inherited from that path by construction.
--
-- `visibility` is the AUTHOR'S INTENT, chosen at creation:
--   - 'public'  — meant for the team. The handler requires a target every
--                 workspace member can invoke, so a public action is runnable
--                 by everyone by construction.
--   - 'private' — meant for its creator only; any target is allowed.
--
-- It is intent, NOT an authorization decision: the run path always re-checks
-- canInvokeAgent, so a target whose permission_mode changes later can never
-- turn a stale row into an actual privilege. The worst case is a public action
-- whose agent went private, which then fails loudly at click time.
--
-- Deliberately absent columns:
--   - cron / webhook_token / execution_mode: those belong to autopilot. A
--     quick action is human-triggered and always acts on an existing issue.
--   - `position`: ordering is use_count DESC everywhere. A manual order plus a
--     usage order meant one list with two different sorts, which is its own
--     source of confusion.
--   - `input_*`: the `/` slash command already inserts a rendered action into
--     the composer for editing, which covers "same action, one detail
--     different" more flexibly than a single fixed field could.
--
-- Actions archive (status='archived') instead of deleting so historical
-- `quick_action` comments stay resolvable to a name.
CREATE TABLE quick_action (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    -- Mirrors autopilot's polymorphic assignee: 'agent' -> agent(id),
    -- 'squad' -> squad(id), resolved to squad.leader_id at run time.
    assignee_type TEXT NOT NULL CHECK (assignee_type IN ('agent', 'squad')),
    assignee_id UUID NOT NULL,
    -- Stored and sent VERBATIM. No interpolation of any kind: every variable
    -- we considered ({{issue.title}}, {{issue.identifier}}, {{issue.url}},
    -- {{user.name}}, {{date}}) names something the agent already has from the
    -- issue context and from the comment's own author, so none of them changed
    -- what the agent ATTENDS TO -- only what it was told twice. The handler
    -- still REJECTS any `{{...}}` at write time so a habitual template token
    -- cannot land literally in an agent's instructions.
    prompt TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'public' CHECK (visibility IN ('private', 'public')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    last_used_at TIMESTAMPTZ,
    use_count BIGINT NOT NULL DEFAULT 0,
    created_by_type TEXT NOT NULL CHECK (created_by_type IN ('member', 'agent')),
    created_by_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes live in follow-up single-statement migrations: CREATE INDEX
-- CONCURRENTLY cannot share a migration with other statements.

```

## server/go/migrations/238_quick_action_workspace_index.up.sql

```sql
-- Listing index for the settings page and the issue sidebar (MUL-5465). Both
-- read "the active actions of one workspace", ordered by use_count DESC.
-- Single-statement migration: CREATE INDEX CONCURRENTLY cannot run inside a
-- transaction or share a migration file.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quick_action_workspace_status_usage
    ON quick_action(workspace_id, status, use_count DESC);

```

## server/go/migrations/239_comment_quick_action.up.sql

```sql
-- Quick-action-triggered comments (MUL-5465).
--
-- A quick action posts an ORDINARY comment (type stays 'comment') and marks it
-- with the action that produced it. The timeline renders the collapsed
-- one-line card off this column, not off a dedicated comment type.
--
-- Two reasons it is an id and NOT a new `type` value:
--
--   1. Adding a type meant dropping and re-adding comment_type_check, and
--      re-adding a CHECK takes ACCESS EXCLUSIVE on `comment` while it scans
--      the whole table. `comment` is one of the hottest tables in the product,
--      so that is a read/write stall for every deploy. Adding a nullable
--      column with no default is metadata-only and instant.
--
--   2. `type` is client-supplied on the generic POST /comments path, so any
--      member could post type='quick_action' and have an ordinary comment
--      render as an action audit record with its body collapsed out of view.
--      There is no request field for quick_action_id — only the quick-action
--      run path sets it — so this marker cannot be forged.
--
-- No FK per repo policy: actions archive rather than delete, and the render
-- path treats an unresolvable id as an ordinary comment.
ALTER TABLE comment ADD COLUMN IF NOT EXISTS quick_action_id UUID;

```

## server/go/migrations/240_agent_task_regenerate_quick_actions.up.sql

```sql
ALTER TABLE agent_task_queue
ADD COLUMN IF NOT EXISTS regenerate_quick_actions_for UUID;

```

## server/go/migrations/241_comment_parent_lookup_index.up.sql

```sql
-- Recursive thread expansion repeatedly looks up same-tenant children by
-- parent_id. Keep this as the migration's only statement: production index
-- builds must be concurrent so comment writes remain available.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_comment_workspace_issue_parent
    ON comment (workspace_id, issue_id, parent_id)
    WHERE parent_id IS NOT NULL;

```

## server/go/migrations/242_runtime_profile_add_qoderclicn.up.sql

```sql
-- Add Qoder CN CLI (`qoderclicn`) as a protocol family. It reuses the Qoder
-- ACP backend while retaining a distinct command, account, and config root.
-- NOT VALID preserves the historical-row tolerance used by prior family
-- additions.
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen'
    )) NOT VALID;

```

## server/go/migrations/243_workspace_teardown_dirty_trigger_guard.up.sql

```sql
-- Workspace teardown removes the raw and rolled-up usage for the entire
-- workspace, so per-row dirty-key maintenance is pure overhead in that one
-- transaction. Keep normal deletes unchanged while allowing the application
-- deletion plan to opt out with a transaction-local setting.

DROP TRIGGER IF EXISTS trg_atq_dirty_hourly ON agent_task_queue;
CREATE TRIGGER trg_atq_dirty_hourly
BEFORE UPDATE OF runtime_id, issue_id OR DELETE ON agent_task_queue
FOR EACH ROW
WHEN (current_setting('workpal.workspace_teardown', true) IS DISTINCT FROM 'on')
EXECUTE FUNCTION enqueue_task_usage_hourly_dirty_for_atq();

DROP TRIGGER IF EXISTS trg_issue_delete_dirty_hourly ON issue;
CREATE TRIGGER trg_issue_delete_dirty_hourly
BEFORE DELETE ON issue
FOR EACH ROW
WHEN (current_setting('workpal.workspace_teardown', true) IS DISTINCT FROM 'on')
EXECUTE FUNCTION enqueue_task_usage_hourly_dirty_for_issue_delete();

DROP TRIGGER IF EXISTS trg_tu_dirty_hourly ON task_usage;
CREATE TRIGGER trg_tu_dirty_hourly
BEFORE DELETE ON task_usage
FOR EACH ROW
WHEN (current_setting('workpal.workspace_teardown', true) IS DISTINCT FROM 'on')
EXECUTE FUNCTION enqueue_task_usage_hourly_dirty_for_tu();

```

## server/go/migrations/244_issue_dependency_issue_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_dependency_issue_id
    ON issue_dependency(issue_id);

```

## server/go/migrations/245_issue_dependency_depends_on_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_dependency_depends_on_issue_id
    ON issue_dependency(depends_on_issue_id);

```

## server/go/migrations/246_inbox_item_issue_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inbox_item_issue_id
    ON inbox_item(issue_id);

```

## server/go/migrations/247_comment_parent_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_comment_parent_id
    ON comment(parent_id)
    WHERE parent_id IS NOT NULL;

```

## server/go/migrations/248_agent_task_trigger_comment_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_trigger_comment_id
    ON agent_task_queue(trigger_comment_id)
    WHERE trigger_comment_id IS NOT NULL;

```

## server/go/migrations/249_issue_subscriber_delegated.up.sql

```sql
-- MUL-5483: an agent creating an issue on a human's behalf must carry that
-- human's visibility with it.
--
-- Two changes, both required by the same rule ("delegation preserves
-- accountability, so it must preserve visibility"):
--
-- 1. reason='delegated' — a new provenance label for "your agent created this
--    on your behalf". It is deliberately NOT folded into 'creator': the DB
--    creator really is the agent, and the notification tier for a delegated
--    subscription is narrower than a direct one (see notification_listeners.go
--    delegatedNotifTypes). A distinct reason is what lets the UI explain the
--    subscription and lets delivery treat it differently.
--
-- 2. unsubscribed_at — an explicit opt-out tombstone. Until now unsubscribing
--    was row ABSENCE, which was survivable only because auto-subscribe rules
--    fired rarely. The delegated rule fires on every agent-created issue, so a
--    deleted row would be silently re-created by the next rule pass and
--    unsubscribe would not stick. Auto-subscribe uses ON CONFLICT DO NOTHING,
--    so a tombstoned row is never resurrected by a rule; only an explicit user
--    subscribe clears it.
-- The CHECK is only WIDENED (one new allowed value), so every existing row
-- already satisfies it. A plain ADD CONSTRAINT would still hold ACCESS
-- EXCLUSIVE on issue_subscriber for a full scan, blocking subscriber reads and
-- writes on a hot table for the duration. Use the two-step NOT VALID +
-- VALIDATE CONSTRAINT pattern from migration 060: the add takes the strong
-- lock only briefly (no scan), and VALIDATE does the scan under SHARE UPDATE
-- EXCLUSIVE, which does not block concurrent reads or writes. The constraint
-- still ends up fully validated, so no un-trusted constraint is left behind.
ALTER TABLE issue_subscriber DROP CONSTRAINT IF EXISTS issue_subscriber_reason_check;
ALTER TABLE issue_subscriber ADD CONSTRAINT issue_subscriber_reason_check
    CHECK (reason IN ('creator', 'assignee', 'commenter', 'mentioned', 'manual', 'autopilot', 'delegated')) NOT VALID;
ALTER TABLE issue_subscriber VALIDATE CONSTRAINT issue_subscriber_reason_check;

-- Nullable, no default, so this is a catalog-only change in PostgreSQL 11+
-- and does not rewrite the table.
ALTER TABLE issue_subscriber ADD COLUMN unsubscribed_at TIMESTAMPTZ;

```

## server/go/migrations/250_issue_subscriber_opt_out_scope.up.sql

```sql
-- MUL-5483 review follow-up: an opt-out has to remember HOW FAR it reaches.
--
-- 249 gave every unsubscribe a tombstone, and HasAncestorOptOut treats any
-- ancestor tombstone as "do not re-subscribe below here". That made the two UI
-- choices — "unsubscribe from this issue" and "…and its sub-issues" — differ
-- only for descendants that already exist: both silently suppressed FUTURE
-- children. Recording the scope is what makes the narrow choice actually narrow.
--
-- NULL means "not opted out" (the row is an active subscription). Only a
-- tombstoned row carries a scope.
ALTER TABLE issue_subscriber ADD COLUMN opt_out_scope TEXT
    CHECK (opt_out_scope IN ('issue', 'subtree'));

-- Rows tombstoned by 249 predate the distinction. They were all written by a
-- path that suppressed future children, so 'subtree' preserves their observed
-- behavior rather than silently widening or narrowing it.
UPDATE issue_subscriber SET opt_out_scope = 'subtree' WHERE unsubscribed_at IS NOT NULL;

```

## server/go/migrations/251_agent_runtime_unbind.up.sql

```sql
-- Migration 251 (MUL-5559): deleting a runtime unbinds its agents instead of
-- destroying them.
--
-- Before this migration an agent physically could not exist without a runtime
-- (agent.runtime_id NOT NULL), so the runtime-delete flow had no third option:
-- it archived the runtime's agents and then hard-deleted the rows, taking their
-- chat sessions with them. The confirmation dialog called that "archive", which
-- is not what the user got — the agents and every conversation with them were
-- gone. Retiring a laptop is an ordinary action; losing the agents configured
-- on it is not an ordinary consequence.
--
-- Two columns become nullable, not one:
--
--   1. agent.runtime_id — NULL now means "unbound": the agent, its
--      instructions, skills, chats, labels, channel installations and
--      autopilot config all survive, it simply cannot run until it is bound to
--      a runtime again. Unbound is orthogonal to archived.
--      AgentReadiness already refuses an agent with no runtime, so the
--      scheduling safety gate needs no change.
--
--   2. agent_task_queue.runtime_id — without this, unbinding the agent would
--      still lose its whole task history: that column is NOT NULL with an
--      ON DELETE CASCADE FK, which cascades further into task_message,
--      task_usage and task_token. ReassignTasksToRuntime already documents the
--      same trap for the legacy-daemon merge path ("Required before deleting
--      the old runtime row because agent_task_queue has an ON DELETE CASCADE
--      FK that would otherwise drop historical tasks"). The delete transaction
--      now nulls these rows explicitly, so the cascade never fires.
--
-- No new foreign keys or cascading actions are introduced (repository rule):
-- the unbind itself is an explicit application-layer UPDATE inside the same
-- transaction as the runtime delete. The pre-existing CASCADE on
-- agent_task_queue.runtime_id is left in place but is now inert on this path —
-- it stays as the last-resort guarantee that no row can reference a runtime
-- that no longer exists.
--
-- The CHECK is the invariant that keeps NULL confined to history: an ACTIVE
-- task must always have a runtime, so claim / dispatch / delivery-CAS paths can
-- never observe runtime_id IS NULL. It is expressed with completed_at rather
-- than a status list because every terminal transition stamps completed_at
-- (CompleteAgentTask / FailAgentTask / the five cancel queries), and because
-- naming enumerable status values in a constraint would force a migration for
-- each new status. A future non-terminal status therefore fails closed — it
-- must carry a runtime — instead of silently slipping through.
--
-- NOT VALID keeps this a metadata-only add on a hot table (no ACCESS EXCLUSIVE
-- full-table scan); PostgreSQL still enforces it on every INSERT and UPDATE
-- from this point on, which is exactly what the invariant needs. Existing rows
-- all satisfy it (runtime_id was NOT NULL until now), so there is nothing to
-- back-fill; a later migration can VALIDATE it during a quiet window.

ALTER TABLE agent
    ALTER COLUMN runtime_id DROP NOT NULL;

ALTER TABLE agent_task_queue
    ALTER COLUMN runtime_id DROP NOT NULL;

ALTER TABLE agent_task_queue
    ADD CONSTRAINT agent_task_queue_active_requires_runtime
    CHECK (runtime_id IS NOT NULL OR completed_at IS NOT NULL)
    NOT VALID;

-- Runtime deletion pauses affected automations so a schedule cannot append one
-- identical skipped run on every tick forever. The reason is persisted
-- separately from status: clients can explain the recoverable condition, and a
-- user can rebind the agent then resume the unchanged automation.
ALTER TABLE autopilot
    ADD COLUMN pause_reason TEXT;

```

## server/go/migrations/252_agent_builder_draft.up.sql

```sql
-- The agent configuration a creation conversation has arrived at.
--
-- Half of this state was already durable: every reply from the builder ends in
-- an <agent_draft> block, so the client could always replay the last one out of
-- chat_message. What was not durable is the half the USER types — a rewritten
-- instruction, an unticked skill — which lived only in React state and died on
-- every reload, tab switch and navigation. Splitting one configuration across
-- "the AI's half on the server, yours in the browser" also forced the client to
-- arbitrate between the two on every restore. This table makes the whole thing
-- one server-owned object.
--
-- `draft` is opaque to the server. The shape is the studio's AgentDraft and is
-- validated client-side against a zod schema; teaching Postgres and the handler
-- about it would create a second definition to keep in sync for no gain, since
-- nothing server-side ever reads a field. The client also stores which
-- assistant message it has already applied, so a restore does not re-apply the
-- last reply over edits made after it.
--
-- No foreign key (repo rule), so deletion is explicit in application code —
-- DeleteChatSession, the runtime teardown agent cascade, and the workspace
-- teardown each prune this table, exactly as they already do for
-- chat_draft_restore.
--
-- chat_session_id is the primary key rather than a surrogate id: a conversation
-- has exactly one current draft, and making that a constraint means the write
-- path is a plain upsert with no room for duplicate rows to accumulate. It also
-- provides the lookup index, so no separate CREATE INDEX CONCURRENTLY is needed.
CREATE TABLE agent_builder_draft (
    chat_session_id UUID PRIMARY KEY,
    -- Denormalised so the workspace teardown can prune without joining through
    -- chat_session, which that statement deletes in the same CTE.
    workspace_id    UUID NOT NULL,
    draft           JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/253_runtime_profile_add_qwenpaw.up.sql

```sql
-- Add QwenPaw (`qwenpaw`) to the built-in runtime profile protocol whitelist.
-- Kept in lockstep with agent.SupportedTypes and agent.New().  NOT VALID
-- preserves the historical-row tolerance used by the prior family additions.
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw'
    )) NOT VALID;

```

## server/go/migrations/254_runtime_profile_add_reasonix.up.sql

```sql
-- Add Reasonix as a first-party ACP protocol family. NOT VALID preserves
-- historical-row tolerance while enforcing the expanded whitelist for new rows.
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'reasonix',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw'
    )) NOT VALID;

```

## server/go/migrations/255_agent_task_queue_chat_pending_deferred_v3.up.sql

```sql
-- Extend the pending-chat partial index to deferred retries (MUL-5750).
--
-- The session pending endpoint now treats a deferred retry as a visible head,
-- and the workspace FAB aggregate must use the same in-flight status set.
-- Migration 143's v2 predicate covers only the four immediately runnable or
-- claimed statuses, so PostgreSQL cannot use it for the five-status aggregate.
--
-- Build v3 before dropping v2 so old and new server versions both retain a
-- usable index throughout a rolling deploy. The old four-status queries are a
-- subset of this predicate and can use v3 safely. This file stays a single
-- statement because CREATE INDEX CONCURRENTLY cannot run in a transaction or
-- a multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_chat_pending_v3
    ON agent_task_queue (chat_session_id, created_at DESC)
    WHERE chat_session_id IS NOT NULL
      AND status IN ('queued', 'dispatched', 'running', 'waiting_local_directory', 'deferred');

```

## server/go/migrations/256_drop_agent_task_queue_chat_pending_v2.up.sql

```sql
-- Drop the superseded four-status partial index after v3 is available.
--
-- Kept separate from migration 254 so both files contain exactly one
-- concurrent index statement and no rollout window is left without coverage.
DROP INDEX CONCURRENTLY IF EXISTS idx_agent_task_queue_chat_pending_v2;

```

## server/go/migrations/257_agent_task_queue_channel_media_pending_unique_v2.up.sql

```sql
-- Build v2 before dropping v1 so queued/dispatched uniqueness remains enforced
-- throughout rolling deploys and interrupted migration runs. The v1 predicate
-- is a strict subset of v2, so both indexes can coexist safely. This file stays
-- a single statement because CREATE INDEX CONCURRENTLY cannot run in a
-- transaction or a multi-command string.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_one_pending_task_per_issue_agent_v2
    ON agent_task_queue (issue_id, agent_id)
    WHERE status IN ('queued', 'dispatched')
       OR (status = 'deferred' AND context->>'channel_issue_media_pending' = 'true');

```

## server/go/migrations/258_drop_pending_issue_agent_v1.up.sql

```sql
-- Drop the superseded queued/dispatched-only index after v2 is available.
DROP INDEX CONCURRENTLY IF EXISTS idx_one_pending_task_per_issue_agent;

```

## server/go/migrations/259_issue_origin_dingtalk_chat.up.sql

```sql
-- Extend issue.origin_type for issues created through DingTalk's /issue
-- command. The shared channel Router stamps origin_type='dingtalk_chat' and
-- origin_id=<chat_session.id>; without this CHECK entry every DingTalk issue
-- creation fails with SQLSTATE 23514.
--
-- The CHECK is only WIDENED (one new allowed value), so every existing row
-- already satisfies it. Add it NOT VALID so this statement takes ACCESS
-- EXCLUSIVE on issue only briefly, without a full-table scan; migration 260
-- runs the VALIDATE under SHARE UPDATE EXCLUSIVE, which does not block reads
-- or writes. issue is a hot core table, so a plain validating ADD here would
-- block all traffic on it for the length of the scan.
--
-- Keep the VALIDATE in its own migration file (the 197/198 pattern), NOT
-- merely as a later statement in this one: the migration runner hands each
-- file to a single conn.Exec, so every statement in a file shares one implicit
-- transaction and the ACCESS EXCLUSIVE taken here would be held until the file
-- finishes — carrying the strong lock straight through the validation scan and
-- defeating the split.
ALTER TABLE issue DROP CONSTRAINT IF EXISTS issue_origin_type_check;
ALTER TABLE issue ADD CONSTRAINT issue_origin_type_check
    CHECK (origin_type IN ('autopilot', 'quick_create', 'lark_chat', 'slack_chat', 'agent_create', 'dingtalk_chat'))
    NOT VALID;

```

## server/go/migrations/260_issue_origin_dingtalk_chat_validate.up.sql

```sql
-- Validate the widened issue_origin_type_check that migration 259 added
-- NOT VALID. This takes SHARE UPDATE EXCLUSIVE while scanning issue, which
-- permits normal SELECT/INSERT/UPDATE/DELETE traffic to continue — the whole
-- point of splitting the two steps across migration files (the 197/198
-- pattern).
--
-- 259 only WIDENED the allowed set, so every pre-existing row already
-- satisfies the constraint and this scan cannot fail on legacy data.
ALTER TABLE issue VALIDATE CONSTRAINT issue_origin_type_check;

```

## server/go/migrations/261_agent_task_queue_terminal_completed_at_v2.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- Supersedes idx_agent_task_queue_terminal_completed_at (migration 231). The
-- run-time rollups now also count runs the user stopped mid-flight, so their
-- status filter reads `IN ('completed','failed','cancelled')`. A partial
-- index is only usable when the planner can prove the query's predicate
-- implies the index predicate, and the v1 two-status predicate cannot cover
-- a three-status filter — leaving those rollups on a full scan of a table
-- whose lifetime row count dwarfs any 30-day window.
--
-- Widening the predicate rather than dropping it keeps the index off the
-- queued / dispatched / running rows that the hot dispatch path churns: a
-- row still enters this index exactly once, when it reaches a terminal state.
--
-- The two failure rollups (ListDashboardFailuresDaily / ...ByAgent) keep the
-- two-status filter on purpose — a manual stop is not a failure and must not
-- dilute the error rate. They stay index-eligible regardless, since their
-- narrower predicate implies this wider one.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_terminal_completed_at_v2
    ON agent_task_queue (completed_at)
    WHERE status IN ('completed', 'failed', 'cancelled');

```

## server/go/migrations/262_drop_agent_task_queue_terminal_completed_at_v1.up.sql

```sql
-- Drop the superseded two-status partial index now that v2 is available.
--
-- Kept separate from migration 261 so both files contain exactly one
-- concurrent index statement and no rollout window is left without coverage.
DROP INDEX CONCURRENTLY IF EXISTS idx_agent_task_queue_terminal_completed_at;

```

## server/go/migrations/263_issue_origin_wecom_chat.up.sql

```sql
-- Extend issue.origin_type to allow the WeCom smart-bot (aibot) `/issue`
-- command path to stamp issues with origin_type='wecom_chat' + origin_id=
-- <chat_session.id>. Mirrors 111_issue_origin_lark_chat and
-- 131_issue_origin_slack_chat — same origin_id semantics (the chat_session
-- the /issue command was typed in), different label because analytics and
-- inbound routing key on this string.
--
-- The full list is respecified (not just appended) because ADD CONSTRAINT
-- cannot append a value. It must therefore carry every value added by earlier
-- migrations — including 'dingtalk_chat' (migration 259) — or this rebuild
-- would silently drop it. Keep this list in sync with the newest
-- issue_origin_* migration when rebasing.
--
-- The CHECK is only WIDENED (one new allowed value), so every existing row
-- already satisfies it. Add it NOT VALID so this statement takes ACCESS
-- EXCLUSIVE on issue only briefly, without a full-table scan; migration 264
-- runs the VALIDATE under SHARE UPDATE EXCLUSIVE, which does not block reads
-- or writes. issue is a hot core table, so a plain validating ADD here would
-- block all traffic on it for the length of the scan.
--
-- Keep the VALIDATE in its own migration file (the 259/260 pattern), NOT
-- merely as a later statement in this one: the migration runner hands each
-- file to a single conn.Exec, so every statement in a file shares one implicit
-- transaction and the ACCESS EXCLUSIVE taken here would be held until the file
-- finishes — carrying the strong lock straight through the validation scan and
-- defeating the split.
ALTER TABLE issue DROP CONSTRAINT IF EXISTS issue_origin_type_check;
ALTER TABLE issue ADD CONSTRAINT issue_origin_type_check
    CHECK (origin_type IN ('autopilot', 'quick_create', 'lark_chat', 'slack_chat', 'agent_create', 'dingtalk_chat', 'wecom_chat'))
    NOT VALID;

```

## server/go/migrations/264_issue_origin_wecom_chat_validate.up.sql

```sql
-- Validate the widened issue_origin_type_check that migration 263 added
-- NOT VALID. This takes SHARE UPDATE EXCLUSIVE while scanning issue, which
-- permits normal SELECT/INSERT/UPDATE/DELETE traffic to continue — the whole
-- point of splitting the two steps across migration files (the 259/260
-- pattern).
--
-- 263 only WIDENED the allowed set, so every pre-existing row already
-- satisfies the constraint and this scan cannot fail on legacy data.
ALTER TABLE issue VALIDATE CONSTRAINT issue_origin_type_check;

```

## server/go/migrations/265_issue_view.up.sql

```sql
-- Saved issue views: named, server-backed filter definitions with display
-- defaults. `query` (filters) is the shared identity of the view; `display`
-- (layout/grouping/sort/card fields) only seeds the first open and is
-- overridden per user locally. No FKs or cascades by repository policy —
-- lifecycle cleanup is handled in application transactions (project delete,
-- member removal).
CREATE TABLE issue_view (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    owner_id UUID NOT NULL,
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    scope_type TEXT NOT NULL CHECK (scope_type IN ('workspace', 'my', 'project')),
    scope_id UUID,
    scope_variant TEXT CHECK (scope_variant IN ('assigned', 'created', 'involved', 'any')),
    visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private', 'workspace')),
    definition_version INTEGER NOT NULL DEFAULT 1,
    query JSONB NOT NULL CHECK (jsonb_typeof(query) = 'object'),
    display JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(display) = 'object'),
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- scope_id carries the project id for project views and must be absent
    -- elsewhere; scope_variant is meaningful only for My Issues views.
    CHECK (
        (scope_type = 'project' AND scope_id IS NOT NULL)
        OR (scope_type IN ('workspace', 'my') AND scope_id IS NULL)
    ),
    CHECK (
        (scope_type = 'my' AND scope_variant IS NOT NULL)
        OR (scope_type <> 'my' AND scope_variant IS NULL)
    ),
    -- My Issues is inherently personal; sharing it would leak a per-user
    -- perspective that renders differently for every member.
    CHECK (scope_type <> 'my' OR visibility = 'private')
);

```

## server/go/migrations/266_issue_view_owner_index.up.sql

```sql
-- List query shape: workspace_id + scope columns, then either "mine" or
-- "shared with workspace" (OR of two branches — see 256 for the shared
-- branch; the planner combines them via BitmapOr). Kept as its own
-- single-statement file: concurrent index builds cannot run inside a
-- transaction or a multi-command migration.
CREATE INDEX CONCURRENTLY idx_issue_view_owner
    ON issue_view (workspace_id, scope_type, scope_id, owner_id);

```

## server/go/migrations/267_issue_view_shared_index.up.sql

```sql
-- Partial index for the "shared with workspace" branch of the list query.
CREATE INDEX CONCURRENTLY idx_issue_view_shared
    ON issue_view (workspace_id, scope_type, scope_id)
    WHERE visibility = 'workspace';

```

## server/go/migrations/268_issue_view_preference.up.sql

```sql
-- Per-user view-bar preferences for one surface container: which items
-- (built-in tabs and saved views) are hidden and in what order they render.
-- `prefs` is a small client-owned doc: { "hidden": [...], "order": [...] }
-- with item ids like "builtin:all" / "view:<uuid>". Single-user data —
-- last-write-wins, no revision. scope_id is backfilled (workspace id for
-- workspace scope, user id for my scope, project id for project scope) so
-- the composite primary key never depends on NULL. No FKs by repository
-- policy; the member-revoke transaction deletes these rows explicitly.
CREATE TABLE issue_view_preference (
    workspace_id UUID NOT NULL,
    user_id UUID NOT NULL,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('workspace', 'my', 'project')),
    scope_id UUID NOT NULL,
    prefs JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(prefs) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id, scope_type, scope_id)
);

```

## server/go/migrations/269_issue_view_workspace_variant.up.sql

```sql
-- Workspace views gain an optional scope_variant mirroring the built-in
-- Members / Agents tabs — the same "which tab" concept my-views already
-- persist. NULL means the unrestricted All tab; a set value narrows the
-- view's scope to that assignee type (injected as scope-level
-- assignee_types at query time). Project views share the same optional
-- vocabulary: the project pages carry the same Members / Agents tabs.
ALTER TABLE issue_view
    DROP CONSTRAINT issue_view_scope_variant_check,
    DROP CONSTRAINT issue_view_check1;

ALTER TABLE issue_view
    ADD CONSTRAINT issue_view_scope_variant_check CHECK (
        scope_variant IN ('assigned', 'created', 'involved', 'any', 'members', 'agents')
    ),
    ADD CONSTRAINT issue_view_scope_variant_pairing CHECK (
        (scope_type = 'my' AND scope_variant IN ('assigned', 'created', 'involved', 'any'))
        OR (scope_type = 'workspace' AND (scope_variant IS NULL OR scope_variant IN ('members', 'agents')))
        OR (scope_type = 'project' AND (scope_variant IS NULL OR scope_variant IN ('members', 'agents')))
    );

```

## server/go/migrations/270_pinned_item_view.up.sql

```sql
-- Saved issue views become pinnable to the sidebar alongside issues and
-- projects. The pin row stores only (item_type, item_id); display data is
-- resolved client-side from the view detail endpoint.
ALTER TABLE pinned_item DROP CONSTRAINT pinned_item_item_type_check;
ALTER TABLE pinned_item ADD CONSTRAINT pinned_item_item_type_check
    CHECK (item_type IN ('issue', 'project', 'view'));

```

## server/go/migrations/271_channel_chat_pending_fresh.up.sql

```sql
ALTER TABLE channel_chat_session_binding
ADD COLUMN pending_fresh BOOLEAN NOT NULL DEFAULT FALSE;

```

## server/go/migrations/272_rollup_task_usage_hourly_xact_lock.up.sql

```sql
-- Make the hourly rollup's advisory lock transaction-scoped.
--
-- Migration 102 took lock 4246 with the SESSION-scoped pg_try_advisory_lock
-- and released it explicitly on both the success path and an
-- `EXCEPTION WHEN OTHERS` path. Two PostgreSQL rules combine to make that
-- leak the lock forever:
--
--   1. OTHERS does not match query_canceled. A cancelled tick — statement
--      timeout, pg_cancel_backend, or pgx cancelling the query when the Go
--      context is done (the scheduler caps a tick at 25 min) — skips the
--      handler entirely, so pg_advisory_unlock never runs.
--   2. A session-level advisory lock does not honour transaction semantics:
--      it survives the rollback that follows.
--
-- pgxpool then hands the connection back to the pool still holding 4246, and
-- nothing releases it until that connection is recycled or the process exits.
--
-- The consequences are silent and unbounded: every later tick loses
-- pg_try_advisory_lock and returns 0 ("no work to do"), so usage aggregation
-- stops, and DeleteWorkspace — which waits on pg_advisory_xact_lock(4246) to
-- keep the rollup out of a workspace it is tearing down — blocks forever, so
-- deleting a workspace appears to do nothing at all (MUL-5983).
--
-- pg_try_advisory_xact_lock is released by the transaction end, including a
-- rollback from a cancelled statement, so no failure mode can leak it. The
-- function is called as a plain `SELECT rollup_task_usage_hourly()`, i.e. its
-- own implicit transaction, so the lock still covers exactly one tick.
--
-- The one behaviour change: the TTL prune at the end used to run after an
-- explicit unlock and now runs inside the locked transaction, so whatever it
-- costs is added to the window in which 4246 is unavailable — to the next
-- tick, to a backfill run, and to a workspace delete, which now waits on 4246
-- under a 10 s budget and answers 503 when it runs out. The prune is an
-- index-driven DELETE (task_usage_hourly_dirty.enqueued_at) with no row cap:
-- in steady state each tick already drains the queue and it deletes nothing,
-- but after a long pause it has a real backlog to clear. Watch rollup duration
-- and workspace-delete 503s together if that ever happens.
CREATE OR REPLACE FUNCTION rollup_task_usage_hourly()
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_lock_ok BOOLEAN;
    v_from    TIMESTAMPTZ;
    v_to      TIMESTAMPTZ;
    v_rows    BIGINT := 0;
BEGIN
    SELECT pg_try_advisory_xact_lock(4246) INTO v_lock_ok;
    IF NOT v_lock_ok THEN
        RETURN 0;
    END IF;

    BEGIN
        UPDATE task_usage_hourly_rollup_state
           SET last_run_started_at = now(),
               last_error          = NULL
         WHERE id = 1
        RETURNING watermark_at INTO v_from;

        -- Cap each tick at a one-day window. In steady state v_from is
        -- recent, so LEAST picks `now() - 5 min` and nothing changes. But
        -- if the worker was paused (incident, migration freeze) the
        -- watermark can fall far behind; without the cap a single catch-up
        -- tick would recompute a multi-week window in one statement while
        -- holding lock 4246, blocking every other tick. Capped, catch-up
        -- advances in bounded one-day steps over successive ticks.
        v_to := LEAST(now() - INTERVAL '5 minutes', v_from + INTERVAL '1 day');

        IF v_from < v_to THEN
            v_rows := rollup_task_usage_hourly_window(v_from, v_to);

            UPDATE task_usage_hourly_rollup_state
               SET watermark_at         = v_to,
                   last_run_finished_at = now(),
                   last_run_rows        = v_rows
             WHERE id = 1;
        ELSE
            UPDATE task_usage_hourly_rollup_state
               SET last_run_finished_at = now(),
                   last_run_rows        = 0
             WHERE id = 1;
        END IF;
    EXCEPTION WHEN OTHERS THEN
        UPDATE task_usage_hourly_rollup_state
           SET last_error           = SQLERRM,
               last_run_finished_at = now()
         WHERE id = 1;
        RAISE;
    END;

    -- TTL prune. Idempotent, and in steady state a no-op because each tick
    -- already drains the queue. It runs under the transaction-scoped lock —
    -- see the note at the top for what that costs after a long pause.
    PERFORM prune_task_usage_hourly_dirty();
    RETURN v_rows;
END;
$$;

```

## server/go/migrations/273_agent_task_queue_runtime_id_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- agent_task_queue has never carried a plain runtime_id index. Every existing
-- one is partial — idx_agent_task_queue_runtime_pending (004),
-- idx_agent_task_queue_claim_candidates (067),
-- idx_agent_task_queue_dispatched_prepare (125) — and a partial index is only
-- usable when the planner can prove the query predicate implies the index
-- predicate. Two all-status consumers therefore had no index at all:
--
--   1. Workspace teardown, which has to find every task belonging to a
--      workspace's runtimes regardless of status (MUL-5999).
--   2. The runtime_id foreign key itself. PostgreSQL does not index the
--      referencing side of a FK, so `DELETE FROM agent_runtime` runs its
--      ON DELETE CASCADE probe (`WHERE runtime_id = $1`) once per deleted
--      runtime row — with no usable index that is a full scan of the largest
--      table in the database per runtime, on the ordinary delete path too.
--
-- Cheap to carry: runtime_id is set on essentially every row, so this is a
-- one-entry-per-row btree with no maintenance beyond what the FK column
-- already implies.
--
-- The trailing id column is what makes teardown's keyset paging free: the sweep
-- pages with `runtime_id = $1 AND id > $cursor ORDER BY id`, and without id in
-- the index every page would have to read the runtime's whole task set and sort
-- it before applying LIMIT.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_runtime_id
    ON agent_task_queue (runtime_id, id);

```

## server/go/migrations/274_task_token_workspace_id_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- task_token has carried workspace_id NOT NULL since migration 108, but only
-- token_hash and task_id were indexed. Workspace teardown is the one consumer
-- that filters on workspace_id, and without this index it had no choice but to
-- scan the whole table (MUL-5999).
--
-- The column is also the natural key for any future per-tenant token audit, so
-- the index is not teardown-only.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_token_workspace_id
    ON task_token (workspace_id);

```

## server/go/migrations/275_task_token_agent_id_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- task_token.agent_id has been a NOT NULL FK since migration 108 with no index.
-- Two consumers need one:
--
--   1. Workspace teardown deletes tokens by agent as one of the three explicit
--      task_token paths (MUL-5999). It must not fall back on the agent_id
--      cascade, because the legacy FKs are documented as an expand-phase safety
--      net that a later contract removes.
--   2. The FK's own ON DELETE CASCADE probe, which PostgreSQL runs once per
--      deleted agent row — a full scan of task_token per agent without an index,
--      on the ordinary agent-delete path too.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_token_agent_id
    ON task_token (agent_id);

```

## server/go/migrations/276_chat_draft_restore_task_id_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- chat_draft_restore.task_id is an unindexed FK. Workspace teardown now deletes
-- drafts one bounded task batch at a time (MUL-5999), and without an index each
-- batch would scan the table; the FK's own ON DELETE SET NULL probe has the same
-- problem on every ordinary task delete.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_draft_restore_task_id
    ON chat_draft_restore (task_id);

```

## server/go/migrations/277_autopilot_run_task_id_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- autopilot_run.task_id is an unindexed FK with ON DELETE SET NULL, so today
-- every single agent_task_queue row deletion anywhere in the product makes
-- PostgreSQL run `UPDATE autopilot_run SET task_id = NULL WHERE task_id = $1`
-- with no index behind it. Workspace teardown detaches these references
-- explicitly per task batch (MUL-5999) and needs the index for the same reason.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_autopilot_run_task_id
    ON autopilot_run (task_id);

```

## server/go/migrations/278_agent_task_queue_agent_id_keyset_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- Workspace teardown pages a busy agent's tasks with
-- `agent_id = $1 AND id > $cursor ORDER BY id LIMIT n` (MUL-5999). The existing
-- idx_agent_task_queue_agent is (agent_id, status), which cannot produce id
-- order, so every page would read the agent's entire task set and sort it before
-- applying LIMIT — quadratic in the number of pages, which is exactly the busy
-- agent this issue is about.
--
-- (agent_id, status) stays: the hot dispatch and claim queries filter on status,
-- and this index does not serve them.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_agent_id_keyset
    ON agent_task_queue (agent_id, id);

```

## server/go/migrations/279_agent_task_queue_issue_id_keyset_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- Same keyset-paging reason as migration 278, for teardown's issue path.
--
-- This makes idx_agent_task_queue_issue_id (migration 035) redundant: a btree on
-- (issue_id, id) serves every `issue_id = $1` predicate that the single-column
-- index served, and additionally produces id order. The old index is left in
-- place deliberately. Dropping it needs its own migration with a
-- direction-aware INVALID-index cleanup, because the down path of such a drop
-- is a CREATE INDEX CONCURRENTLY. An interrupted rollback would otherwise leave
-- no usable issue_id index at all.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_issue_id_keyset
    ON agent_task_queue (issue_id, id);

```

## server/go/migrations/281_agent_workspace_id_keyset_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- Workspace teardown enumerates the workspace's agents in bounded pages —
-- `workspace_id = $1 AND id > $cursor ORDER BY id LIMIT n` — so a workspace with
-- a very large owner set never has its whole id list held in the API process
-- (MUL-5999). The existing single-column workspace_id index cannot produce id
-- order, which would put a Sort over the entire owner set in front of every page.
--
-- id rather than a natural key on purpose: a keyset column has to be immutable,
-- and renaming an agent row mid-teardown would otherwise let it sort behind the
-- cursor and escape the sweep.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_workspace_id_keyset
    ON agent (workspace_id, id);

```

## server/go/migrations/282_issue_workspace_id_keyset_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- Workspace teardown enumerates the workspace's issues in bounded pages —
-- `workspace_id = $1 AND id > $cursor ORDER BY id LIMIT n` — so a workspace with
-- a very large owner set never has its whole id list held in the API process
-- (MUL-5999). The existing single-column workspace_id index cannot produce id
-- order, which would put a Sort over the entire owner set in front of every page.
--
-- id rather than a natural key on purpose: a keyset column has to be immutable,
-- and renaming an issue row mid-teardown would otherwise let it sort behind the
-- cursor and escape the sweep.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_workspace_id_keyset
    ON issue (workspace_id, id);

```

## server/go/migrations/283_agent_runtime_workspace_id_keyset_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- Workspace teardown enumerates the workspace's runtimes in bounded pages —
-- `workspace_id = $1 AND id > $cursor ORDER BY id LIMIT n` — so a workspace with
-- a very large owner set never has its whole id list held in the API process
-- (MUL-5999). The existing single-column workspace_id index cannot produce id
-- order, which would put a Sort over the entire owner set in front of every page.
--
-- id rather than a natural key on purpose: a keyset column has to be immutable,
-- and renaming an agent_runtime row mid-teardown would otherwise let it sort behind the
-- cursor and escape the sweep.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_runtime_workspace_id_keyset
    ON agent_runtime (workspace_id, id);

```

## server/go/migrations/284_task_owner_row_fence.up.sql

```sql
-- The write half of workspace teardown's concurrency contract, and of the legacy
-- runtime merge's (MUL-5999).
--
-- THE WINDOWS
--
-- Two deletes remove rows a task write depends on, and both would otherwise strand
-- or silently drop a task that arrives while they run:
--
--   1. Workspace teardown sweeps a workspace's tasks and then commits. A task
--      inserted between the last sweep and COMMIT would be left behind with its own
--      leaf rows, owned by rows that no longer exist.
--   2. The legacy runtime merge moves an old runtime's tasks onto a new one and then
--      deletes the old runtime. A task inserted against the OLD runtime after that
--      scan is deleted by agent_task_queue's ON DELETE CASCADE when the old runtime
--      goes — it was never a task anyone chose to discard.
--
-- Re-scanning cannot close either: the check and the commit are not atomic with
-- respect to a concurrent writer, so a row can always land after the final scan.
--
-- WHAT THIS IS
--
-- A predicate that every statement writing agent_task_queue ownership calls in its
-- own WHERE clause:
--
--     INSERT INTO agent_task_queue (...)
--     SELECT ... WHERE lock_task_owner_rows(@agent_id, @issue_id, @runtime_id)
--
-- It locks, in a fixed order, the workspace rows behind the row's agent, issue and
-- runtime, and then those owner rows themselves — all FOR KEY SHARE — and returns
-- false unless every owner reference still resolves afterwards.
--
--   * FOR KEY SHARE on the workspace conflicts with the FOR UPDATE that
--     LockWorkspaceForDelete holds for a whole teardown transaction.
--   * FOR KEY SHARE on the owner rows conflicts with the FOR UPDATE that the legacy
--     merge takes on the runtimes it is about to collapse (LockRuntimesForMerge),
--     and with the DELETE of any owner row.
--
-- So a task write racing either delete blocks until it finishes, and then either
-- proceeds (the delete rolled back) or writes no row (it committed). Locking the
-- workspace alone was not enough: the merge holds only KEY SHARE there, which does
-- not conflict with another KEY SHARE, so a writer sailed past it and had its task
-- cascade-deleted with the old runtime.
--
-- WHY A CALLED PREDICATE RATHER THAN A TRIGGER OR THE FOREIGN KEYS
--
--   * Not the foreign keys. An INSERT does take FOR KEY SHARE on the rows it
--     references, which is why these windows have been survivable so far — but that
--     is a side effect of FK enforcement, and workspace_delete.sql documents the
--     legacy FKs as an expand-phase net a later contract removes. Cleanup
--     correctness must not be a hostage of that migration.
--   * Not a trigger. A row trigger is a database-layer relational constraint that
--     coordinates application behaviour behind the caller's back. This repo keeps
--     relationships in the application layer, so the write path names its own
--     fence, and TestTaskOwnershipWritesCallTheFence fails the build if a statement
--     that writes ownership forgets to.
--   * It must be in the writer's transaction. Several enqueue statements run as
--     single autocommit statements, so a separate "take the fence" statement issued
--     by the caller would be its own transaction and release the lock before the
--     insert landed. Calling the predicate from the writing statement is
--     in-transaction by construction.
--
-- DETERMINISTIC LOCK ORDER
--
-- Workspaces first (ORDER BY id), then owners as agent, issue, runtime. Every
-- reader of this contract — writers, teardown, the merge — takes locks in that
-- order, so no two of them can hold each other's next lock. Within a step,
-- LockRows sits above Sort in the plan, so ORDER BY really does fix acquisition
-- order.
--
-- VOLATILE (the default) is load-bearing: it stops the planner from inlining the
-- body or optimising the call away, which would drop the locks.

CREATE OR REPLACE FUNCTION lock_task_owner_rows(
    p_agent_id uuid,
    p_issue_id uuid,
    p_runtime_id uuid
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    required int := (CASE WHEN p_agent_id IS NULL THEN 0 ELSE 1 END)
                  + (CASE WHEN p_issue_id IS NULL THEN 0 ELSE 1 END)
                  + (CASE WHEN p_runtime_id IS NULL THEN 0 ELSE 1 END);
    resolved int;
    distinct_workspaces int;
    locked int;
BEGIN
    -- A row with no owner reference at all cannot belong to any workspace.
    IF required = 0 THEN
        RETURN TRUE;
    END IF;

    WITH owners AS (
        SELECT a.workspace_id FROM agent a WHERE a.id = p_agent_id
        UNION ALL
        SELECT i.workspace_id FROM issue i WHERE i.id = p_issue_id
        UNION ALL
        SELECT r.workspace_id FROM agent_runtime r WHERE r.id = p_runtime_id
    )
    SELECT count(*), count(DISTINCT workspace_id)
    INTO resolved, distinct_workspaces
    FROM owners;

    -- An owner reference that no longer resolves means its row has been deleted —
    -- by a teardown or a merge that already committed, most likely. Refuse without
    -- leaning on the foreign key to report it.
    IF resolved <> required THEN
        RETURN FALSE;
    END IF;

    -- Step 1: the workspaces.
    WITH locked_workspaces AS (
        SELECT w.id
        FROM workspace w
        WHERE w.id IN (
            SELECT a.workspace_id FROM agent a WHERE a.id = p_agent_id
            UNION
            SELECT i.workspace_id FROM issue i WHERE i.id = p_issue_id
            UNION
            SELECT r.workspace_id FROM agent_runtime r WHERE r.id = p_runtime_id
        )
        ORDER BY w.id
        FOR KEY SHARE
    )
    SELECT count(*) INTO locked FROM locked_workspaces;

    IF locked <> distinct_workspaces THEN
        RETURN FALSE;
    END IF;

    -- Step 2: the owner rows, agent then issue then runtime. Re-checking existence
    -- here is what closes the merge window: whoever is deleting one of these rows
    -- holds FOR UPDATE on it, so this either waits for them or finds the row gone.
    locked := 0;

    IF p_agent_id IS NOT NULL THEN
        PERFORM 1 FROM agent WHERE id = p_agent_id FOR KEY SHARE;
        IF FOUND THEN locked := locked + 1; END IF;
    END IF;

    IF p_issue_id IS NOT NULL THEN
        PERFORM 1 FROM issue WHERE id = p_issue_id FOR KEY SHARE;
        IF FOUND THEN locked := locked + 1; END IF;
    END IF;

    IF p_runtime_id IS NOT NULL THEN
        PERFORM 1 FROM agent_runtime WHERE id = p_runtime_id FOR KEY SHARE;
        IF FOUND THEN locked := locked + 1; END IF;
    END IF;

    RETURN locked = required;
END;
$$;

```

## server/go/migrations/285_plugin_lifecycle_v1.up.sql

```sql
-- Plugin V1 lifecycle foundation.
--
-- This migration deliberately stores only the generic Plugin spine. The first
-- contribution adapter (agent.skill.v1), capability snapshots, and execution
-- manifests build on these objects in later migrations.
--
-- Relationships are application-owned by repository policy: there are no
-- foreign keys or cascades. Write queries resolve and lock parent rows, and the
-- workspace teardown deletes installation descendants explicitly.

CREATE TABLE plugin_identity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_key TEXT NOT NULL CHECK (char_length(plugin_key) BETWEEN 3 AND 255),
    display_name TEXT NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 160),
    publisher_id TEXT NOT NULL CHECK (char_length(publisher_id) BETWEEN 1 AND 255),
    publisher_type TEXT NOT NULL CHECK (
        publisher_type IN ('official', 'verified', 'community', 'private_dev')
    ),
    trust_tier TEXT NOT NULL CHECK (
        trust_tier IN ('official', 'verified', 'community', 'private_dev')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retired_at TIMESTAMPTZ
);

CREATE TABLE plugin_release (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_id UUID NOT NULL,
    version TEXT NOT NULL CHECK (char_length(version) BETWEEN 1 AND 128),
    manifest JSONB NOT NULL CHECK (jsonb_typeof(manifest) = 'object'),
    manifest_digest TEXT NOT NULL CHECK (manifest_digest ~ '^sha256:[0-9a-f]{64}$'),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('bundled', 'private_dev')),
    source_ref TEXT NOT NULL CHECK (char_length(source_ref) BETWEEN 1 AND 2048),
    archive_digest TEXT NOT NULL CHECK (archive_digest ~ '^sha256:[0-9a-f]{64}$'),
    artifact_ref TEXT NOT NULL CHECK (char_length(artifact_ref) BETWEEN 1 AND 2048),
    artifact_digest TEXT NOT NULL CHECK (artifact_digest ~ '^sha256:[0-9a-f]{64}$'),
    artifact_size BIGINT NOT NULL CHECK (artifact_size BETWEEN 0 AND 33554432),
    signature BYTEA,
    signature_key_id TEXT,
    revocation_status TEXT NOT NULL DEFAULT 'active' CHECK (
        revocation_status IN ('active', 'revoked', 'quarantined')
    ),
    revoked_at TIMESTAMPTZ,
    revocation_reason TEXT,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((signature IS NULL) = (signature_key_id IS NULL)),
    CHECK (source_kind <> 'bundled' OR signature IS NOT NULL),
    CHECK (
        (revocation_status = 'active' AND revoked_at IS NULL AND revocation_reason IS NULL)
        OR
        (revocation_status <> 'active' AND revoked_at IS NOT NULL AND char_length(revocation_reason) > 0)
    )
);

CREATE TABLE plugin_contribution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id UUID NOT NULL,
    contribution_key TEXT NOT NULL CHECK (char_length(contribution_key) BETWEEN 1 AND 128),
    type TEXT NOT NULL CHECK (type IN ('agent.skill.v1')),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    display_name TEXT NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 160),
    description TEXT NOT NULL,
    entry_path TEXT NOT NULL CHECK (char_length(entry_path) BETWEEN 1 AND 1024),
    entry_digest TEXT NOT NULL CHECK (entry_digest ~ '^sha256:[0-9a-f]{64}$'),
    artifact_digest TEXT NOT NULL CHECK (artifact_digest ~ '^sha256:[0-9a-f]{64}$'),
    required_daemon_features JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (
        jsonb_typeof(required_daemon_features) = 'array'
    ),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE plugin_installation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    plugin_id UUID NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('bundled', 'private_dev')),
    source_ref TEXT NOT NULL CHECK (char_length(source_ref) BETWEEN 1 AND 2048),
    desired_release_id UUID NOT NULL,
    active_release_id UUID,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    desired_generation BIGINT NOT NULL DEFAULT 1 CHECK (desired_generation > 0),
    active_generation BIGINT NOT NULL DEFAULT 0 CHECK (active_generation >= 0),
    lifecycle_status TEXT NOT NULL DEFAULT 'installed' CHECK (
        lifecycle_status IN (
            'installed', 'activating', 'active', 'degraded', 'error',
            'uninstalling', 'uninstalled'
        )
    ),
    installed_by UUID,
    installed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by UUID,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    disabled_at TIMESTAMPTZ,
    uninstalled_at TIMESTAMPTZ,
    CHECK (active_generation <= desired_generation),
    CHECK (active_generation > 0 OR active_release_id IS NULL),
    CHECK (
        (lifecycle_status = 'uninstalled' AND uninstalled_at IS NOT NULL AND enabled = FALSE)
        OR
        (lifecycle_status <> 'uninstalled' AND uninstalled_at IS NULL)
    )
);

-- Grants and bindings are append-only revision logs. A new decision inserts a
-- new revision; readers select the greatest revision per logical key.
CREATE TABLE plugin_grant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id UUID NOT NULL,
    capability TEXT NOT NULL CHECK (char_length(capability) BETWEEN 1 AND 255),
    decision TEXT NOT NULL CHECK (decision IN ('granted', 'denied')),
    limits JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(limits) = 'object'),
    grant_revision BIGINT NOT NULL CHECK (grant_revision > 0),
    approved_by UUID,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ
);

CREATE TABLE plugin_binding (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id UUID NOT NULL,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('workspace', 'agent')),
    scope_id UUID NOT NULL,
    enabled BOOLEAN NOT NULL,
    binding_revision BIGINT NOT NULL CHECK (binding_revision > 0),
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Release identity/content and contribution rows are immutable. Revocation is
-- the only release mutation and is a one-way transition out of active.
CREATE FUNCTION enforce_plugin_release_immutable()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.plugin_id IS DISTINCT FROM OLD.plugin_id
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.manifest IS DISTINCT FROM OLD.manifest
       OR NEW.manifest_digest IS DISTINCT FROM OLD.manifest_digest
       OR NEW.source_kind IS DISTINCT FROM OLD.source_kind
       OR NEW.source_ref IS DISTINCT FROM OLD.source_ref
       OR NEW.archive_digest IS DISTINCT FROM OLD.archive_digest
       OR NEW.artifact_ref IS DISTINCT FROM OLD.artifact_ref
       OR NEW.artifact_digest IS DISTINCT FROM OLD.artifact_digest
       OR NEW.artifact_size IS DISTINCT FROM OLD.artifact_size
       OR NEW.signature IS DISTINCT FROM OLD.signature
       OR NEW.signature_key_id IS DISTINCT FROM OLD.signature_key_id
       OR NEW.published_at IS DISTINCT FROM OLD.published_at THEN
        RAISE EXCEPTION 'plugin releases are immutable';
    END IF;

    IF OLD.revocation_status <> 'active' THEN
        RAISE EXCEPTION 'plugin release revocation is immutable';
    END IF;

    IF NEW.revocation_status = 'active' THEN
        RAISE EXCEPTION 'plugin release update must revoke or quarantine';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_plugin_release_immutable
BEFORE UPDATE ON plugin_release
FOR EACH ROW EXECUTE FUNCTION enforce_plugin_release_immutable();

CREATE FUNCTION reject_plugin_append_only_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% rows are append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER trg_plugin_contribution_append_only
BEFORE UPDATE ON plugin_contribution
FOR EACH ROW EXECUTE FUNCTION reject_plugin_append_only_update();

CREATE TRIGGER trg_plugin_grant_append_only
BEFORE UPDATE ON plugin_grant
FOR EACH ROW EXECUTE FUNCTION reject_plugin_append_only_update();

CREATE TRIGGER trg_plugin_binding_append_only
BEFORE UPDATE ON plugin_binding
FOR EACH ROW EXECUTE FUNCTION reject_plugin_append_only_update();

```

## server/go/migrations/286_plugin_identity_key_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_identity_key
    ON plugin_identity (plugin_key);

```

## server/go/migrations/287_plugin_release_version_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_release_version
    ON plugin_release (plugin_id, version);

```

## server/go/migrations/288_plugin_installation_workspace_plugin_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_installation_workspace_plugin_active
    ON plugin_installation (workspace_id, plugin_id)
    WHERE uninstalled_at IS NULL;

```

## server/go/migrations/289_plugin_contribution_key_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_contribution_release_key
    ON plugin_contribution (release_id, contribution_key);

```

## server/go/migrations/290_plugin_contribution_ordinal_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_contribution_release_ordinal
    ON plugin_contribution (release_id, ordinal);

```

## server/go/migrations/291_plugin_grant_revision_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_grant_revision
    ON plugin_grant (installation_id, capability, grant_revision);

```

## server/go/migrations/292_plugin_binding_revision_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_binding_revision
    ON plugin_binding (installation_id, scope_type, scope_id, binding_revision);

```

## server/go/migrations/293_plugin_installation_workspace_index.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_plugin_installation_workspace
    ON plugin_installation (workspace_id, id);

```

## server/go/migrations/294_plugin_snapshot_execution_v1.up.sql

```sql
-- Plugin V1 capability snapshots, task execution manifests, and immutable
-- artifact files. The workspace state row is the only mutable pointer: every
-- snapshot and execution manifest remains append-only for replay/audit.

CREATE TABLE plugin_artifact_file (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id UUID NOT NULL,
    path TEXT NOT NULL CHECK (char_length(path) BETWEEN 1 AND 1024),
    digest TEXT NOT NULL CHECK (digest ~ '^sha256:[0-9a-f]{64}$'),
    size_bytes BIGINT NOT NULL CHECK (size_bytes BETWEEN 0 AND 1048576),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (octet_length(content) = size_bytes)
);

CREATE TABLE plugin_workspace_capability_state (
    workspace_id UUID PRIMARY KEY,
    next_revision BIGINT NOT NULL DEFAULT 1 CHECK (next_revision > 0),
    active_snapshot_id UUID,
    active_revision BIGINT NOT NULL DEFAULT 0 CHECK (active_revision >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((active_snapshot_id IS NULL) = (active_revision = 0))
);

CREATE TABLE plugin_capability_snapshot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    revision BIGINT NOT NULL CHECK (revision > 0),
    source_generations JSONB NOT NULL CHECK (jsonb_typeof(source_generations) = 'object'),
    compiler_version TEXT NOT NULL CHECK (char_length(compiler_version) BETWEEN 1 AND 128),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    snapshot_digest TEXT NOT NULL CHECK (snapshot_digest ~ '^sha256:[0-9a-f]{64}$'),
    compiled_entries JSONB NOT NULL CHECK (jsonb_typeof(compiled_entries) = 'array'),
    diagnostics JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(diagnostics) = 'array'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE plugin_execution_manifest (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    runtime_id UUID NOT NULL,
    snapshot_id UUID,
    snapshot_revision BIGINT NOT NULL DEFAULT 0 CHECK (snapshot_revision >= 0),
    snapshot_digest TEXT,
    composer_version TEXT NOT NULL CHECK (char_length(composer_version) BETWEEN 1 AND 128),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    ordered_contributions JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (
        jsonb_typeof(ordered_contributions) = 'array'
    ),
    diagnostics JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(diagnostics) = 'array'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((snapshot_id IS NULL) = (snapshot_revision = 0)),
    CHECK ((snapshot_id IS NULL) = (snapshot_digest IS NULL)),
    CHECK (snapshot_digest IS NULL OR snapshot_digest ~ '^sha256:[0-9a-f]{64}$')
);

CREATE TABLE plugin_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    installation_id UUID NOT NULL,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('workspace', 'agent')),
    scope_id UUID,
    state TEXT NOT NULL CHECK (state IN ('healthy', 'degraded', 'error', 'disabled')),
    reason_code TEXT NOT NULL CHECK (char_length(reason_code) BETWEEN 1 AND 128),
    safe_detail TEXT NOT NULL DEFAULT '',
    observed_generation BIGINT NOT NULL CHECK (observed_generation > 0),
    last_good_snapshot_id UUID,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE agent_task_queue
    ADD COLUMN plugin_execution_manifest_id UUID;

CREATE TRIGGER trg_plugin_artifact_file_append_only
BEFORE UPDATE ON plugin_artifact_file
FOR EACH ROW EXECUTE FUNCTION reject_plugin_append_only_update();

CREATE TRIGGER trg_plugin_capability_snapshot_append_only
BEFORE UPDATE ON plugin_capability_snapshot
FOR EACH ROW EXECUTE FUNCTION reject_plugin_append_only_update();

CREATE TRIGGER trg_plugin_execution_manifest_append_only
BEFORE UPDATE ON plugin_execution_manifest
FOR EACH ROW EXECUTE FUNCTION reject_plugin_append_only_update();

CREATE TRIGGER trg_plugin_health_append_only
BEFORE UPDATE ON plugin_health
FOR EACH ROW EXECUTE FUNCTION reject_plugin_append_only_update();

CREATE FUNCTION pin_plugin_execution_manifest()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    workspace UUID;
    source_manifest plugin_execution_manifest%ROWTYPE;
    active_snapshot plugin_capability_snapshot%ROWTYPE;
    manifest_id UUID;
    contributions JSONB := '[]'::jsonb;
BEGIN
    SELECT agent.workspace_id INTO workspace
    FROM agent
    WHERE agent.id = NEW.agent_id;

    IF workspace IS NULL THEN
        RAISE EXCEPTION 'cannot compose plugin execution manifest without task workspace';
    END IF;

    IF NEW.retry_of_task_id IS NOT NULL THEN
        SELECT plugin_execution_manifest.* INTO source_manifest
        FROM agent_task_queue parent
        JOIN plugin_execution_manifest
          ON plugin_execution_manifest.id = parent.plugin_execution_manifest_id
        WHERE parent.id = NEW.retry_of_task_id;
    END IF;

    IF source_manifest.id IS NOT NULL THEN
        INSERT INTO plugin_execution_manifest (
            task_id, workspace_id, agent_id, runtime_id,
            snapshot_id, snapshot_revision, snapshot_digest,
            composer_version, schema_version,
            ordered_contributions, diagnostics
        ) VALUES (
            NEW.id, workspace, NEW.agent_id, NEW.runtime_id,
            source_manifest.snapshot_id,
            source_manifest.snapshot_revision,
            source_manifest.snapshot_digest,
            source_manifest.composer_version,
            source_manifest.schema_version,
            source_manifest.ordered_contributions,
            source_manifest.diagnostics
        ) RETURNING id INTO manifest_id;
    ELSE
        SELECT snapshot.* INTO active_snapshot
        FROM plugin_workspace_capability_state state
        JOIN plugin_capability_snapshot snapshot
          ON snapshot.id = state.active_snapshot_id
        WHERE state.workspace_id = workspace;

        IF active_snapshot.id IS NOT NULL THEN
            SELECT COALESCE(jsonb_agg(entry ORDER BY
                COALESCE((entry->>'ordinal')::integer, 0),
                entry->>'plugin_key',
                entry->>'contribution_key'
            ), '[]'::jsonb)
            INTO contributions
            FROM jsonb_array_elements(active_snapshot.compiled_entries) AS entry
            WHERE (
                entry->>'scope_type' = 'agent'
                AND entry->>'scope_id' = NEW.agent_id::text
            ) OR (
                entry->>'scope_type' = 'workspace'
                AND NOT COALESCE(entry->'excluded_agent_ids', '[]'::jsonb) ? NEW.agent_id::text
            );
        END IF;

        INSERT INTO plugin_execution_manifest (
            task_id, workspace_id, agent_id, runtime_id,
            snapshot_id, snapshot_revision, snapshot_digest,
            composer_version, schema_version,
            ordered_contributions, diagnostics
        ) VALUES (
            NEW.id, workspace, NEW.agent_id, NEW.runtime_id,
            active_snapshot.id,
            COALESCE(active_snapshot.revision, 0),
            active_snapshot.snapshot_digest,
            'plugin-composer-v1', 1,
            contributions, '[]'::jsonb
        ) RETURNING id INTO manifest_id;
    END IF;

    NEW.plugin_execution_manifest_id = manifest_id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_agent_task_queue_plugin_execution_manifest
BEFORE INSERT ON agent_task_queue
FOR EACH ROW EXECUTE FUNCTION pin_plugin_execution_manifest();

```

## server/go/migrations/295_plugin_artifact_file_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_artifact_file_release_path
    ON plugin_artifact_file (release_id, path);

```

## server/go/migrations/296_plugin_snapshot_revision_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_snapshot_workspace_revision
    ON plugin_capability_snapshot (workspace_id, revision);

```

## server/go/migrations/297_plugin_execution_task_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_execution_manifest_task
    ON plugin_execution_manifest (task_id);

```

## server/go/migrations/298_plugin_health_index.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_plugin_health_installation_observed
    ON plugin_health (installation_id, observed_at DESC);

```

## server/go/migrations/299_agent_task_plugin_manifest_index.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_agent_task_plugin_execution_manifest
    ON agent_task_queue (plugin_execution_manifest_id)
    WHERE plugin_execution_manifest_id IS NOT NULL;

```

## server/go/migrations/300_drop_redundant_issue_workspace_number_index.up.sql

```sql
DROP INDEX CONCURRENTLY IF EXISTS idx_issue_workspace_number;

```

## server/go/migrations/301_drop_redundant_sys_cron_job_plan_index.up.sql

```sql
DROP INDEX CONCURRENTLY IF EXISTS idx_sys_cron_exec_job_plan;

```

## server/go/migrations/302_drop_redundant_channel_chat_session_binding_index.up.sql

```sql
DROP INDEX CONCURRENTLY IF EXISTS idx_channel_chat_session_binding_session;

```

## server/go/migrations/303_drop_redundant_lark_chat_session_binding_index.up.sql

```sql
DROP INDEX CONCURRENTLY IF EXISTS idx_lark_chat_session_binding_session;

```

## server/go/migrations/304_dingtalk_group_route.up.sql

```sql
-- A DingTalk Stream robot can participate in multiple group conversations.
-- Keep the robot credentials on channel_installation and route each observed
-- group to its own Workpal agent. Relationships are application-owned; this
-- table intentionally has no foreign keys or inline unique constraints.
CREATE TABLE dingtalk_group_route (
    id                   UUID NOT NULL DEFAULT gen_random_uuid(),
    workspace_id         UUID NOT NULL,
    installation_id      UUID NOT NULL,
    conversation_id      TEXT NOT NULL,
    conversation_title   TEXT NOT NULL DEFAULT '',
    agent_id             UUID NOT NULL,
    revision             BIGINT NOT NULL DEFAULT 1,
    discovered_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/305_dingtalk_group_route_installation_conversation_unique.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_dingtalk_group_route_installation_conversation ON dingtalk_group_route(installation_id, conversation_id);

```

## server/go/migrations/306_dingtalk_group_route_workspace_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dingtalk_group_route_workspace ON dingtalk_group_route(workspace_id);

```

## server/go/migrations/307_dingtalk_group_route_id_unique.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_dingtalk_group_route_id_unique ON dingtalk_group_route(id);

```

## server/go/migrations/308_agent_task_branch_name.up.sql

```sql
-- Records the git branch a task delivered its work on.
--
-- Worktree-mode local_directory tasks hand their result back as a branch in the
-- user's own repo rather than as edits to the working copy, so the branch name
-- is the only pointer to where the work went. It is written on BOTH terminal
-- paths: a task that fails partway still commits whatever the agent produced,
-- and that is exactly when the user most needs to be told where to look.
--
-- Nullable and unindexed on purpose: only worktree tasks populate it, and it is
-- read alongside the task row that is already being fetched by primary key.
ALTER TABLE agent_task_queue ADD COLUMN IF NOT EXISTS branch_name TEXT;

-- Rollout / rollback note for worktree mode (MUL-5707).
--
-- Isolation for a worktree resource is enforced in two places, both of which
-- live in server code shipped with this migration: the save-time daemon-version
-- gate, and the claim-time gate that re-checks the runtime actually taking the
-- task. Those cover a daemon downgraded at any point after the resource was
-- created.
--
-- The one combination they cannot cover is rolling the SERVER back to before
-- this change while a daemon below MinLocalWorktreeCLIVersion is still in the
-- fleet: an old server has no gate, and an old daemon json-skips execution_mode
-- and would run the task in place, editing the working copy the resource asked
-- to isolate. So: do not roll the server back past this change while any
-- worktree local_directory resource exists, unless every daemon in those
-- workspaces is at or above the floor.
--
-- Rolling the server back with only CURRENT daemons is safe for isolation — a
-- current daemon implements the mode itself and refuses modes it does not
-- recognise. The only loss is branch_name, which an old server drops.

```

## server/go/migrations/309_agent_runtime_id_index.up.sql

```sql
-- Runtime GC re-checks that no Agent references a candidate after locking the
-- runtime row, then agent.runtime_id's existing RESTRICT foreign key repeats
-- the same lookup while deleting it. Without a runtime-leading index, each
-- bounded GC batch can scan the full Agent table once per candidate.
--
-- Keep this as the migration's only statement: the runner executes files
-- outside an explicit transaction so PostgreSQL can build the index without
-- blocking Agent writes for the duration of the scan.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_runtime_id
    ON agent (runtime_id);

```

## server/go/migrations/310_workspace_private_plugin_identity.up.sql

```sql
-- Workspace ownership is part of private Plugin identity, while official
-- identities remain global. Relationships stay application-owned: no FK.
ALTER TABLE plugin_identity
    ADD COLUMN owner_workspace_id UUID,
    ADD CONSTRAINT plugin_identity_scope_check CHECK (
        (publisher_type = 'private_dev' AND trust_tier = 'private_dev' AND owner_workspace_id IS NOT NULL)
        OR
        (publisher_type <> 'private_dev' AND trust_tier <> 'private_dev' AND owner_workspace_id IS NULL)
    );

```

## server/go/migrations/311_plugin_identity_scoped_key_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_identity_scoped_key
    ON plugin_identity (COALESCE(owner_workspace_id, '00000000-0000-0000-0000-000000000000'::uuid), plugin_key);

```

## server/go/migrations/312_drop_global_plugin_identity_key_index.up.sql

```sql
DROP INDEX CONCURRENTLY IF EXISTS idx_plugin_identity_key;

```

## server/go/migrations/313_runtime_profile_add_dsh.up.sql

```sql
-- Add the DeepSeek Harness runtime bridge as a first-party protocol
-- family. NOT VALID preserves historical-row tolerance while enforcing the
-- expanded whitelist for new rows.
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'reasonix',
        'dsh',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw'
    )) NOT VALID;

```

## server/go/migrations/314_workspace_mcp_config.up.sql

```sql
-- Workspace-level MCP configuration (GH #6062, MUL-5421).
--
-- Shares one MCP server set across every agent in the workspace instead of
-- forcing the same servers to be re-entered on each agent. Deliberately the
-- same shape as agent.mcp_config (046_agent_mcp_config): a nullable JSONB
-- document holding `{"mcpServers": {<name>: {...}}}`.
--
-- NULL keeps its meaning from the agent column — "nothing configured at this
-- layer" — so every existing workspace starts out with no shared servers and
-- no agent's effective configuration changes until an admin sets one.
ALTER TABLE workspace ADD COLUMN mcp_config jsonb;

```

## server/go/migrations/315_workspace_mcp_server.up.sql

```sql
-- Workspace MCP servers as an explicit per-agent assignment (GH #6062,
-- MUL-5421), replacing the inherit-by-default document added in 314.
--
-- A workspace-level library of MCP servers plus an explicit per-agent binding,
-- deliberately shaped like `skill` + `agent_skill`: creating a server here
-- gives it to NOBODY. It reaches an agent only when someone adds it to that
-- agent, and the binding carries its own on/off toggle. Nothing about this
-- layer propagates implicitly — that is the whole point of the shape, and the
-- reason 314's model is being replaced rather than extended.
--
-- No foreign keys (repo rule): the application sweeps `agent_mcp_server` when
-- an agent or a server goes away, and both tables on workspace delete.
CREATE TABLE workspace_mcp_server (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    name TEXT NOT NULL,
    -- One MCP server entry: the object that sits under a name in
    -- `mcpServers`. Secret-bearing (urls, headers, env), never returned by the
    -- API — see the write-only contract in workspace_mcp_api.go.
    config JSONB NOT NULL,
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE agent_mcp_server (
    agent_id UUID NOT NULL,
    server_id UUID NOT NULL,
    -- Bound but switched off: the agent keeps the association and the toggle
    -- state, exactly like agent_skill.enabled, so turning it back on does not
    -- mean finding the server again.
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (agent_id, server_id)
);

```

## server/go/migrations/316_workspace_mcp_server_name_unique.up.sql

```sql
-- Names identify a server to an agent's runtime, so they must not collide
-- inside a workspace. Concurrent build per the repo migration rule; kept in
-- its own single-statement file because Postgres rejects CONCURRENTLY inside a
-- transaction or a multi-command string.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_workspace_mcp_server_workspace_name
    ON workspace_mcp_server (workspace_id, name);

```

## server/go/migrations/317_agent_mcp_server_server_index.up.sql

```sql
-- Reverse lookup for the sweep that runs when a workspace server is deleted
-- (and for "which agents use this server" later). The forward direction is
-- already covered by the (agent_id, server_id) primary key.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_mcp_server_server
    ON agent_mcp_server (server_id);

```

## server/go/migrations/318_drop_workspace_mcp_config.up.sql

```sql
-- Drops the inherit-by-default column added in 314. Its model — every agent
-- picks the workspace document up automatically — is replaced by the explicit
-- assignment in 315, so leaving the column would keep a second, silently
-- inherited source of MCP servers alive.
--
-- No data migration, and no expand-contract window, by explicit maintainer
-- decision (Bohan, 2026-08-14): 314 shipped and merged in this same cycle and
-- was never deployed, so no environment has a binary that reads this column
-- and no workspace has ever stored a document in it. There is nothing to
-- preserve and no old instance to keep compatible.
--
-- If that ever stops being true — a deploy of 314 happens before this lands —
-- this file must become the CONTRACT half of an expand-contract pair instead:
-- convert each `mcpServers` entry into a `workspace_mcp_server` row with ZERO
-- `agent_mcp_server` bindings (which preserves the entries without giving them
-- to any agent, the behaviour being removed), ship the reading code first, and
-- drop the column only after the old binaries are gone.
ALTER TABLE workspace DROP COLUMN IF EXISTS mcp_config;

```

## server/go/migrations/319_remote_mcp_plugin_v1.up.sql

```sql
-- Remote MCP Plugin V1 adds revisioned installation configuration and a
-- dedicated encrypted credential store. Contribution declarations remain in
-- immutable Plugin releases; endpoint, grants, and credentials are owned by a
-- workspace installation and never enter an artifact or execution manifest.

ALTER TABLE plugin_contribution
    DROP CONSTRAINT plugin_contribution_type_check;

ALTER TABLE plugin_contribution
    ADD CONSTRAINT plugin_contribution_type_check
    CHECK (type IN ('agent.skill.v1', 'tool.remote-mcp.v1'));

CREATE TABLE plugin_remote_mcp_secret (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    installation_id UUID NOT NULL,
    contribution_id UUID NOT NULL,
    version BIGINT NOT NULL CHECK (version > 0),
    ciphertext BYTEA NOT NULL CHECK (octet_length(ciphertext) > 0),
    hint TEXT NOT NULL DEFAULT '' CHECK (char_length(hint) <= 32),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    CHECK (
        (status = 'active' AND revoked_at IS NULL)
        OR (status = 'revoked' AND revoked_at IS NOT NULL)
    )
);

CREATE TABLE plugin_installation_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    installation_id UUID NOT NULL,
    contribution_id UUID NOT NULL,
    revision BIGINT NOT NULL CHECK (revision > 0),
    endpoint TEXT NOT NULL CHECK (char_length(endpoint) BETWEEN 9 AND 2048),
    public_config JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(public_config) = 'object'),
    auth_type TEXT NOT NULL CHECK (auth_type IN ('none', 'bearer', 'header')),
    auth_header TEXT NOT NULL DEFAULT '' CHECK (char_length(auth_header) <= 128),
    secret_ref UUID,
    approved_tools JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(approved_tools) = 'array'),
    schema_digest TEXT,
    failure_policy TEXT NOT NULL DEFAULT 'required' CHECK (failure_policy IN ('required', 'optional')),
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((auth_type = 'none') = (secret_ref IS NULL)),
    CHECK (auth_type <> 'header' OR char_length(auth_header) > 0),
    CHECK ((jsonb_array_length(approved_tools) = 0) = (schema_digest IS NULL)),
    CHECK (schema_digest IS NULL OR schema_digest ~ '^sha256:[0-9a-f]{64}$'),
    CHECK ((reviewed_by IS NULL) = (reviewed_at IS NULL))
);

CREATE TRIGGER trg_plugin_installation_config_append_only
BEFORE UPDATE ON plugin_installation_config
FOR EACH ROW EXECUTE FUNCTION reject_plugin_append_only_update();

```

## server/go/migrations/320_plugin_installation_config_revision_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_installation_config_contribution_revision
    ON plugin_installation_config (installation_id, contribution_id, revision);

```

## server/go/migrations/321_plugin_installation_config_workspace_index.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_plugin_installation_config_workspace
    ON plugin_installation_config (workspace_id, installation_id, contribution_id, revision DESC);

```

## server/go/migrations/322_plugin_remote_mcp_secret_revision_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_remote_mcp_secret_revision
    ON plugin_remote_mcp_secret (installation_id, contribution_id, version);

```

## server/go/migrations/323_plugin_remote_mcp_secret_workspace_index.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_plugin_remote_mcp_secret_workspace
    ON plugin_remote_mcp_secret (workspace_id, installation_id, contribution_id, version DESC);

```

## server/go/migrations/324_plugin_remote_mcp_one_active_secret_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_plugin_remote_mcp_one_active_secret
    ON plugin_remote_mcp_secret (installation_id, contribution_id)
    WHERE status = 'active';

```

## server/go/migrations/325_plugin_remote_mcp_oauth.up.sql

```sql
-- Add first-class OAuth 2.1 connections for hosted Remote MCP servers.
-- Authorization state is short-lived and single-use. Access/refresh tokens,
-- PKCE verifiers, and optional client secrets are always secretbox ciphertext.

ALTER TABLE plugin_installation_config
    DROP CONSTRAINT plugin_installation_config_auth_type_check;

ALTER TABLE plugin_installation_config
    ADD CONSTRAINT plugin_installation_config_auth_type_check
    CHECK (auth_type IN ('none', 'bearer', 'header', 'oauth'));

ALTER TABLE plugin_installation_config
    ADD COLUMN discovered_tools JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(discovered_tools) = 'array'),
    ADD COLUMN discovered_schema_digest TEXT
        CHECK (discovered_schema_digest IS NULL OR discovered_schema_digest ~ '^sha256:[0-9a-f]{64}$'),
    ADD CONSTRAINT plugin_installation_config_discovered_digest_check
        CHECK ((jsonb_array_length(discovered_tools) = 0) = (discovered_schema_digest IS NULL));

CREATE TABLE plugin_remote_mcp_oauth_state (
    state_hash BYTEA PRIMARY KEY CHECK (octet_length(state_hash) = 32),
    workspace_id UUID NOT NULL,
    installation_id UUID NOT NULL,
    contribution_id UUID NOT NULL,
    actor_id UUID NOT NULL,
    endpoint TEXT NOT NULL CHECK (char_length(endpoint) BETWEEN 9 AND 2048),
    public_config JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(public_config) = 'object'),
    failure_policy TEXT NOT NULL DEFAULT 'required' CHECK (failure_policy IN ('required', 'optional')),
    authorization_endpoint TEXT NOT NULL CHECK (char_length(authorization_endpoint) BETWEEN 9 AND 2048),
    token_endpoint TEXT NOT NULL CHECK (char_length(token_endpoint) BETWEEN 9 AND 2048),
    client_id TEXT NOT NULL CHECK (char_length(client_id) BETWEEN 1 AND 2048),
    scope TEXT NOT NULL DEFAULT '' CHECK (char_length(scope) <= 4096),
    redirect_uri TEXT NOT NULL CHECK (char_length(redirect_uri) BETWEEN 9 AND 2048),
    return_to TEXT NOT NULL DEFAULT '' CHECK (char_length(return_to) <= 2048),
    secret_ciphertext BYTEA NOT NULL CHECK (octet_length(secret_ciphertext) > 0),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (expires_at > created_at)
);

```

## server/go/migrations/326_plugin_remote_mcp_oauth_state_expiry_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS plugin_remote_mcp_oauth_state_expiry_idx
    ON plugin_remote_mcp_oauth_state (expires_at);

```

## server/go/migrations/327_workspace_share_link.up.sql

```sql
-- Shareable invite links for workspaces (complement to email invitations).
--
-- id is NOT declared inline as PRIMARY KEY: the repo convention (see
-- migrations 207-209 / 227-229) is to build the table without a primary key,
-- create the backing unique index CONCURRENTLY in its own single-statement
-- migration (328), then attach it with PRIMARY KEY USING INDEX (329). The
-- workspace_id partial unique index (330) enforces the one-active-link-per-
-- workspace invariant and is created CONCURRENTLY as well.
CREATE TABLE workspace_share_link (
    id           UUID NOT NULL DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    code         TEXT NOT NULL,
    created_by   UUID NOT NULL,
    role         TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    expires_at   TIMESTAMPTZ,
    max_uses     INT,
    use_count    INT NOT NULL DEFAULT 0,
    is_active    BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/328_workspace_share_link_id_uidx.up.sql

```sql
-- Backing index for workspace_share_link's primary key, attached in 329 via
-- PRIMARY KEY USING INDEX. Own single-statement migration so CONCURRENTLY runs
-- outside an implicit transaction (repo convention).
--
-- IF NOT EXISTS covers the retry where the build committed but the runner died
-- before recording the version: a bare CREATE would fail on "already exists"
-- every time, and because 329 cannot attach a primary key without this index,
-- the migrator would stay wedged there instead of moving on. The INVALID
-- leftover of a genuinely interrupted build is removed first by the cleanup
-- hook registered for this migration in cmd/migrate, so IF NOT EXISTS can never
-- skip past a half-built index.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS workspace_share_link_pkey_uidx
    ON workspace_share_link (id);

```

## server/go/migrations/329_workspace_share_link_primary_key.up.sql

```sql
-- Attach the CONCURRENTLY-built unique index as the table's primary key.
ALTER TABLE workspace_share_link
    ADD CONSTRAINT workspace_share_link_pkey PRIMARY KEY USING INDEX workspace_share_link_pkey_uidx;

```

## server/go/migrations/330_workspace_share_link_active_ws_uidx.up.sql

```sql
-- Enforce at most one active share link per workspace. Partial unique index so
-- only active rows are constrained; revoked/expired links remain in place for
-- audit without blocking a new link.
-- IF NOT EXISTS keeps a retry idempotent when the build committed but the
-- version was never recorded; an interrupted build's INVALID leftover is
-- dropped first by this migration's cleanup hook in cmd/migrate.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS workspace_share_link_active_ws_uidx
    ON workspace_share_link (workspace_id) WHERE is_active = true;

```

## server/go/migrations/331_workspace_share_link_code_uidx.up.sql

```sql
-- Lookup index for joins/previews by invite code.
--
-- IF NOT EXISTS keeps a retry idempotent when the build committed but the
-- version was never recorded; an interrupted build's INVALID leftover is
-- dropped first by this migration's cleanup hook in cmd/migrate.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS workspace_share_link_code_uidx
    ON workspace_share_link (code);

```

## server/go/migrations/332_issue_status.up.sql

```sql
-- Custom Issue Status catalog (MUL-6243).
--
-- MODEL: the 7 categories map ONE-TO-ONE onto the 7 built-in statuses, and a
-- category's value IS its canonical status key. A custom status names a
-- category and inherits that canonical's platform behavior wholesale, so there
-- is no second "behaves_as" concept and no way to build a status that inherits
-- only half of a behavior.
--
-- `issue.status` stays the authoritative TEXT column and keeps holding a key
-- from this catalog, so no status_id, no backfill, and no double-write: every
-- existing `WHERE status = 'todo'` and `issue.Status == "backlog"` keeps
-- working verbatim because the 7 built-in keys never change.
--
-- No foreign keys (workspace_id is an application-layer relation, per the
-- project's database rules); cleanup is handled by the application.
--
-- id is NOT declared inline as PRIMARY KEY: the repo convention (see migrations
-- 327-329) is to build the table without a primary key, create the backing
-- unique index CONCURRENTLY in its own single-statement migration (333), then
-- attach it with PRIMARY KEY USING INDEX (334). An inline PRIMARY KEY would
-- build its index non-concurrently, which the project's migration rules forbid
-- even on a new table.
CREATE TABLE issue_status (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,

    -- Stable machine handle. Immutable after create: it is what `issue.status`
    -- stores, what the CLI accepts, and what agent instructions reference.
    key TEXT NOT NULL CHECK (key ~ '^[a-z0-9][a-z0-9_]{0,31}$'),

    -- Human-facing label. Editable for custom statuses; locked for built-ins.
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 64),
    description TEXT NOT NULL DEFAULT '' CHECK (char_length(description) <= 256),

    -- Behavior equivalence class. Immutable after create — changing it would
    -- silently rewrite the machine semantics of every issue already sitting on
    -- this status, with no audit trail.
    category TEXT NOT NULL CHECK (
        category IN ('backlog', 'todo', 'in_progress', 'in_review', 'done', 'blocked', 'cancelled')
    ),

    -- "#rrggbb". Built-in rows carry the seeded palette for API consumers, but
    -- clients that already know a built-in key keep rendering it from their own
    -- config, so the default experience stays pixel-identical.
    color TEXT NOT NULL CHECK (color ~ '^#[0-9a-f]{6}$'),

    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    position DOUBLE PRECISION NOT NULL DEFAULT 0,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- A built-in row IS its category's canonical, so its key must equal its
    -- category. This is what makes Effective() an identity function on built-in
    -- keys, which is in turn what keeps every existing status check correct.
    CONSTRAINT issue_status_system_is_canonical
        CHECK (NOT is_system OR key = category),

    -- Archiving a built-in would delete its category's behavior definition.
    CONSTRAINT issue_status_system_not_archivable
        CHECK (NOT is_system OR archived_at IS NULL)
);

```

## server/go/migrations/333_issue_status_pkey_index.up.sql

```sql
-- Backing index for issue_status's primary key, attached in 334 via
-- PRIMARY KEY USING INDEX. Own single-statement migration so CONCURRENTLY runs
-- outside an implicit transaction (repo convention).
CREATE UNIQUE INDEX CONCURRENTLY issue_status_pkey_uidx
    ON issue_status (id);

```

## server/go/migrations/334_issue_status_primary_key.up.sql

```sql
-- Attach the CONCURRENTLY-built unique index as the table's primary key.
ALTER TABLE issue_status
    ADD CONSTRAINT issue_status_pkey PRIMARY KEY USING INDEX issue_status_pkey_uidx;

```

## server/go/migrations/335_issue_status_workspace_key_index.up.sql

```sql
-- The catalog lookup that every status resolution and the ordering join use:
-- (workspace_id, key) is how `issue.status` is resolved back to its category.
-- Unique because a workspace cannot hold two statuses with the same key, and
-- this is what stops a custom status from colliding with a built-in one.
CREATE UNIQUE INDEX CONCURRENTLY idx_issue_status_workspace_key
    ON issue_status (workspace_id, key);

```

## server/go/migrations/336_issue_status_workspace_name_index.up.sql

```sql
-- Display names must stay unambiguous among ACTIVE statuses; archived rows are
-- excluded so an archived name can be reused.
CREATE UNIQUE INDEX CONCURRENTLY idx_issue_status_workspace_name_active
    ON issue_status (workspace_id, lower(name))
    WHERE archived_at IS NULL;

```

## server/go/migrations/337_issue_status_open_check.up.sql

```sql
-- Open `issue.status` to catalog keys (MUL-6243).
--
-- The old constraint hard-coded the 7 built-in statuses, which is exactly the
-- thing a per-workspace catalog has to be able to extend. Membership validation
-- moves to the application layer, where it is checked against issue_status for
-- the issue's OWN workspace — something a table-level CHECK cannot express.
--
-- A format constraint stays behind as defense in depth: it cannot know whether
-- a key exists in the catalog, but it does keep an empty string or arbitrary
-- text out of the column if a write path ever forgets to validate. Added
-- NOT VALID so it takes no table scan under lock; migration 338 validates it.
ALTER TABLE issue DROP CONSTRAINT issue_status_check;

ALTER TABLE issue
    ADD CONSTRAINT issue_status_format_check
    CHECK (status ~ '^[a-z0-9][a-z0-9_]{0,31}$')
    NOT VALID;

```

## server/go/migrations/338_issue_status_validate_format.up.sql

```sql
-- Validates the format constraint added NOT VALID in 330. Existing rows all
-- hold one of the 7 built-in keys, which match the pattern, so this scan
-- confirms rather than repairs. SHARE UPDATE EXCLUSIVE — reads and writes
-- continue during the scan.
ALTER TABLE issue VALIDATE CONSTRAINT issue_status_format_check;

```

## server/go/migrations/339_seed_issue_status_catalog.up.sql

```sql
-- Seed the 7 built-in statuses for every EXISTING workspace (MUL-6243).
--
-- New workspaces are seeded inside their create transaction; this covers the
-- ones that already exist. Idempotent via the unique (workspace_id, key)
-- index from migration 335, so a re-run or a concurrent seed from a pod that
-- already booted the new code is a no-op rather than an error.
--
-- Not a hazard if it is slow: until a workspace has custom statuses, the
-- resolver treats a built-in key as itself without consulting this table at
-- all, so an unseeded workspace keeps behaving exactly as it does today.
INSERT INTO issue_status (workspace_id, key, name, description, category, color, is_system, position)
SELECT w.id, s.key, s.name, s.description, s.key, s.color, TRUE, 0
FROM workspace w
CROSS JOIN (
    VALUES
        ('backlog',     'Backlog',     'Parked. Assigning an issue here never starts an agent run.',        '#6b7280'),
        ('todo',        'Todo',        'Queued for work. Moving an issue here starts the assigned agent.',  '#6b7280'),
        ('in_progress', 'In Progress', 'Actively being worked on.',                                         '#f59e0b'),
        ('in_review',   'In Review',   'Work delivered, waiting on human review. Finalizes the autopilot run.', '#22c55e'),
        ('done',        'Done',        'Completed.',                                                        '#3b82f6'),
        ('blocked',     'Blocked',     'Stalled on an external dependency.',                                '#ef4444'),
        ('cancelled',   'Cancelled',   'Decided not to do.',                                                '#6b7280')
) AS s(key, name, description, color)
ON CONFLICT DO NOTHING;

```

## server/go/migrations/340_issue_effective_status_fn.up.sql

```sql
-- SQL mirror of issuestatus.Effective (MUL-6243).
--
-- Several queries have to ask "is this issue terminal / open?" in SQL, where
-- the Go resolver cannot reach. Without this, a custom status in the `done`
-- category would still count as open for the duplicate guard, and would be
-- missed by sub-issue and project completion counts.
--
-- The built-in fast path comes FIRST and short-circuits, so a workspace with no
-- custom statuses performs no catalog lookup at all — the same guarantee the Go
-- resolver gives. The lookup for a custom key is a single point read on
-- idx_issue_status_workspace_key.
--
-- Falls back to the raw status when the key is unknown or its category is
-- corrupt, matching the Go resolver's fail-safe direction: an unrecognized
-- status matches none of the canonical comparisons, so the issue is left alone
-- rather than being treated as terminal on a guess.
--
-- STABLE (not IMMUTABLE): the result depends on catalog rows, so it must not be
-- folded into an index or cached across statements.
CREATE FUNCTION issue_effective_status(p_workspace_id UUID, p_status TEXT)
RETURNS TEXT
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN p_status IN ('backlog', 'todo', 'in_progress', 'in_review', 'done', 'blocked', 'cancelled')
            THEN p_status
        ELSE COALESCE(
            (SELECT s.category
               FROM issue_status s
              WHERE s.workspace_id = p_workspace_id
                AND s.key = p_status
                AND s.category IN ('backlog', 'todo', 'in_progress', 'in_review', 'done', 'blocked', 'cancelled')),
            p_status)
    END
$$;

```

## server/go/migrations/341_issue_property_actor_types.up.sql

```sql
-- Custom issue property actor types (MUL-6286).
--
-- Adds 'actor' and 'multi_actor' to the type allowlist. Both store a prefixed
-- reference string ("member:<user_id>"); multi_actor stores an array of them.
-- The kind prefix is what lets the accepted-kind set widen later without
-- another migration or a new property type.
--
-- Keeping the value a plain string (rather than an object) means the existing
-- @> containment filter, the jsonb_path_ops GIN index, and the client value
-- schema all keep working unchanged.
--
-- The type is validated again in the handler, which additionally resolves each
-- reference against the workspace. This constraint is only the outer guard.
--
-- NOT VALID + VALIDATE keeps the ACCESS EXCLUSIVE lock instantaneous; existing
-- rows all carry one of the original seven types, so validation is a formality.
ALTER TABLE issue_property DROP CONSTRAINT IF EXISTS issue_property_type_check;
ALTER TABLE issue_property ADD CONSTRAINT issue_property_type_check
    CHECK (type IN ('text', 'number', 'select', 'multi_select', 'date', 'checkbox', 'url', 'actor', 'multi_actor')) NOT VALID;
ALTER TABLE issue_property VALIDATE CONSTRAINT issue_property_type_check;

```

## server/go/migrations/342_runtime_profile_add_mcode.up.sql

```sql
-- Add MiniMax Code as a first-party ACP protocol family. NOT VALID preserves
-- historical-row tolerance while enforcing the expanded whitelist for new rows.
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'reasonix',
        'dsh',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw',
        'mcode'
    )) NOT VALID;

```

## server/go/migrations/343_comment_delegated_failure_pending_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_comment_delegated_failure_pending
ON comment (created_at, id)
WHERE author_type = 'system'
  AND type = 'progress_update'
  AND source_task_id IS NOT NULL;

```

## server/go/migrations/344_plugin_v2_reset.up.sql

```sql
-- Plugin system reset.
--
-- The previous design shipped 14 tables, an append-only revision log per
-- relationship, a capability-snapshot compiler, and a per-task execution
-- manifest pinned by an INSERT trigger on agent_task_queue. It never left its
-- feature flag and holds no production data, so this migration removes it
-- outright rather than migrating it forward.
--
-- What replaces it: one installation row per (workspace, plugin), holding the
-- manifest snapshot the administrator actually consented to, plus two leaf
-- tables for plugin-owned state. Relationships stay application-owned by
-- repository policy: no foreign keys, no cascades.

DROP TRIGGER IF EXISTS trg_agent_task_queue_plugin_execution_manifest ON agent_task_queue;
DROP FUNCTION IF EXISTS pin_plugin_execution_manifest();

DROP TRIGGER IF EXISTS trg_plugin_installation_config_append_only ON plugin_installation_config;
DROP TRIGGER IF EXISTS trg_plugin_health_append_only ON plugin_health;
DROP TRIGGER IF EXISTS trg_plugin_execution_manifest_append_only ON plugin_execution_manifest;
DROP TRIGGER IF EXISTS trg_plugin_capability_snapshot_append_only ON plugin_capability_snapshot;
DROP TRIGGER IF EXISTS trg_plugin_artifact_file_append_only ON plugin_artifact_file;
DROP TRIGGER IF EXISTS trg_plugin_binding_append_only ON plugin_binding;
DROP TRIGGER IF EXISTS trg_plugin_grant_append_only ON plugin_grant;
DROP TRIGGER IF EXISTS trg_plugin_contribution_append_only ON plugin_contribution;
DROP TRIGGER IF EXISTS trg_plugin_release_immutable ON plugin_release;
DROP FUNCTION IF EXISTS reject_plugin_append_only_update();
DROP FUNCTION IF EXISTS enforce_plugin_release_immutable();

ALTER TABLE agent_task_queue DROP COLUMN IF EXISTS plugin_execution_manifest_id;

DROP TABLE IF EXISTS plugin_remote_mcp_oauth_state;
DROP TABLE IF EXISTS plugin_remote_mcp_secret;
DROP TABLE IF EXISTS plugin_installation_config;
DROP TABLE IF EXISTS plugin_health;
DROP TABLE IF EXISTS plugin_execution_manifest;
DROP TABLE IF EXISTS plugin_capability_snapshot;
DROP TABLE IF EXISTS plugin_workspace_capability_state;
DROP TABLE IF EXISTS plugin_artifact_file;
DROP TABLE IF EXISTS plugin_binding;
DROP TABLE IF EXISTS plugin_grant;
DROP TABLE IF EXISTS plugin_installation;
DROP TABLE IF EXISTS plugin_contribution;
DROP TABLE IF EXISTS plugin_release;
DROP TABLE IF EXISTS plugin_identity;

-- One row per installed plugin. `manifest` is the snapshot the administrator
-- saw and approved on the consent screen, not whatever the source URL serves
-- today: an upgrade re-fetches, re-consents, and overwrites it. That is why
-- there is no separate version table.
CREATE TABLE plugin_installation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    plugin_key TEXT NOT NULL CHECK (char_length(plugin_key) BETWEEN 3 AND 255),
    source_url TEXT NOT NULL CHECK (char_length(source_url) BETWEEN 1 AND 2048),
    version TEXT NOT NULL CHECK (char_length(version) BETWEEN 1 AND 64),
    manifest JSONB NOT NULL CHECK (jsonb_typeof(manifest) = 'object'),
    granted_scopes JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(granted_scopes) = 'array'),
    config JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(config) = 'object'),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    installed_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Plugin-owned key/value state. Exactly two scopes: workspace state shared by
-- the team, and per-member state. Quotas are enforced on write in application
-- code; nothing here is evicted behind the plugin's back.
CREATE TABLE plugin_storage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id UUID NOT NULL,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('workspace', 'user')),
    scope_id UUID NOT NULL,
    -- Byte-counted, matching the service-side quota: key and value are
    -- plugin-supplied and routinely non-ASCII.
    key TEXT NOT NULL CHECK (octet_length(key) BETWEEN 1 AND 1024),
    value TEXT NOT NULL CHECK (octet_length(value) <= 102400),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Secrets live in their own table so no storage read path can reach them by
-- construction. Values are encrypted with WORKPAL_PLUGIN_SECRET_KEY and are
-- never returned by any endpoint.
CREATE TABLE plugin_secret (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id UUID NOT NULL,
    key TEXT NOT NULL CHECK (char_length(key) BETWEEN 1 AND 128),
    ciphertext BYTEA NOT NULL CHECK (octet_length(ciphertext) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/345_plugin_installation_workspace_key_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_installation_workspace_key
    ON plugin_installation (workspace_id, plugin_key);

```

## server/go/migrations/346_plugin_storage_scope_key_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_storage_scope_key
    ON plugin_storage (installation_id, scope_type, scope_id, key);

```

## server/go/migrations/347_plugin_secret_installation_key_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_secret_installation_key
    ON plugin_secret (installation_id, key);

```

## server/go/migrations/348_plugin_via_attribution.up.sql

```sql
-- Plugin-mediated writes record which plugin mediated them.
--
-- A surface writes as the CURRENT USER — a plugin can never do more than the
-- person using it — so author_type/author_id stay exactly what they would be
-- without a plugin. This column is the missing half of that: permission-wise
-- the write is the user's, but audit-wise it must stay attributable to the
-- plugin that produced it, or an installed plugin becomes an untraceable way
-- to act as someone.
--
-- Modeled on comment.quick_action_id (migration 239) for the same two reasons:
-- adding a nullable column with no default is metadata-only and instant on a
-- hot table, and there is no request field for it — only the plugin Action API
-- sets it — so the marker cannot be forged by a member posting normally.
--
-- No FK per repository policy. The render path treats an unresolvable id as an
-- ordinary write, so uninstalling a plugin degrades old rows to plain
-- attribution instead of breaking them.
ALTER TABLE comment ADD COLUMN IF NOT EXISTS via_plugin_id UUID;

```

## server/go/migrations/349_agent_task_queue_chat_terminal_resume_index.up.sql

```sql
-- Bounds both chat resume-history queries to one chat instead of scanning the
-- global terminal-task population. Keep all three terminal states: the
-- completed/failed rollout-missing query implies this wider predicate, while
-- GetLastChatTaskSession also needs cancelled rows. chat_session_id IS NOT NULL
-- excludes issue tasks from this hot write-table index.
--
-- Do NOT add session_id IS NOT NULL. The resume_overflow_at CTE must read
-- codex_resume_oversized failures whose NULL session_id marks the cutoff; a
-- narrower predicate would silently send that CTE back to a full-table scan.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_chat_terminal_resume
ON agent_task_queue (chat_session_id, session_id, completed_at DESC)
WHERE chat_session_id IS NOT NULL
  AND status IN ('completed', 'failed', 'cancelled');

```

## server/go/migrations/350_agent_task_queue_chat_retired_session_index.up.sql

```sql
-- Retired sessions need their own sparse index: the database has no CHECK
-- constraint proving retired_session_id is present only on terminal rows, so
-- folding this into migration 349's terminal predicate could resurrect a
-- retired session by silently omitting a valid non-terminal marker.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_chat_retired_session
ON agent_task_queue (chat_session_id, retired_session_id)
WHERE chat_session_id IS NOT NULL
  AND retired_session_id IS NOT NULL;

```

## server/go/migrations/351_issue_comment_revision.up.sql

```sql
ALTER TABLE issue
    ADD COLUMN revision BIGINT NOT NULL DEFAULT 1;

ALTER TABLE comment
    ADD COLUMN revision BIGINT NOT NULL DEFAULT 1;

```

## server/go/migrations/352_autopilot_quota_execution.up.sql

```sql
-- Durable, policy-agnostic accounting for the autopilot_runs entitlement gate.
-- Limits and period boundaries are supplied by Cloud at runtime; no commercial
-- defaults or calendar assumptions live in this schema.

CREATE TABLE autopilot_quota_period (
    workspace_id UUID NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    used_count BIGINT NOT NULL DEFAULT 0 CHECK (used_count >= 0),
    reserved_count BIGINT NOT NULL DEFAULT 0 CHECK (reserved_count >= 0),
    blocked_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (period_start < period_end)
);

CREATE TABLE autopilot_quota_reservation (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    policy_revision BIGINT NOT NULL,
    subscription_version BIGINT NOT NULL,
    source TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'reserved'
        CHECK (state IN ('reserved', 'consumed', 'released')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalized_at TIMESTAMPTZ,
    CHECK (period_start < period_end)
);

ALTER TABLE autopilot_run
    ADD COLUMN quota_reservation_id UUID,
    ADD COLUMN reason_code TEXT;

ALTER TABLE webhook_delivery
    ADD COLUMN reason_code TEXT,
    ADD COLUMN replay_idempotency_key TEXT;

```

## server/go/migrations/353_autopilot_quota_period_scope_index.up.sql

```sql
-- Natural-key backing index for the primary key attached in migration 359.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_autopilot_quota_period_scope
    ON autopilot_quota_period(workspace_id, period_start, period_end);

```

## server/go/migrations/354_autopilot_quota_reservation_id_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS autopilot_quota_reservation_pkey_uidx
    ON autopilot_quota_reservation(id);

```

## server/go/migrations/355_autopilot_quota_reservation_key_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_autopilot_quota_reservation_key
    ON autopilot_quota_reservation(workspace_id, period_start, period_end, idempotency_key)
    WHERE state <> 'released';

```

## server/go/migrations/356_autopilot_run_quota_reservation_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_autopilot_run_quota_reservation
    ON autopilot_run(quota_reservation_id)
    WHERE quota_reservation_id IS NOT NULL;

```

## server/go/migrations/357_webhook_delivery_replay_idempotency_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_webhook_delivery_replay_idempotency
    ON webhook_delivery(replayed_from_delivery_id, replay_idempotency_key)
    WHERE replayed_from_delivery_id IS NOT NULL AND replay_idempotency_key IS NOT NULL;

```

## server/go/migrations/358_autopilot_quota_reservation_state_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_autopilot_quota_reservation_state
    ON autopilot_quota_reservation(state, created_at)
    WHERE state = 'reserved';

```

## server/go/migrations/359_autopilot_quota_primary_keys.up.sql

```sql
-- Attach the concurrently-built unique indexes as primary keys. The quota
-- period uses its actual lookup and locking key instead of an unused surrogate.
ALTER TABLE autopilot_quota_period
    ADD CONSTRAINT autopilot_quota_period_pkey
    PRIMARY KEY USING INDEX uq_autopilot_quota_period_scope;

ALTER TABLE autopilot_quota_reservation
    ADD CONSTRAINT autopilot_quota_reservation_pkey
    PRIMARY KEY USING INDEX autopilot_quota_reservation_pkey_uidx;

```

## server/go/migrations/360_issue_last_activity_at.up.sql

```sql
ALTER TABLE issue
    ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ;

```

## server/go/migrations/361_issue_last_activity_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_workspace_last_activity
    ON issue (workspace_id, last_activity_at DESC NULLS LAST, id DESC);

```

## server/go/migrations/362_plugin_hook_engine.up.sql

```sql
-- Hook engine: the host calls out to a plugin's own server.
--
-- Everything before this shipped one direction only — a sandboxed surface asks
-- the host, the host acts on the signed-in user's session. This is the reverse
-- edge, so the two new things it needs are a record of what we sent (triage,
-- rate limiting, circuit breaking) and a credential a plugin backend can present
-- when it calls back.

-- One row per hook call. Deliberately NOT an audit log: it is TTL-swept, it
-- stores no request or response body, and nothing in the product reads it to
-- decide what happened to a user's data. Its jobs are operational — show the
-- author why their endpoint is failing, feed the per-hook rate limit, and let
-- the event dispatcher decide when to trip a circuit breaker.
--
-- Bodies are omitted on purpose. A hook payload can carry issue text, and a
-- table that keeps every payload forever is a second copy of workspace content
-- with none of the deletion paths that the first copy has.
CREATE TABLE plugin_invocation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    hook_key TEXT NOT NULL CHECK (char_length(hook_key) BETWEEN 1 AND 128),
    trigger TEXT NOT NULL CHECK (trigger IN ('ui', 'manual', 'event', 'agent')),
    status TEXT NOT NULL CHECK (status IN ('ok', 'failed', 'timeout', 'refused')),
    -- Which event caused an event-triggered call. NULL for every other trigger.
    event_type TEXT,
    attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt BETWEEN 1 AND 10),
    latency_ms INTEGER NOT NULL DEFAULT 0 CHECK (latency_ms >= 0),
    -- Redacted, bounded, and only ever the host's own description of the
    -- failure. Never a response body: an endpoint that echoes its input would
    -- otherwise write issue content in here through the back door.
    error TEXT CHECK (error IS NULL OR char_length(error) <= 500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Install token: lets a plugin's own backend reach the Action API without a
-- user in the loop. Only the hash is stored, so a database read cannot mint a
-- working credential, and rotation is an UPDATE of this column.
--
-- This is the first credential in the system that is not the signed-in user's
-- session. It does not weaken the surface rule — a token still never enters an
-- iframe, and a surface still cannot obtain one — but the claim is now "tokens
-- only move between servers" rather than "there are no tokens".
ALTER TABLE plugin_installation ADD COLUMN IF NOT EXISTS token_hash TEXT;
ALTER TABLE plugin_installation ADD COLUMN IF NOT EXISTS token_rotated_at TIMESTAMPTZ;

-- A fourth comment author. Identity follows the trigger: a ui/manual hook acts
-- for the person who pressed the button and stays attributed to them (with
-- via_plugin_id naming the plugin), while an event hook has no person behind it
-- and must not borrow one. author_id then holds the installation id.
--
-- Same reason as migration 107, which added 'system': a row the platform
-- produced that would be a lie attributed to any member. NOT the same shape,
-- though — 107 revalidated the whole table under ACCESS EXCLUSIVE, which was
-- cheap on the comment table of that era and is not on today's. NOT VALID adds
-- the constraint without a scan; migration 365 validates it under a lock that
-- readers and writers can share.
--
-- New rows are checked from the moment this lands. NOT VALID only means "do not
-- re-check the rows already here", and the widened set is a superset of the old
-- one, so there is nothing here that could violate it.
ALTER TABLE comment DROP CONSTRAINT IF EXISTS comment_author_type_check;
ALTER TABLE comment ADD CONSTRAINT comment_author_type_check
    CHECK (author_type IN ('member', 'agent', 'system', 'plugin')) NOT VALID;

```

## server/go/migrations/363_plugin_invocation_installation_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_invocation_installation_created
    ON plugin_invocation (installation_id, created_at DESC);

```

## server/go/migrations/364_plugin_invocation_created_at_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_invocation_created_at
    ON plugin_invocation (created_at);

```

## server/go/migrations/365_plugin_comment_author_type_validate.up.sql

```sql
-- Validates the constraint migration 362 added NOT VALID.
--
-- Split out because VALIDATE CONSTRAINT takes SHARE UPDATE EXCLUSIVE — readers
-- and writers continue — while doing the scan that ADD CONSTRAINT would have
-- done under ACCESS EXCLUSIVE, stopping the comment table for its duration.
ALTER TABLE comment VALIDATE CONSTRAINT comment_author_type_check;

```

## server/go/migrations/366_issue_origin_telegram_chat.up.sql

```sql
-- Extend issue.origin_type for issues created by the Telegram `/issue`
-- command. origin_id stores the chat_session id, matching the existing Lark,
-- Slack, DingTalk, and WeCom channel origins.
--
-- This only widens the allowed set. Recreate the CHECK as NOT VALID so the
-- ACCESS EXCLUSIVE lock is held briefly; migration 367 performs the table scan
-- under SHARE UPDATE EXCLUSIVE without blocking normal reads and writes.
ALTER TABLE issue DROP CONSTRAINT IF EXISTS issue_origin_type_check;
ALTER TABLE issue ADD CONSTRAINT issue_origin_type_check
    CHECK (origin_type IN ('autopilot', 'quick_create', 'lark_chat', 'slack_chat', 'agent_create', 'dingtalk_chat', 'wecom_chat', 'telegram_chat'))
    NOT VALID;

```

## server/go/migrations/367_issue_origin_telegram_chat_validate.up.sql

```sql
-- Validate the widened CHECK separately from migration 366 so the validation
-- scan does not inherit migration 366's ACCESS EXCLUSIVE lock.
ALTER TABLE issue VALIDATE CONSTRAINT issue_origin_type_check;

```

## server/go/migrations/368_skill_plugin_ownership.up.sql

```sql
-- A plugin's `skill` resources become ordinary workspace skills.
--
-- Deliberately the EXISTING skill table rather than a plugin-owned copy. The
-- previous plugin system routed skills through an artifact/digest/bundle
-- pipeline across fourteen tables and, after all of it, delivered one SKILL.md
-- that the skill table could already hold. A plugin skill is a skill; the only
-- thing the platform needs to remember is who put it there.
--
-- That is what this column is for: uninstall has to remove exactly the skills
-- the installation contributed, and nothing a person wrote by hand. NULL means
-- a human made it, which is every row that exists today.
--
-- Nullable, no default: metadata-only, no rewrite. No FK per repository policy —
-- uninstall deletes these explicitly, in the same transaction as the rest of the
-- installation's cleanup.
ALTER TABLE skill ADD COLUMN IF NOT EXISTS plugin_installation_id UUID;

```

## server/go/migrations/369_plugin_mcp_approvals.up.sql

```sql
-- Admin approval for an mcp-transport hook's tool list.
--
-- A hook with transport.type == "mcp" points at an MCP server the plugin author
-- already runs, and Workpal adopts its tools as callable hooks. Unlike an http
-- hook — where the manifest declares exactly one endpoint and one shape — an MCP
-- server decides its own tool list at runtime and can change it whenever it
-- likes.
--
-- That is the difference this column exists for. An administrator approves a
-- specific list with a specific schema digest; a tool that appears later is not
-- adopted, and a tool whose schema drifts stops being called. Without the pin,
-- "install this plugin" would be a standing grant to run whatever that server
-- decides to offer next week.
--
-- Keyed by hook key, so one installation can contribute several mcp hooks and
-- each is approved on its own:
--   {"<hook_key>": {"tools": [{"name": ..., "schema_digest": ...}],
--                   "approved_at": "...", "approved_by": "<user uuid>"}}
--
-- JSONB rather than a table: nothing joins on it, nothing queries inside it, and
-- it is read as a whole whenever the installation is. A table would be a second
-- lifecycle to keep in step with the installation for no reader's benefit.
ALTER TABLE plugin_installation
    ADD COLUMN IF NOT EXISTS mcp_approvals JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(mcp_approvals) = 'object');

```

## server/go/migrations/370_runtime_profile_add_dim.up.sql

```sql
-- Add Dim as a first-party ACP protocol family. NOT VALID preserves
-- historical-row tolerance while enforcing the expanded whitelist for new rows.
-- The whitelist includes dsh (added by migration 313) and dim.
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'reasonix',
        'dsh',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw',
        'mcode',
        'dim'
    )) NOT VALID;

```

## server/go/migrations/371_comment_content_search_index_strategy.up.sql

```sql
-- The migration runner executes this only when the CJK-friendly
-- idx_comment_content_bigm index has the exact valid and ready shape used by
-- SearchIssues. pg_bigm-less self-hosted deployments skip this statement and
-- retain the trigram fallback.
-- If the preferred index later becomes unusable, follow the recovery procedure
-- in server/go/cmd/migrate/README.md; this migration is already recorded and will
-- not recreate the fallback automatically.
DROP INDEX CONCURRENTLY IF EXISTS idx_comment_content_trgm;

```

## server/go/migrations/375_drop_issue_last_activity_index.up.sql

```sql
-- The recent-activity issue window is not active, while maintaining this index
-- makes every last_activity_at update ineligible for a HOT update.
DROP INDEX CONCURRENTLY IF EXISTS idx_issue_workspace_last_activity;

```

## server/go/migrations/376_agent_task_durable_work_dir.up.sql

```sql
-- Records the durable directory that replaces a disposable task worktree
-- after the daemon has confirmed that worktree was finalized and removed.
-- NULL means no such handoff was reported, so clients must keep using work_dir.
--
-- Renumbered from 362: #7176 and #7182 both took prefix 362 before either
-- merged, and neither had shipped in a release when the collision was found.
-- The runner keys schema_migrations on the full stem, so a database that
-- already ran 362_agent_task_durable_work_dir re-runs this file under the new
-- stem; the DDL is idempotent, so that replay is a no-op. Keep it that way.
ALTER TABLE agent_task_queue
ADD COLUMN IF NOT EXISTS durable_work_dir TEXT;

```

## server/go/migrations/377_channel_chat_context_generation.up.sql

```sql
ALTER TABLE channel_chat_session_binding
    ADD COLUMN IF NOT EXISTS context_revision BIGINT NOT NULL DEFAULT 1;

ALTER TABLE chat_message
    ADD COLUMN IF NOT EXISTS channel_context_revision BIGINT;

ALTER TABLE chat_message
    ADD COLUMN IF NOT EXISTS channel_outbound_type TEXT;

ALTER TABLE chat_message
    ADD COLUMN IF NOT EXISTS channel_outbound_installation_id UUID;

ALTER TABLE chat_message
    ADD COLUMN IF NOT EXISTS channel_outbound_chat_id TEXT;

ALTER TABLE chat_message
    ADD COLUMN IF NOT EXISTS channel_outbound_message_ids TEXT[];

ALTER TABLE agent_task_queue
    ADD COLUMN IF NOT EXISTS channel_context_revision BIGINT;

CREATE TABLE IF NOT EXISTS channel_chat_context_generation (
    chat_session_id          UUID NOT NULL,
    revision                 BIGINT NOT NULL,
    history_start_message_id TEXT,
    history_end_message_id   TEXT,
    history_boundary_pending BOOLEAN NOT NULL DEFAULT FALSE,
    pending_fresh            BOOLEAN NOT NULL DEFAULT FALSE,
    initiator_user_id        UUID,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO channel_chat_context_generation (chat_session_id, revision)
SELECT chat_session_id, context_revision
FROM channel_chat_session_binding AS binding
WHERE NOT EXISTS (
    SELECT 1
    FROM channel_chat_context_generation AS generation
    WHERE generation.chat_session_id = binding.chat_session_id
      AND generation.revision = binding.context_revision
);

```

## server/go/migrations/378_channel_chat_context_generation_key.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS channel_chat_context_generation_session_revision_idx
    ON channel_chat_context_generation (chat_session_id, revision);

```

## server/go/migrations/379_channel_context_mixed_version_guard.up.sql

```sql
-- Snapshot only channel tasks that may still execute after this migration.
-- Terminal historical rows remain NULL and use the generation-1 read fallback;
-- rewriting them would create unnecessary table churn during deployment.
UPDATE agent_task_queue AS task
SET channel_context_revision = 1
WHERE task.channel_context_revision IS NULL
  AND task.chat_session_id IS NOT NULL
  AND task.status IN ('queued', 'dispatched', 'running', 'waiting_local_directory', 'deferred')
  AND (
      EXISTS (
          SELECT 1
          FROM channel_chat_session_binding AS binding
          WHERE binding.chat_session_id = task.chat_session_id
      )
      OR EXISTS (
          SELECT 1
          FROM chat_message AS message
          WHERE message.task_id = task.id
            AND message.channel_ingested
      )
  );

-- A channel message can only become input to a task from the same context
-- generation. This is a durable data invariant, not an old-writer shim: the
-- supported deployment strategy stops the previous server before starting the
-- new one, while adjacent-release rollback relies on nullable columns and the
-- generation-1 fallback.
CREATE OR REPLACE FUNCTION enforce_channel_message_task_context_revision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    task_revision BIGINT;
BEGIN
    IF OLD.task_id IS NOT NULL
       OR NEW.task_id IS NULL
       OR NEW.role <> 'user' THEN
        RETURN NEW;
    END IF;

    SELECT COALESCE(task.channel_context_revision, 1)
    INTO task_revision
    FROM agent_task_queue AS task
    WHERE task.id = NEW.task_id;

    IF task_revision IS NOT NULL
       AND COALESCE(NEW.channel_context_revision, 1) <> task_revision THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_enforce_channel_message_task_context_revision
BEFORE UPDATE OF task_id ON chat_message
FOR EACH ROW
WHEN (OLD.task_id IS NULL AND NEW.task_id IS NOT NULL AND NEW.role = 'user')
EXECUTE FUNCTION enforce_channel_message_task_context_revision();

```

## server/go/migrations/382_remove_dingtalk_group_routing_bindings.up.sql

```sql
-- A channel chat session is permanently owned by the agent recorded on its
-- chat_session row. Remove only DingTalk group bindings that still point at an
-- agent other than the installation's default so the next @bot message creates
-- a new session for that default agent. Direct messages, other channels, and
-- groups already owned by the default agent keep their existing context.
WITH removed_bindings AS (
    DELETE FROM channel_chat_session_binding binding
    USING channel_installation installation, chat_session session
    WHERE binding.installation_id = installation.id
      AND binding.chat_session_id = session.id
      AND binding.channel_type = 'dingtalk'
      AND binding.chat_type = 'group'
      AND installation.channel_type = 'dingtalk'
      AND session.agent_id IS DISTINCT FROM installation.agent_id
    RETURNING binding.chat_session_id
)
DELETE FROM channel_outbound_card_message outbound
USING removed_bindings removed
WHERE outbound.chat_session_id = removed.chat_session_id;

```

## server/go/migrations/383_create_dingtalk_group_presence.up.sql

```sql
-- Product-facing DingTalk group inventory. This table records observations and
-- activity only: it deliberately has no agent routing columns or foreign keys.
-- Relationships are enforced and cleaned up by application transactions.
CREATE TABLE dingtalk_group_presence (
    workspace_id         UUID NOT NULL,
    installation_id      UUID NOT NULL,
    conversation_id      TEXT NOT NULL,
    conversation_title   TEXT NOT NULL DEFAULT '',
    bot_name              TEXT NOT NULL DEFAULT '',
    bot_identity_issue    TEXT NOT NULL DEFAULT '',
    first_seen_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at        TIMESTAMPTZ,
    mention_count         BIGINT NOT NULL DEFAULT 0 CHECK (mention_count >= 0),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/384_create_dingtalk_group_presence_identity_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_dingtalk_group_presence_installation_conversation ON dingtalk_group_presence(installation_id, conversation_id);

```

## server/go/migrations/385_create_dingtalk_group_presence_activity_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dingtalk_group_presence_workspace_activity ON dingtalk_group_presence(workspace_id, last_active_at DESC NULLS LAST, installation_id, conversation_id);

```

## server/go/migrations/386_backfill_dingtalk_group_presence.up.sql

```sql
-- Keep accepting writes from an older server process during a mixed-version
-- rollout. Old discovery writes do not expose bot identity, but they must not
-- disappear after the one-time backfill. A route revision change is an admin
-- routing edit, not observed message activity, so it only refreshes the title.
CREATE OR REPLACE FUNCTION mirror_legacy_dingtalk_group_route_presence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    is_activity BOOLEAN;
BEGIN
    is_activity := TG_OP = 'INSERT';
    IF TG_OP = 'UPDATE' THEN
        is_activity := NEW.revision = OLD.revision;
    END IF;

    INSERT INTO dingtalk_group_presence (
        workspace_id,
        installation_id,
        conversation_id,
        conversation_title,
        first_seen_at,
        last_active_at,
        mention_count
    ) VALUES (
        NEW.workspace_id,
        NEW.installation_id,
        NEW.conversation_id,
        NEW.conversation_title,
        NEW.discovered_at,
        CASE WHEN is_activity THEN now() ELSE NULL END,
        CASE WHEN is_activity THEN 1 ELSE 0 END
    )
    ON CONFLICT (installation_id, conversation_id) DO UPDATE SET
        workspace_id = EXCLUDED.workspace_id,
        conversation_title = CASE
            WHEN EXCLUDED.conversation_title <> '' THEN EXCLUDED.conversation_title
            ELSE dingtalk_group_presence.conversation_title
        END,
        first_seen_at = LEAST(dingtalk_group_presence.first_seen_at, EXCLUDED.first_seen_at),
        last_active_at = CASE
            WHEN is_activity THEN now()
            ELSE dingtalk_group_presence.last_active_at
        END,
        mention_count = dingtalk_group_presence.mention_count + CASE WHEN is_activity THEN 1 ELSE 0 END,
        updated_at = now();

    RETURN NEW;
END;
$$;

DO $$
BEGIN
    IF to_regclass('dingtalk_group_route') IS NOT NULL THEN
        EXECUTE 'CREATE TRIGGER mirror_legacy_dingtalk_group_route_presence
            AFTER INSERT OR UPDATE ON dingtalk_group_route
            FOR EACH ROW
            EXECUTE FUNCTION mirror_legacy_dingtalk_group_route_presence()';
    END IF;
END;
$$;

-- Historical route rows prove that a bot was discovered in a group and retain
-- its title. They do not prove when a message was last processed, so activity
-- remains unknown until a new addressed message succeeds.
-- A draft build briefly persisted observed titles in installation config. This
-- source also makes upgrades from that build recoverable if it already dropped
-- the legacy route table.
INSERT INTO dingtalk_group_presence (
    workspace_id, installation_id, conversation_id, conversation_title,
    bot_name, bot_identity_issue
)
SELECT
    installation.workspace_id,
    installation.id,
    groups.conversation_id,
    groups.conversation_title,
    COALESCE(installation.config -> 'group_bot_names' ->> groups.conversation_id, ''),
    COALESCE(installation.config -> 'group_bot_identity_issues' ->> groups.conversation_id, '')
FROM channel_installation installation
CROSS JOIN LATERAL jsonb_each_text(
    CASE
        WHEN jsonb_typeof(installation.config -> 'group_titles') = 'object'
            THEN installation.config -> 'group_titles'
        ELSE '{}'::jsonb
    END
) AS groups(conversation_id, conversation_title)
WHERE installation.channel_type = 'dingtalk'
ON CONFLICT (installation_id, conversation_id) DO UPDATE SET
    conversation_title = CASE
        WHEN dingtalk_group_presence.conversation_title = '' AND EXCLUDED.conversation_title <> ''
            THEN EXCLUDED.conversation_title
        ELSE dingtalk_group_presence.conversation_title
    END,
    bot_name = CASE
        WHEN EXCLUDED.bot_name <> '' THEN EXCLUDED.bot_name
        ELSE dingtalk_group_presence.bot_name
    END,
    bot_identity_issue = CASE
        WHEN EXCLUDED.bot_identity_issue <> '' THEN EXCLUDED.bot_identity_issue
        ELSE dingtalk_group_presence.bot_identity_issue
    END,
    updated_at = now();

DO $$
BEGIN
    IF to_regclass('dingtalk_group_route') IS NOT NULL THEN
        EXECUTE $backfill$
            INSERT INTO dingtalk_group_presence (
                workspace_id, installation_id, conversation_id,
                conversation_title, first_seen_at
            )
            SELECT
                workspace_id, installation_id, conversation_id,
                conversation_title, discovered_at
            FROM dingtalk_group_route
            ON CONFLICT (installation_id, conversation_id) DO UPDATE SET
                conversation_title = CASE
                    WHEN dingtalk_group_presence.conversation_title = ''
                         AND EXCLUDED.conversation_title <> ''
                        THEN EXCLUDED.conversation_title
                    ELSE dingtalk_group_presence.conversation_title
                END,
                first_seen_at = LEAST(
                    dingtalk_group_presence.first_seen_at,
                    EXCLUDED.first_seen_at
                ),
                updated_at = now()
        $backfill$;
    END IF;
END;
$$;

```

## server/go/migrations/387_create_dingtalk_bot_identity.up.sql

```sql
-- Bot identity belongs to one DingTalk installation, independently of how many
-- groups have been observed or forgotten. Relationships are enforced and
-- cleaned up by application transactions; no foreign keys are added.
CREATE TABLE dingtalk_bot_identity (
    workspace_id       UUID NOT NULL,
    installation_id    UUID NOT NULL,
    bot_name            TEXT NOT NULL DEFAULT '',
    bot_identity_issue  TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/388_create_dingtalk_bot_identity_installation_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_dingtalk_bot_identity_installation ON dingtalk_bot_identity(installation_id);

```

## server/go/migrations/389_backfill_dingtalk_bot_identity.up.sql

```sql
-- During a mixed-version rollout, a process from the previous draft may still
-- write identity values to group-presence rows. Mirror those writes into the
-- installation-level identity without treating empty transient lookups as new
-- information.
CREATE OR REPLACE FUNCTION mirror_dingtalk_group_presence_bot_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.bot_name = '' AND NEW.bot_identity_issue = '' THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM dingtalk_bot_identity identity
        WHERE identity.installation_id = NEW.installation_id
          AND identity.workspace_id = NEW.workspace_id
          AND identity.bot_name = NEW.bot_name
          AND identity.bot_identity_issue = NEW.bot_identity_issue
    ) THEN
        RETURN NEW;
    END IF;

    INSERT INTO dingtalk_bot_identity (
        workspace_id, installation_id, bot_name, bot_identity_issue
    ) VALUES (
        NEW.workspace_id, NEW.installation_id, NEW.bot_name, NEW.bot_identity_issue
    )
    ON CONFLICT (installation_id) DO UPDATE SET
        workspace_id = EXCLUDED.workspace_id,
        bot_name = CASE
            WHEN EXCLUDED.bot_name <> '' THEN EXCLUDED.bot_name
            ELSE dingtalk_bot_identity.bot_name
        END,
        bot_identity_issue = CASE
            WHEN EXCLUDED.bot_identity_issue <> '' THEN EXCLUDED.bot_identity_issue
            WHEN EXCLUDED.bot_name <> '' THEN ''
            ELSE dingtalk_bot_identity.bot_identity_issue
        END,
        updated_at = now();

    RETURN NEW;
END;
$$;

CREATE TRIGGER mirror_dingtalk_group_presence_bot_identity
AFTER INSERT OR UPDATE OF bot_name, bot_identity_issue ON dingtalk_group_presence
FOR EACH ROW
EXECUTE FUNCTION mirror_dingtalk_group_presence_bot_identity();

-- Prefer normalized observations, then recover identity written by the brief
-- config-backed draft. Empty rows are still useful: they preserve the fact that
-- an installation has been observed without inventing a readable Bot name.
INSERT INTO dingtalk_bot_identity (
    workspace_id, installation_id, bot_name, bot_identity_issue
)
SELECT
    installation.workspace_id,
    installation.id,
    COALESCE(presence.bot_name, config_name.bot_name, ''),
    COALESCE(presence.bot_identity_issue, config_issue.bot_identity_issue, '')
FROM channel_installation installation
LEFT JOIN LATERAL (
    SELECT
        max(NULLIF(bot_name, ''))::text AS bot_name,
        max(NULLIF(bot_identity_issue, ''))::text AS bot_identity_issue
    FROM dingtalk_group_presence
    WHERE installation_id = installation.id
) presence ON true
LEFT JOIN LATERAL (
    SELECT max(NULLIF(value, ''))::text AS bot_name
    FROM jsonb_each_text(
        CASE
            WHEN jsonb_typeof(installation.config -> 'group_bot_names') = 'object'
                THEN installation.config -> 'group_bot_names'
            ELSE '{}'::jsonb
        END
    )
) config_name ON true
LEFT JOIN LATERAL (
    SELECT max(NULLIF(value, ''))::text AS bot_identity_issue
    FROM jsonb_each_text(
        CASE
            WHEN jsonb_typeof(installation.config -> 'group_bot_identity_issues') = 'object'
                THEN installation.config -> 'group_bot_identity_issues'
            ELSE '{}'::jsonb
        END
    )
) config_issue ON true
WHERE installation.channel_type = 'dingtalk'
ON CONFLICT (installation_id) DO UPDATE SET
    workspace_id = EXCLUDED.workspace_id,
    bot_name = CASE
        WHEN EXCLUDED.bot_name <> '' THEN EXCLUDED.bot_name
        ELSE dingtalk_bot_identity.bot_name
    END,
    bot_identity_issue = CASE
        WHEN EXCLUDED.bot_identity_issue <> '' THEN EXCLUDED.bot_identity_issue
        ELSE dingtalk_bot_identity.bot_identity_issue
    END,
    updated_at = now();

```

## server/go/migrations/390_agent_task_queue_dispatched_reclaim_v2_index.up.sql

```sql
-- Put dispatched_at directly after runtime_id so stale-reclaim scans can use
-- both equality and time-range conditions before applying the priority sort.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_dispatched_reclaim_v2
    ON agent_task_queue (runtime_id, dispatched_at ASC, priority DESC)
    WHERE status = 'dispatched' AND started_at IS NULL;

```

## server/go/migrations/391_drop_agent_task_queue_dispatched_prepare_index.up.sql

```sql
-- Migration 390 replaces this index with the same partial predicate and a key
-- order that makes dispatched_at usable as a stale-reclaim range condition.
DROP INDEX CONCURRENTLY IF EXISTS idx_agent_task_queue_dispatched_prepare;

```

## server/go/migrations/392_plugin_package_publishing.up.sql

```sql
-- Platform-hosted plugin artifacts.
--
-- Until now a plugin was a URL: the manifest was fetched once and frozen as the
-- consented snapshot, but the surface script was loaded from the author's server
-- every time a panel opened. So the administrator consented to a manifest while
-- the browser ran whatever code that host served that day, the author's uptime
-- became our uptime, and every panel open told the author who was reading which
-- issue.
--
-- What replaces it: the author uploads an artifact bundle, Workpal stores it,
-- and an installation is bound to one immutable version. Nothing about a
-- published version is ever updated in place — a new publish is a new row, and
-- an installed workspace keeps running the version it consented to until an
-- administrator upgrades it.
--
-- Hook endpoints and MCP servers stay on the author's own infrastructure. Only
-- the frontend artifact moved.

-- One publishable plugin identity per workspace. Publishing is workspace-private
-- for now; a public directory needs review, reporting and takedown, which is a
-- separate decision from where the bytes live.
CREATE TABLE plugin_package (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    plugin_key TEXT NOT NULL CHECK (char_length(plugin_key) BETWEEN 3 AND 255),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 160),
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One published version. Immutable by construction: no statement in the
-- application updates this row, and republishing an existing version is a
-- conflict rather than an overwrite. That is the whole point — "what the admin
-- approved" and "what the browser runs" have to name the same bytes.
--
-- workspace_id is denormalized so every read can be scoped without joining
-- through plugin_package; relationships stay application-owned by repository
-- policy, so there is no foreign key to join through cheaply anyway.
CREATE TABLE plugin_package_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    version TEXT NOT NULL CHECK (char_length(version) BETWEEN 1 AND 64),
    manifest JSONB NOT NULL CHECK (jsonb_typeof(manifest) = 'object'),
    -- sha256 of the uploaded bundle, hex. Shown to the publisher so two people
    -- can confirm they are looking at the same artifact.
    digest TEXT NOT NULL CHECK (char_length(digest) = 64),
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    published_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The files a version ships: the surface scripts, the skill text, the icon.
--
-- Stored in Postgres rather than object storage. A bundle is capped at a few
-- hundred kilobytes by the service, and this way an installed plugin cannot be
-- half-available: the manifest snapshot and the code it names commit together
-- and are restored together. Object storage would reintroduce, against our own
-- bucket, exactly the availability split this change exists to remove.
CREATE TABLE plugin_package_file (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL,
    path TEXT NOT NULL CHECK (char_length(path) BETWEEN 1 AND 1024),
    content BYTEA NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    sha256 TEXT NOT NULL CHECK (char_length(sha256) = 64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every existing installation names a source URL, which is no longer a concept.
-- There is nothing to migrate them to: the code they would run was never
-- published here, so binding them to a version would be an invention. plugins_v1
-- has never left its feature flag and holds no production data, so they are
-- removed — the same call migration 344 made for the same reason.
DELETE FROM skill WHERE plugin_installation_id IS NOT NULL;
DELETE FROM plugin_invocation;
DELETE FROM plugin_secret;
DELETE FROM plugin_storage;
DELETE FROM plugin_installation;

ALTER TABLE plugin_installation DROP COLUMN IF EXISTS source_url;
ALTER TABLE plugin_installation ADD COLUMN package_version_id UUID NOT NULL;

```

## server/go/migrations/393_plugin_package_workspace_key_index.up.sql

```sql
-- One package per plugin key per workspace: publishing a new version of an
-- existing key must find the same package, not create a second one.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_package_workspace_key
    ON plugin_package (workspace_id, plugin_key);

```

## server/go/migrations/394_plugin_package_version_unique_index.up.sql

```sql
-- A version is published once. This index is what makes immutability a database
-- rule rather than a convention the service is trusted to keep.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_package_version_unique
    ON plugin_package_version (package_id, version);

```

## server/go/migrations/395_plugin_package_version_package_index.up.sql

```sql
-- The version list a publisher reads: newest first, per package.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_package_version_package
    ON plugin_package_version (package_id, created_at DESC);

```

## server/go/migrations/396_plugin_package_file_path_index.up.sql

```sql
-- Serving one file of a version is a point lookup by path, and a bundle must not
-- be able to ship the same path twice.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_package_file_path
    ON plugin_package_file (version_id, path);

```

## server/go/migrations/397_plugin_installation_package_version_index.up.sql

```sql
-- Deleting a published version has to know whether any workspace still runs it.
-- Without this index that check is a sequential scan on every publish page load.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_installation_package_version
    ON plugin_installation (package_version_id);

```

## server/go/migrations/398_issue_workspace_status_position_index.up.sql

```sql
-- Re-ranking an issue into a new column reads MIN(position) for the
-- destination (workspace_id, status). idx_issue_status stops at
-- (workspace_id, status), so that min costs a heap fetch per issue in the
-- column -- paid on every status change, most often against Done, the column
-- that grows without bound. Carrying position in the index makes it an
-- index-only min. New-issue creation takes the same min and benefits equally.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_workspace_status_position
    ON issue (workspace_id, status, position);

```

## server/go/migrations/399_plugin_hook_schedule.up.sql

```sql
-- Durable schedule declarations for Plugin HTTP hooks. The consented manifest
-- remains the public source of truth; this table is the execution projection
-- that gives each installed hook an activation epoch and a stable scheduler
-- scope without reparsing every installation on every tick.
--
-- Relationships are application-owned by repository policy: install, upgrade,
-- enable/disable, uninstall and workspace teardown reconcile these rows in the
-- same transaction as plugin_installation. No foreign key or cascade is used.
CREATE TABLE plugin_hook_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    hook_key TEXT NOT NULL CHECK (char_length(hook_key) BETWEEN 1 AND 128),
    cron_expression TEXT NOT NULL CHECK (char_length(cron_expression) BETWEEN 1 AND 255),
    timezone TEXT NOT NULL CHECK (char_length(timezone) BETWEEN 1 AND 255),
    generation UUID NOT NULL DEFAULT gen_random_uuid(),
    activated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Display-only projection. Dispatch correctness is recovered from cron +
    -- activated_at + sys_cron_executions even when this value is stale/NULL.
    next_run_at TIMESTAMPTZ,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Schedule attempts use the same operational invocation table as every other
-- Hook trigger. delivery_id is stable across retries; planned_at is the cron
-- occurrence, distinct from created_at (the actual attempt time).
ALTER TABLE plugin_invocation
    ADD COLUMN delivery_id TEXT CHECK (delivery_id IS NULL OR char_length(delivery_id) BETWEEN 1 AND 128),
    ADD COLUMN planned_at TIMESTAMPTZ;

ALTER TABLE plugin_invocation DROP CONSTRAINT IF EXISTS plugin_invocation_trigger_check;
ALTER TABLE plugin_invocation ADD CONSTRAINT plugin_invocation_trigger_check
    CHECK (trigger IN ('ui', 'manual', 'event', 'agent', 'schedule')) NOT VALID;

```

## server/go/migrations/400_plugin_hook_schedule_installation_key_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_hook_schedule_installation_key
    ON plugin_hook_schedule (installation_id, hook_key);

```

## server/go/migrations/401_plugin_hook_schedule_enabled_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_plugin_hook_schedule_enabled
    ON plugin_hook_schedule (id)
    WHERE enabled;

```

## server/go/migrations/402_plugin_invocation_schedule_trigger_validate.up.sql

```sql
ALTER TABLE plugin_invocation VALIDATE CONSTRAINT plugin_invocation_trigger_check;

```

## server/go/migrations/403_runtime_profile_add_zeroclaw.up.sql

```sql
-- Add ZeroClaw as a first-party ACP protocol family. NOT VALID preserves
-- historical-row tolerance while enforcing the expanded whitelist for new rows.
-- The whitelist includes dim (added by migration 370) and zeroclaw.
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'reasonix',
        'dsh',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw',
        'mcode',
        'dim',
        'zeroclaw'
    )) NOT VALID;

```

## server/go/migrations/404_agent_starter_prompts.up.sql

```sql
ALTER TABLE agent
ADD COLUMN starter_prompts JSONB NOT NULL DEFAULT '[]'::jsonb
CHECK (
    jsonb_typeof(starter_prompts) = 'array'
    AND jsonb_array_length(starter_prompts) <= 3
);

```

## server/go/migrations/407_issue_source_context.up.sql

```sql
CREATE TABLE issue_source_context (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    issue_id UUID,
    origin_task_id UUID,
    source_issue_id UUID NOT NULL,
    anchor_comment_id UUID NOT NULL,
    captured_by_user_id UUID NOT NULL,
    snapshot_version SMALLINT NOT NULL,
    snapshot JSONB NOT NULL,
    capture_digest TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending', 'attached', 'abandoned')),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    attached_at TIMESTAMPTZ,
    CHECK (
        (state = 'pending' AND issue_id IS NULL AND origin_task_id IS NOT NULL AND attached_at IS NULL)
        OR (state = 'attached' AND issue_id IS NOT NULL AND attached_at IS NOT NULL)
        OR (state = 'abandoned' AND issue_id IS NULL AND attached_at IS NULL)
    )
);

ALTER TABLE attachment ADD COLUMN source_context_id UUID;

CREATE TABLE issue_source_context_object_intent (
    storage_key TEXT NOT NULL,
    workspace_id UUID NOT NULL,
    source_context_id UUID NOT NULL,
    attachment_id UUID NOT NULL,
    object_url TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'deleting')),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/408_issue_source_context_id_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_issue_source_context_id ON issue_source_context (id);

```

## server/go/migrations/409_issue_source_context_issue_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_issue_source_context_issue ON issue_source_context (issue_id) WHERE state = 'attached' AND issue_id IS NOT NULL;

```

## server/go/migrations/410_issue_source_context_origin_task_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_issue_source_context_origin_task ON issue_source_context (origin_task_id) WHERE state = 'pending' AND origin_task_id IS NOT NULL;

```

## server/go/migrations/411_attachment_source_context_index.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_attachment_source_context ON attachment (source_context_id) WHERE source_context_id IS NOT NULL;

```

## server/go/migrations/412_issue_source_context_object_intent_key_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_issue_source_context_object_intent_key ON issue_source_context_object_intent (storage_key);

```

## server/go/migrations/413_issue_source_context_object_intent_due_index.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_issue_source_context_object_intent_due ON issue_source_context_object_intent (next_attempt_at) WHERE state IN ('pending', 'deleting');

```

## server/go/migrations/414_issue_source_context_object_intent_context_index.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_issue_source_context_object_intent_context ON issue_source_context_object_intent (source_context_id);

```

## server/go/migrations/415_seat_capacity_outbox.up.sql

```sql
-- Product-side durable intents for Cloud's pre-purchased seat protocol. This
-- table contains no commercial limits; it only records cross-service writes
-- until their idempotent Cloud operation is settled.
CREATE TABLE seat_capacity_outbox (
    workspace_id UUID NOT NULL,
    operation_token UUID NOT NULL,
    action TEXT NOT NULL CHECK (action IN (
        'reserve_invitation',
        'consume_invitation',
        'claim_share_join',
        'confirm',
        'release',
        'release_member'
    )),
    subject_id UUID,
    member_id UUID,
    invitation_id UUID,
    share_link_id UUID,
    user_id UUID,
    expires_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_token UUID,
    last_error TEXT,
    dead_lettered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((action <> 'reserve_invitation') OR (invitation_id IS NOT NULL AND expires_at IS NOT NULL)),
    CHECK ((action <> 'consume_invitation') OR (invitation_id IS NOT NULL AND user_id IS NOT NULL)),
    CHECK ((action <> 'claim_share_join') OR (share_link_id IS NOT NULL AND user_id IS NOT NULL)),
    CHECK ((action <> 'confirm') OR member_id IS NOT NULL),
    CHECK ((action <> 'release_member') OR member_id IS NOT NULL)
);

```

## server/go/migrations/416_seat_capacity_operation_token_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_seat_capacity_outbox_operation_token
    ON seat_capacity_outbox(operation_token);

```

## server/go/migrations/417_seat_capacity_primary_key.up.sql

```sql
ALTER TABLE seat_capacity_outbox
    ADD CONSTRAINT seat_capacity_outbox_pkey
    PRIMARY KEY USING INDEX idx_seat_capacity_outbox_operation_token;

```

## server/go/migrations/418_seat_capacity_due_index.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_seat_capacity_outbox_due
    ON seat_capacity_outbox(next_attempt_at, created_at)
    WHERE dead_lettered_at IS NULL;

```

## server/go/migrations/419_seat_capacity_share_join_index.up.sql

```sql
-- One user joining through one share link must keep one Cloud operation until
-- that operation is settled, including while it is dead-lettered or releasing.
CREATE UNIQUE INDEX CONCURRENTLY idx_seat_capacity_outbox_share_join
    ON seat_capacity_outbox(workspace_id, share_link_id, user_id)
    WHERE share_link_id IS NOT NULL AND user_id IS NOT NULL;

```

## server/go/migrations/420_channel_chat_route_generation.up.sql

```sql
-- Channel Chat route migration.
ALTER TABLE channel_chat_session_binding
    ADD COLUMN route_revision BIGINT NOT NULL DEFAULT 1,
    ADD COLUMN retired_at TIMESTAMPTZ,
    ADD COLUMN history_start_message_id TEXT,
    ADD COLUMN history_end_message_id TEXT,
    ADD COLUMN history_boundary_pending BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE chat_session
    ADD COLUMN explicitly_created_at TIMESTAMPTZ;

CREATE TABLE channel_task_delivery (
    task_id             UUID NOT NULL,
    binding_id          UUID NOT NULL,
    installation_id     UUID NOT NULL,
    channel_type        TEXT NOT NULL,
    channel_chat_id     TEXT NOT NULL,
    chat_type           TEXT NOT NULL,
    channel_message_id  TEXT,
    channel_thread_id   TEXT,
    route_revision      BIGINT NOT NULL,
    config              JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/421_channel_chat_active_route_index.up.sql

```sql
-- Channel Chat route migration.
CREATE UNIQUE INDEX CONCURRENTLY idx_channel_chat_session_binding_active_route ON channel_chat_session_binding (installation_id, channel_chat_id) WHERE retired_at IS NULL;

```

## server/go/migrations/422_channel_chat_route_history.up.sql

```sql
-- Channel Chat route migration.
ALTER TABLE channel_chat_session_binding DROP CONSTRAINT IF EXISTS channel_chat_session_binding_installation_id_channel_chat_i_key;
DROP INDEX IF EXISTS channel_chat_session_binding_installation_id_channel_chat_i_key;

```

## server/go/migrations/423_channel_task_delivery_pkey_index.up.sql

```sql
-- Channel Chat route migration.
CREATE UNIQUE INDEX CONCURRENTLY channel_task_delivery_pkey ON channel_task_delivery (task_id);

```

## server/go/migrations/424_channel_task_delivery_primary_key.up.sql

```sql
-- Promote the concurrently-built unique index without rebuilding it or
-- holding a long index-build lock on channel_task_delivery.
ALTER TABLE channel_task_delivery
    ADD CONSTRAINT channel_task_delivery_pkey
    PRIMARY KEY USING INDEX channel_task_delivery_pkey;

```

## server/go/migrations/425_channel_outbound_message.up.sql

```sql
-- Channel Chat route migration.
CREATE TABLE channel_outbound_message (
    installation_id   UUID NOT NULL,
    channel_type      TEXT NOT NULL,
    channel_message_id TEXT NOT NULL,
    binding_id        UUID NOT NULL,
    route_revision    BIGINT NOT NULL,
    task_id           UUID,
    outbound_kind     TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/426_channel_outbound_message_id_index.up.sql

```sql
-- Channel Chat route migration.
CREATE UNIQUE INDEX CONCURRENTLY idx_channel_outbound_message_id ON channel_outbound_message (installation_id, channel_message_id);

```

## server/go/migrations/427_channel_task_delivery_backfill.up.sql

```sql
-- Channel Chat route migration.
INSERT INTO channel_task_delivery (
    task_id, binding_id, installation_id, channel_type, channel_chat_id, chat_type,
    channel_message_id, channel_thread_id, route_revision, config
)
SELECT
    task.id, binding.id, binding.installation_id, binding.channel_type,
    binding.channel_chat_id, binding.chat_type, binding.last_message_id, binding.last_thread_id,
    binding.route_revision, binding.config
FROM agent_task_queue AS task
JOIN channel_chat_session_binding AS binding
  ON binding.chat_session_id = task.chat_session_id
WHERE task.status IN ('queued', 'deferred', 'dispatched', 'running', 'waiting_local_directory')
  AND EXISTS (
      SELECT 1 FROM chat_message AS message
      WHERE message.task_id = COALESCE(task.chat_input_task_id, task.id)
        AND message.role = 'user'
        AND message.channel_ingested
  )
ON CONFLICT (task_id) DO NOTHING;

```

## server/go/migrations/428_channel_task_delivery_binding_index.up.sql

```sql
-- Channel Chat route migration.
CREATE INDEX CONCURRENTLY idx_channel_task_delivery_binding ON channel_task_delivery (binding_id);

```

## server/go/migrations/429_channel_task_delivery_installation_index.up.sql

```sql
-- Channel Chat route migration.
CREATE INDEX CONCURRENTLY idx_channel_task_delivery_installation ON channel_task_delivery (installation_id);

```

## server/go/migrations/430_channel_outbound_message_binding_index.up.sql

```sql
-- Channel Chat route migration.
CREATE INDEX CONCURRENTLY idx_channel_outbound_message_binding_route ON channel_outbound_message (binding_id, route_revision);

```

## server/go/migrations/431_chat_explicit_origin_backfill.up.sql

```sql
-- The idempotent pre-migration hook performs the legacy Chat origin backfill
-- in short primary-key pages before this marker is recorded.
SELECT 1;

```

## server/go/migrations/432_agent_conversation_starters_rename.up.sql

```sql
-- Rename the agent starter-prompts column to the product name it ships under.
-- The feature is unreleased (the column arrived in migration 404, after the
-- last release tag), so this is a pure rename with no compatibility window:
-- no deployed client reads the old name. Both statements are sent in one
-- migration query and therefore commit atomically.
ALTER TABLE agent
    RENAME COLUMN starter_prompts TO conversation_starters;

ALTER TABLE agent
    RENAME CONSTRAINT agent_starter_prompts_check
    TO agent_conversation_starters_check;

```

## server/go/migrations/437_drop_agent_runtime_last_seen_at_index.up.sql

```sql
DROP INDEX CONCURRENTLY IF EXISTS idx_agent_runtime_last_seen_at;

```

## server/go/migrations/438_agent_runtime_online_last_seen_index.up.sql

```sql
-- Keep the 30-second global liveness sweep off agent_runtime's offline
-- history. Only online rows receive heartbeat writes, and that set is small;
-- the partial index preserves the range predicate without restoring the
-- retired full-table last_seen_at index.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_runtime_online_last_seen
    ON agent_runtime (last_seen_at)
    WHERE status = 'online';

```

## server/go/migrations/439_agent_runtime_offline_last_seen_index.up.sql

```sql
-- Runtime GC orders stale offline candidates by last_seen_at and takes a
-- bounded prefix. Offline heartbeat timestamps are stable, so this partial
-- index removes the full-table sort with negligible steady-state write cost.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_runtime_offline_last_seen
    ON agent_runtime (last_seen_at, id)
    WHERE status = 'offline';

```

## server/go/migrations/440_github_pr_head_sha_index.up.sql

```sql
-- Head SHA is selective enough to narrow the CI-webhook fallback to the few
-- mirrored rows whose installation and repository are then checked by SQL.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_github_pull_request_head_sha
    ON github_pull_request (head_sha);

```

## server/go/migrations/441_runtime_profile_add_codearts.up.sql

```sql
-- Add Huawei Cloud CodeArts Agent as a first-party protocol family. NOT VALID
-- preserves historical-row tolerance while enforcing the expanded whitelist
-- for new rows.
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'codearts',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'reasonix',
        'dsh',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw',
        'mcode',
        'dim',
        'zeroclaw'
    )) NOT VALID;

```

## server/go/migrations/442_vcs_reference_only_repair.up.sql

```sql
-- Repair installations where issue_vcs_pull_request was created by an early
-- VCS integration build before reference_only was present. Migration 216 uses
-- CREATE TABLE IF NOT EXISTS, so rerunning it cannot reconcile that partial
-- schema once its version is recorded.
ALTER TABLE issue_vcs_pull_request
    ADD COLUMN IF NOT EXISTS reference_only BOOLEAN NOT NULL DEFAULT FALSE;

```

## server/go/migrations/443_issue_project_status_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_project_status
    ON issue (project_id, workspace_id, status);

```

## server/go/migrations/444_comment_recovery_settled_at.up.sql

```sql
-- Durable "this delegated-failure recovery is finished" marker.
--
-- The recovery outbox scan (ListPendingDelegatedFailureRecoveries) had no
-- indexable settled state: every recovery comment ever written stayed in the
-- candidate partial index from migration 343 forever, and each sweeper tick
-- re-proved through four joins and two NOT EXISTS subqueries that it was
-- already handled. LIMIT bounded the rows RETURNED, never the rows CHECKED, so
-- a tick that found nothing still grew more expensive as history accumulated.
--
-- This column is that missing state. It is written only inside the transaction
-- that makes a task terminal, and only for recovery comments already present in
-- that task's delivered_comment_ids receipt — the one condition in the scan
-- that is monotonic. A NULL therefore means "not proven finished", which is the
-- safe direction: an unmarked row is still scanned exactly as it is today and
-- no recovery can be lost, while a marked row is provably settled.
--
-- Nullable with no default keeps this metadata-only and instant on a hot table,
-- the same reason comment.quick_action_id (239) and comment.via_plugin_id (348)
-- are shaped this way. No FK per repository policy.
--
-- The matching partial index is migration 445: PostgreSQL rejects CREATE INDEX
-- CONCURRENTLY in a multi-command string, so the two cannot share a file.
ALTER TABLE comment ADD COLUMN IF NOT EXISTS recovery_settled_at TIMESTAMPTZ;

```

## server/go/migrations/445_comment_delegated_failure_unsettled_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_comment_delegated_failure_unsettled
ON comment (created_at, id)
WHERE author_type = 'system'
  AND type = 'progress_update'
  AND source_task_id IS NOT NULL
  AND recovery_settled_at IS NULL;

```

## server/go/migrations/446_issue_properties_bigm_index.up.sql

```sql
-- Bigram GIN index behind the lossy prefilter that scalar `contains` property
-- filtering puts in front of its per-key ILIKE check (MUL-6928). Without it a
-- contains filter cannot reach any index and degrades to a workspace-wide
-- sequential scan: on a 1M-issue workspace throughput drops ~8x against an
-- equality filter, which does reach idx_issue_properties_gin.
--
-- LOWER(...) LIKE, not ILIKE: pg_bigm 1.2 (RDS) has no ILIKE index scan, the
-- same constraint migration 036 hit — an ILIKE-shaped predicate would never use
-- this index. The pattern side is lowered in SQL as well so the prefilter folds
-- case exactly the way the ILIKE it guards does.
--
-- Single-statement file because a concurrent build cannot share a migration,
-- and for the same reason it cannot be wrapped in the DO ... EXCEPTION block
-- migrations 032 / 036 use to tolerate a missing pg_bigm. The runner gates this
-- version on the extension instead (issuePropertiesBigramOperatorClass in
-- cmd/migrate): environments without pg_bigm record it with the SQL skipped and
-- keep the unaccelerated — still correct — prefilter. Recovery for a database
-- that installs pg_bigm later is in cmd/migrate/README.md.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_properties_bigm
    ON issue USING gin (LOWER(properties::text) gin_bigm_ops);

```

## server/go/migrations/447_issue_properties_bigm_index_statistics.up.sql

```sql
-- Generate planner statistics for the LOWER(properties::text) expression that
-- migration 446 indexes. Building an expression index does not collect
-- statistics for its expression — the CREATE INDEX docs are explicit that
-- ANALYZE must run, or the autovacuum daemon must analyze the table, before the
-- planner has anything to judge the new index by.
--
-- Without it the index is built, valid, and ignored: an existing issue table
-- gets no statistics row for the expression, the planner falls back to a
-- pattern-length heuristic that estimates a single-character needle at 5% of
-- the table, and a scalar `contains` filter stays on the workspace-wide
-- sequential scan this index exists to remove — now also paying for the
-- prefilter clause on every row. A deployment with no bulk writes cannot rely
-- on autovacuum to fix that promptly: the default threshold is 10% of rows
-- changed, which a large, quiet issue table can take weeks to reach.
--
-- Deliberately not gated on pg_bigm, unlike 446: ANALYZE is valid, cheap and
-- side-effect-free everywhere, and refreshing the table's ordinary column
-- statistics is useful even where the expression index was skipped. It takes
-- ShareUpdateExclusiveLock, which does not block reads or writes.
--
-- Separate file because 446 must stay a single-statement concurrent build.
ANALYZE issue;

```

## server/go/migrations/448_autopilot_quota_rejection_notified_at.up.sql

```sql
ALTER TABLE autopilot_quota_period
    ADD COLUMN rejection_notified_at TIMESTAMPTZ;

```

## server/go/migrations/449_autopilot_trigger_created_by.up.sql

```sql
-- MUL-6951: give autopilot_trigger an IMMUTABLE creator, distinct from
-- published_by.
--
-- Since MUL-6951 a schedule/webhook run acts as a human, so the column naming
-- that human is an authorization input, not an audit label. published_by cannot
-- serve that role: it means "who is currently responsible for this trigger's
-- effective config" and TRANSFERS to whoever last substantively edits the
-- trigger (MUL-4302). Using it would mean a collaborator adjusting a cron
-- expression silently hands the automation their own invoke rights — a change
-- nothing in the UI expresses. Bohan's ruling on the MUL-6951 thread is that the
-- run always acts as the trigger's CREATOR.
--
-- created_by_* is written once at creation and never rewritten by the edit
-- paths; published_by keeps its existing audit meaning unchanged.
--
-- BACKFILL is best-effort and knowingly imprecise. For a trigger nobody has
-- edited, published_by IS the creator and this recovers the right human. For an
-- ALREADY-EDITED trigger it freezes the last recoverable EDITOR as the immutable
-- creator — not necessarily the historical creator, which the schema never
-- recorded and which is therefore unrecoverable.
--
-- This IS a widening, and is accepted as a compatibility tradeoff (MUL-6951, Elon
-- review). Before MUL-6951 an automatic run carried no originator at all, only a
-- set of narrowly-scoped borrow paths; after it, a backfilled editor becomes the
-- run's full originator and it acts with that member's own rights. The
-- alternative — backfilling nothing — stops every existing autopilot, which is
-- why this is preferred over precision here.
--
-- A trigger with no published_by at all (predating migration 189, which added
-- published_by_* to this table) stays NULL.
-- Dispatch then fails closed rather than guessing a principal, and there is
-- deliberately NO recovery path — re-saving such a trigger re-stamps published_by,
-- not created_by, so it stays unresolvable (Bohan: leave them empty). Its runs are
-- refused with a recorded failure_reason.
--
-- The table holds one row per configured trigger (small, bounded by autopilot
-- count), so this runs as a single statement rather than a batched backfill.
--
-- No foreign key by house rule; the referenced member is re-validated in
-- application code on every dispatch, which is what actually matters here since
-- a member can be removed from the workspace long after the row is written.
ALTER TABLE autopilot_trigger ADD COLUMN IF NOT EXISTS created_by_type TEXT;
ALTER TABLE autopilot_trigger ADD COLUMN IF NOT EXISTS created_by_id UUID;

UPDATE autopilot_trigger
SET created_by_type = published_by_type,
    created_by_id = published_by_id
WHERE created_by_id IS NULL
  AND published_by_id IS NOT NULL
  AND published_by_type IS NOT NULL;

-- Migration 189 documented published_by_* as deciding the accountable human of the
-- runs a trigger fires. That is no longer true and the text is generated into
-- pkg/db/generated/models.go, so it would keep asserting the old authorization
-- model to every reader. 189 is already released and must not be edited; override
-- the comments here instead.
COMMENT ON COLUMN autopilot_trigger.published_by_type IS
    'Actor type of the trigger''s current responsible publisher: member | agent. Set to the creator at creation and re-stamped to the editor on any substantive edit governing this trigger. CONFIG audit only — since MUL-6951 it decides nothing about the runs this trigger fires. NULL on triggers predating MUL-4302.';

COMMENT ON COLUMN autopilot_trigger.published_by_id IS
    'The member/agent currently responsible for this trigger''s effective config (creator, then last substantive editor). CONFIG audit only: since MUL-6951 the runs this trigger fires act as, and are accountable to, created_by_id instead, so an edit recorded here never moves a run''s authority. No FK, app-layer integrity (MUL-4302).';

COMMENT ON COLUMN autopilot_trigger.created_by_type IS
    'Actor type of the trigger''s immutable creator: member | agent. Only ''member'' yields a run principal. NULL for triggers created before MUL-6951 that had no published_by to backfill from.';

COMMENT ON COLUMN autopilot_trigger.created_by_id IS
    'The member a schedule/webhook run fires AS: dispatch admission, the task''s originator/accountable, and every delegated run all resolve to this one human (MUL-6951). Written once at creation and never re-stamped, so editing the trigger cannot re-authorize its runs as the editor. NULL means no provable principal and the dispatch fails closed. No FK; workspace membership is re-validated on every dispatch.';

```

## server/go/migrations/450_drop_comment_delegated_failure_pending_index.up.sql

```sql
-- Migration 445 replaced this index with the smaller unsettled-only partial
-- index after the historical recovery backfill completed.
DROP INDEX CONCURRENTLY IF EXISTS idx_comment_delegated_failure_pending;

```

## server/go/migrations/451_agent_task_comment_thread.up.sql

```sql
-- Persist the queue's thread scope so uniqueness remains atomic for every
-- writer, including retries and older clients. This is derived data, not a FK.
ALTER TABLE agent_task_queue ADD COLUMN comment_thread_id uuid;

CREATE FUNCTION comment_thread_root_id(comment_id uuid) RETURNS uuid
LANGUAGE sql STABLE STRICT AS $$
    WITH RECURSIVE ancestors AS (
        SELECT c.id, c.parent_id, c.issue_id, ARRAY[c.id] AS path
        FROM comment c WHERE c.id = comment_id
        UNION ALL
        SELECT p.id, p.parent_id, p.issue_id, a.path || p.id
        FROM ancestors a JOIN comment p ON p.id = a.parent_id AND p.issue_id = a.issue_id
        WHERE NOT p.id = ANY(a.path)
    )
    SELECT COALESCE(
        (SELECT id FROM ancestors ORDER BY cardinality(path) DESC LIMIT 1),
        comment_id
    )
$$;

CREATE FUNCTION set_agent_task_comment_thread() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.comment_thread_id := comment_thread_root_id(NEW.trigger_comment_id);
    RETURN NEW;
END
$$;

CREATE TRIGGER agent_task_comment_thread
BEFORE INSERT OR UPDATE OF trigger_comment_id ON agent_task_queue
FOR EACH ROW EXECUTE FUNCTION set_agent_task_comment_thread();

-- Existing rows intentionally retain a NULL thread scope. Pre-migration tasks
-- drain under the issue/agent claim fence without rewriting historical data.

-- Do NOT add a backfill here. Migration 451 originally shipped one and it was
-- removed: rewriting the whole historical queue at startup is unsafe against
-- production data volume, and there is nothing to gain — the only rows without
-- a thread scope are the tasks in flight during the rolling deploy, and their
-- historical thread scope has no value. #8229 proposed doing it again as
-- migration 457 and was closed for the same reason.

```

## server/go/migrations/452_agent_task_pending_thread_unique.up.sql

```sql
-- Build the new guard before retiring the issue-wide guard.
CREATE UNIQUE INDEX CONCURRENTLY idx_one_pending_task_per_issue_agent_thread
    ON agent_task_queue (issue_id, agent_id, COALESCE(comment_thread_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE status IN ('queued', 'dispatched')
       OR (status = 'deferred' AND context->>'channel_issue_media_pending' = 'true');

```

## server/go/migrations/453_drop_pending_issue_agent_unique.up.sql

```sql
DROP INDEX CONCURRENTLY IF EXISTS idx_one_pending_task_per_issue_agent_v2;

```

## server/go/migrations/454_drop_comment_content_bigm_index.up.sql

```sql
-- SearchIssues now scans comments by workspace and evaluates content matches
-- during aggregation, so this global content GIN is no longer read.
DROP INDEX CONCURRENTLY IF EXISTS idx_comment_content_bigm;

```

## server/go/migrations/455_drop_comment_content_trgm_index.up.sql

```sql
-- Retire the portable fallback for the same workspace-first SearchIssues path.
-- Keep this separate because concurrent index DDL must be the only statement.
DROP INDEX CONCURRENTLY IF EXISTS idx_comment_content_trgm;

```

## server/go/migrations/456_cancel_comment_assignee_fallbacks.up.sql

```sql
-- Comment replies no longer escalate to the issue assignee. Retire old
-- fallback tasks and their automatic retries that have not started; preserve
-- running tasks, completed history, and user-requested reruns.
-- Stop old API instances before running this one-time cleanup: they can still
-- enqueue new fallback rows after it finishes. The Helm Recreate deployment
-- and migrate-before-server entrypoint provide this ordering.
WITH RECURSIVE fallback_lineage AS (
    SELECT task.id AS task_id,
        task.escalation_for_task_id,
        ARRAY[task.id] AS path
    FROM agent_task_queue task
    WHERE task.escalation_for_task_id IS NOT NULL
      -- CreateDeferredAgentTask never set retry_of_task_id. Excluding retry
      -- descendants backfilled by an earlier idempotent run keeps one root per
      -- lineage instead of rediscovering every suffix as a separate tree.
      AND task.retry_of_task_id IS NULL

    UNION ALL

    -- CreateRetryTask stores both links to the same immediate parent but does
    -- not copy escalation_for_task_id. Following the indexed parent_task_id
    -- finds descendants without scanning the whole queue; retry_of_task_id
    -- keeps user-requested reruns outside this cleanup.
    SELECT retry.id,
        lineage.escalation_for_task_id,
        lineage.path || retry.id
    FROM fallback_lineage lineage
    JOIN agent_task_queue retry
      ON retry.parent_task_id = lineage.task_id
     AND retry.retry_of_task_id = lineage.task_id
    -- Stored retry links should be acyclic, but corrupt historical data must
    -- not make a startup migration recurse forever.
    WHERE NOT retry.id = ANY(lineage.path)
), cancelled AS (
    UPDATE agent_task_queue task
    SET status = 'cancelled',
        completed_at = now(),
        prepare_lease_expires_at = NULL,
        escalation_for_task_id = fallback_lineage.escalation_for_task_id
    FROM fallback_lineage
    WHERE task.id = fallback_lineage.task_id
      AND task.started_at IS NULL
      -- An unstarted fallback may have absorbed newer comments while queued.
      -- Preserve it so those merged instructions still receive their run.
      AND cardinality(task.coalesced_comment_ids) = 0
      AND task.status IN ('deferred', 'queued', 'dispatched', 'waiting_local_directory')
    RETURNING task.id, task.agent_id
), desired AS (
    SELECT DISTINCT cancelled.agent_id,
        CASE WHEN EXISTS (
            SELECT 1 FROM agent_task_queue task
            WHERE task.agent_id = cancelled.agent_id
              AND task.status IN ('dispatched', 'running')
              -- Data-modifying CTEs share a snapshot. Exclude the returned
              -- rows explicitly rather than reading their old task status.
              AND NOT EXISTS (SELECT 1 FROM cancelled c WHERE c.id = task.id)
        ) THEN 'working' ELSE 'idle' END AS status
    FROM cancelled
)
UPDATE agent
SET status = desired.status, updated_at = now()
FROM desired
WHERE agent.id = desired.agent_id AND agent.status IS DISTINCT FROM desired.status;

```

## server/go/migrations/457_task_message_output_truncated.up.sql

```sql
-- Records whether a tool_result's stored output dropped bytes to fit the
-- daemon's preview budget.
--
-- Nullable with NO DEFAULT, and deliberately not backfilled. Three states:
--   NULL  = unknown. The row predates this column, or an older installed
--           daemon reported it. The original length is gone, so nothing can
--           recover whether it was complete.
--   FALSE = the daemon measured the output and stored all of it.
--   TRUE  = the remainder was never uploaded and cannot be recovered.
--
-- Backfilling NULL to FALSE would assert completeness the data cannot support,
-- which is the specific claim the truncation indicator exists to stop making.
ALTER TABLE task_message ADD COLUMN IF NOT EXISTS output_truncated BOOLEAN;

```

## server/go/migrations/458_agent_task_cancellation_actor.up.sql

```sql
-- Additive cancellation provenance for run history. Nullable columns keep
-- historical rows and mixed-version deployments compatible: old cancellations
-- continue to render the existing plain status.
ALTER TABLE agent_task_queue
    ADD COLUMN cancelled_by_type TEXT,
    ADD COLUMN cancelled_by_id UUID,
    ADD COLUMN cancelled_by_name TEXT;

```

## server/go/migrations/459_chat_message_assistant_task_index.up.sql

```sql
-- Index the task-owned assistant lookup used by quick-action generation.
--
-- GetChatMessageByTaskAssistant and SetChatMessageQuickActionsByTask both find
-- the newest assistant row for one task. The existing task_id index is partial
-- on role = 'user', so neither query can use it and both scan chat_message.
--
-- Single-statement migration: CREATE INDEX CONCURRENTLY cannot run inside a
-- transaction or a multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_message_assistant_task
    ON chat_message (task_id, created_at DESC)
    WHERE role = 'assistant';

```

## server/go/migrations/460_agent_task_queue_autopilot_run_created_at_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- GetAutopilotTaskByRun recovers run_only dispatches whose task INSERT committed
-- before autopilot_run.task_id was linked. Without an autopilot_run_id-leading
-- index, finding the earliest task scans and sorts the entire task queue.
-- Automatic retries inherit the same autopilot_run_id, so this index must remain
-- non-unique. The partial predicate avoids indexing ordinary non-Autopilot tasks.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_autopilot_run_created_at
    ON agent_task_queue (autopilot_run_id, created_at)
    WHERE autopilot_run_id IS NOT NULL;

```

## server/go/migrations/461_channel_trigger_snapshot.up.sql

```sql
-- Freeze each trigger's reply target AND its channel-native sender per context
-- generation, so an outbound reply answers exactly the message that asked and
-- @-mentions exactly the account that sent it (#8234).
--
-- Two earlier shapes were wrong, both for the same underlying reason — the
-- identity was read from something coarser than "this trigger":
--
--   * Resolving the open_id at send time from the task's initiator_user_id.
--     channel_user_binding is unique on (installation_id, channel_user_id) and
--     NOT on (installation_id, workpal_user_id), so a member who binds a
--     second Feishu account on one installation has two rows and the reverse
--     lookup could name either.
--
--   * Recording the trigger on channel_chat_session_binding, which holds one
--     row per chat_session and therefore only ever remembers the LATEST
--     trigger. A run debounced in revision 1 has its delivery row created
--     after a /clear opened revision 2, so it would freeze the newer
--     generation's message and sender: reply to A's question, quote and
--     mention B.
--
-- channel_chat_context_generation is keyed (chat_session_id, revision) and
-- already snapshots initiator_user_id for exactly this reason — see
-- SetChannelChatContextInitiator, whose comment names the same hazard for
-- crash recovery. The trigger belongs beside it. channel_task_delivery then
-- freezes the generation's values per task.
--
-- The thread belongs here too, with the message and sender. It is tempting to
-- call the thread "route" and read it from the binding, but that only holds
-- for thread-ISOLATED sessions. Slack DMs are the counterexample the repo
-- already encodes: slackSessionRouting keeps one binding per DM channel while
-- carrying a per-message reply thread, so the binding's cursor names whichever
-- thread spoke last. Reading it there would hand a debounced revision-1 run
-- the thread of a later revision — the same cross-generation hazard this
-- snapshot exists to close for the message and sender.
--
-- The binding keeps its own last_message_id / last_thread_id for the
-- history-boundary bookkeeping (history_start_message_id,
-- history_end_message_id). That cursor is deliberately NOT interchangeable
-- with the trigger here: it advances for channel commands (/issue) too,
-- whereas the trigger is written only for messages that are actually agent
-- input.
--
-- No index: every read here goes through an existing key (chat_session_id +
-- revision, or task_id).
ALTER TABLE channel_chat_context_generation
    ADD COLUMN IF NOT EXISTS last_message_id TEXT,
    ADD COLUMN IF NOT EXISTS last_thread_id  TEXT,
    ADD COLUMN IF NOT EXISTS last_sender_id  TEXT;

ALTER TABLE channel_task_delivery
    ADD COLUMN IF NOT EXISTS channel_sender_id TEXT;

-- Existing generations intentionally keep a NULL trigger — no backfill, in
-- line with 451_agent_task_comment_thread's "pre-migration rows drain without
-- rewriting historical data".
--
-- Nothing needs one. The trigger is recorded during AppendUserMessage, which
-- commits before the debounced flush that enqueues the task and creates its
-- delivery row, so the first inbound turn after deploy already supplies a
-- correct value for that generation. Only a generation enqueued with NO
-- post-deploy append can read NULL here — the recovered-run path — and that is
-- exactly the case a backfill cannot serve: the binding cursor it would copy
-- from has already advanced past that generation, so seeding would supply a
-- confidently wrong message and sender rather than no answer.
--
-- What a NULL trigger costs depends on where the answer is going, and
-- CreateChannelTaskDeliveryFromSession is written around that:
--
--   * Ordinary chat, p2p, Slack DM — a chat-level send lands in the very
--     conversation the session belongs to. No quote, no mention, right place.
--
--   * Thread-isolated session (Lark topic, Slack channel thread, Telegram
--     forum topic) — the thread is recovered from the binding, which for these
--     bindings is a stable property of the session rather than a cursor. The
--     answer still reaches its thread.
--
--   * Lark topic specifically — Lark can only enter a topic by replying to a
--     message inside it, so a recovered thread is not enough. The Patcher
--     declines to send rather than posting into the parent group; see
--     topicSendWithoutTrigger.

```

## server/go/migrations/462_delete_reference_only_pr_links.up.sql

```sql
-- Retire reference-only PR links. A link row was written for an issue key that
-- appeared ONLY as a bare mention in a PR body (no closing keyword, nothing in
-- the title or branch), then flagged reference_only and filtered out of every
-- read path: the issue PR list, the close-intent aggregate, and the review
-- dedup head SHA. The row therefore had no reader at all, and once the PR went
-- terminal the link upsert preserved the flag, so adding "Closes KEY" to a
-- merged PR's body could never surface the PR on its issue — the one recovery
-- action a user can take was the one that could not work.
--
-- The webhook now links only a key it read from the PR title, the branch name,
-- or a body closing keyword, which is exactly the set that was visible before.
-- Deleting the hidden rows keeps the two in step: left behind, they would
-- become visible — and block auto-advance while in flight — as soon as the read
-- filters went away.
--
-- Old API instances still running during a rolling deploy can insert a few more
-- such rows; the column stays in place for now, and the follow-up migration
-- that drops it re-runs this delete as a mop-up.
DELETE FROM issue_pull_request WHERE reference_only;
DELETE FROM issue_vcs_pull_request WHERE reference_only;

```

## server/go/migrations/463_drop_issue_description_bigm_index.up.sql

```sql
-- SearchIssues evaluates description matches while scanning a workspace's
-- issue candidates, so this global description GIN is no longer read.
DROP INDEX CONCURRENTLY IF EXISTS idx_issue_description_bigm;

```

## server/go/migrations/464_drop_issue_description_trgm_index.up.sql

```sql
-- Retire the portable fallback for the same workspace-first SearchIssues path.
-- Keep this separate because concurrent index DDL must be the only statement.
DROP INDEX CONCURRENTLY IF EXISTS idx_issue_description_trgm;

```

## server/go/migrations/465_agent_task_queue_chat_with_session_index.up.sql

```sql
-- Bound AdvanceCancelledChatSessionPointer's newer-task guard to one chat
-- instead of scanning the global task population (MUL-7247).
--
-- This is a net-new index on the hottest write table and may contain most
-- historical chat tasks: session_id is normally present once a chat task has
-- started. The partial predicate still excludes every issue task and chat tasks
-- that never established a provider session.
-- Measure the production build set before rollout with:
-- SELECT count(*) FROM agent_task_queue
-- WHERE chat_session_id IS NOT NULL AND session_id IS NOT NULL;
--
-- Keep this separate from idx_agent_task_queue_chat_pending_v3. That index's
-- status predicate is what keeps workspace-wide pending-task queries selective,
-- while this guard must see both in-flight and terminal tasks with sessions.
--
-- This file must stay single-statement: CREATE INDEX CONCURRENTLY cannot run in
-- a transaction or a multi-command string.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_chat_with_session_created_at
ON agent_task_queue (chat_session_id, created_at DESC)
WHERE chat_session_id IS NOT NULL
  AND session_id IS NOT NULL;

```

## server/go/migrations/466_activity_log_member_assignee_frequency_index.up.sql

```sql
-- Renumbered from 458 to avoid the cancellation-provenance migration.
-- IF NOT EXISTS preserves an index already created under the old version;
-- the runner records this version without rewriting the historical ledger.
-- CountAssigneeChangesByActor filters by workspace and member actor, then
-- groups on the assignment target stored in details. Keep the expressions in
-- key order so PostgreSQL can aggregate the matching history directly from
-- this targeted partial index instead of scanning the full activity log.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_log_member_assignee_frequency
    ON activity_log (
        workspace_id,
        actor_id,
        (details->>'to_type'),
        (details->>'to_id')
    )
    WHERE actor_type = 'member'
      AND action = 'assignee_changed'
      AND details->>'to_type' IS NOT NULL
      AND details->>'to_id' IS NOT NULL;

```

## server/go/migrations/467_autopilot_trigger_creator_from_autopilot.up.sql

```sql
-- MUL-7267: give legacy autopilot triggers the dispatch principal migration 449
-- could not recover.
--
-- Migration 449 backfilled autopilot_trigger.created_by from published_by and
-- left the row NULL when there was no published_by either: every trigger created
-- before migration 189 that nobody substantively edited since. A schedule/webhook
-- dispatch acts as created_by and fails closed without one (MUL-6951), so since
-- that upgrade each such trigger has produced only skipped runs — the webhook
-- delivery still reads "dispatched" and the schedule still advances, but nothing
-- executes (#8284).
--
-- This fills those rows from the AUTOPILOT's creator, reversing 449's "leave them
-- empty" choice. The value is a best-effort INFERENCE frozen here, not a record of
-- who created the trigger: before migration 189 an autopilot and its triggers were
-- normally created together, in one dialog, by one member, so for most rows it is
-- the historical creator — but a trigger another member added later through the
-- edit dialog gets the autopilot's creator instead.
--
-- This IS a widening, accepted as the same compatibility tradeoff 449 made. The
-- member chosen is the one automatic dispatch was ADMITTED as before MUL-6951
-- (canCreatorInvokeAgent), so admission decides as it did before that upgrade.
-- Execution does not: a pre-MUL-6951 automatic run carried no originator, only
-- narrowly-scoped borrow paths, whereas a run of a filled trigger acts as the
-- autopilot's creator with that member's own rights, and every run delegated from
-- it inherits that principal. The alternative, NULL, has no in-product recovery
-- that keeps the trigger: an edit re-stamps published_by only, so the user must
-- delete and re-create it, which also changes a webhook's URL for every external
-- sender.
--
-- Only rows without a member principal are touched. An existing member is never
-- rewritten, so an edit still cannot move who a trigger acts as. The autopilot
-- creator must be a member of the autopilot's workspace now; a departed creator is
-- not written in to regain rights if they are re-invited later, and such rows keep
-- failing closed. Dispatch still re-validates membership and invoke access on
-- every run.
--
-- Rollback cannot take this back: from the next schedule or webhook fire the
-- trigger runs as the filled member, and neither an application rollback nor the
-- down migration clears the value.
--
-- autopilot_trigger holds one row per configured trigger (bounded by autopilot
-- count), so this runs as a single statement, like 449. Re-running it is a no-op.
UPDATE autopilot_trigger t
SET created_by_type = 'member',
    created_by_id = a.created_by_id
FROM autopilot a
WHERE a.id = t.autopilot_id
  AND (t.created_by_id IS NULL OR t.created_by_type IS DISTINCT FROM 'member')
  AND a.created_by_type = 'member'
  AND a.created_by_id IS NOT NULL
  AND EXISTS (
      SELECT 1
      FROM member m
      WHERE m.user_id = a.created_by_id
        AND m.workspace_id = a.workspace_id
  );

-- 449's comments describe created_by as the creator, written once at creation.
-- That now holds only for triggers created since MUL-6951, and the text is
-- generated into pkg/db/generated/models.go, so correct it here.
COMMENT ON COLUMN autopilot_trigger.created_by_type IS
    'Actor type of created_by_id: member | agent. Only ''member'' yields a run principal. NULL only for a legacy trigger that neither backfill (migrations 449, 467) could fill.';

COMMENT ON COLUMN autopilot_trigger.created_by_id IS
    'The member a schedule/webhook run fires AS: dispatch admission, the task''s originator/accountable, and every delegated run all resolve to this one human (MUL-6951). For a trigger created since MUL-6951 it is the creator, written at creation. For a legacy trigger it is a best-effort principal inferred once by backfill and frozen (the last publisher, migration 449, else the autopilot''s creator, migration 467), not proof of who created it. Ordinary edits never rewrite it, so editing the trigger cannot re-authorize its runs as the editor. NULL means no principal and the dispatch fails closed. No FK; workspace membership is re-validated on every dispatch.';

```

## server/go/migrations/468_drop_reference_only_column.up.sql

```sql
-- Drop reference_only, the contract half of the pair MUL-7072 started. Since that
-- release a bare body mention of an issue key writes no link row at all, and no
-- query reads or writes this column. It may only run once every instance of the
-- previous release is gone: an older instance still names the column in its link
-- INSERT and would fail on every link write against this schema.
--
-- The DELETE repeats as a mop-up. Migration 462 cleared the historical hidden
-- rows, but instances still serving during that rollout could write a few more,
-- and once the column is gone such a row becomes indistinguishable from a real
-- link — visible in the issue's PR list and, while its PR is in flight, blocking
-- the issue from auto-advancing.
DELETE FROM issue_pull_request WHERE reference_only;
DELETE FROM issue_vcs_pull_request WHERE reference_only;

ALTER TABLE issue_pull_request DROP COLUMN reference_only;
ALTER TABLE issue_vcs_pull_request DROP COLUMN reference_only;

```

## server/go/migrations/469_issue_status_lifecycle_categories.up.sql

```sql
-- Forward-only category consolidation (MUL-7240). A single DO statement keeps
-- constraints and the small status catalog rewrite atomic under this runner.
-- Issue keys/IDs, archived rows, and issue associations are never rewritten.
-- No issue updates/events are emitted: migration must not start agent runs.
DO $migration$
BEGIN
    ALTER TABLE issue_status DROP CONSTRAINT IF EXISTS issue_status_system_is_canonical;
    ALTER TABLE issue_status DROP CONSTRAINT IF EXISTS issue_status_category_check;

    UPDATE issue_status SET category = CASE category
        WHEN 'backlog' THEN 'unstarted'
        WHEN 'todo' THEN 'unstarted'
        WHEN 'in_progress' THEN 'started'
        WHEN 'in_review' THEN 'started'
        WHEN 'blocked' THEN 'started'
        WHEN 'cancelled' THEN 'closed'
        ELSE category
    END
    WHERE category NOT IN ('unstarted', 'started', 'done', 'closed');

    ALTER TABLE issue_status ADD CONSTRAINT issue_status_category_check
        CHECK (category IN ('unstarted', 'started', 'done', 'closed'));
    ALTER TABLE issue_status ADD CONSTRAINT issue_status_system_is_canonical CHECK (
        NOT is_system OR (key, category) IN (
            ('backlog', 'unstarted'), ('todo', 'unstarted'),
            ('in_progress', 'started'), ('in_review', 'started'), ('blocked', 'started'),
            ('done', 'done'), ('cancelled', 'closed')
        )
    );

    CREATE OR REPLACE FUNCTION issue_effective_status(p_workspace_id UUID, p_status TEXT)
    RETURNS TEXT LANGUAGE sql STABLE PARALLEL SAFE AS $function$
        SELECT CASE
            WHEN p_status IN ('backlog', 'todo', 'in_progress', 'in_review', 'done', 'blocked', 'cancelled') THEN p_status
            ELSE COALESCE((SELECT CASE s.category
                WHEN 'done' THEN 'done'
                WHEN 'closed' THEN 'cancelled'
                ELSE p_status END
                FROM issue_status s WHERE s.workspace_id = p_workspace_id AND s.key = p_status), p_status)
        END
    $function$;
END
$migration$;

```

## server/go/migrations/470_issue_status_icon.up.sql

```sql
-- Presentation only. Empty keeps the category default for existing statuses
-- and clients that do not send an icon. No issue or workflow data is rewritten.
ALTER TABLE issue_status ADD COLUMN IF NOT EXISTS icon text NOT NULL DEFAULT '';

```

## server/go/migrations/471_comment_deleted_at.up.sql

```sql
-- Deleting a comment removes only that comment (#8296). A comment that still
-- has replies keeps its row as a tombstone — content cleared, deleted_at set —
-- so every reply stays attached to its direct parent. A comment without
-- replies is removed outright, and a tombstone is removed once its last reply
-- is gone. The application owns that lifecycle; nothing here relies on the
-- legacy parent_id cascade.
--
-- Nullable with no default, so this is a metadata-only change. IF NOT EXISTS
-- lets development databases that applied this migration under its original
-- unreleased 468 stem advance to the corrected ledger version safely.
ALTER TABLE comment ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL;

```

## server/go/migrations/472_agent_task_queue_chat_session_index.up.sql

```sql
-- Every chat_session delete runs the legacy agent_task_queue foreign-key
-- action with only chat_session_id in its predicate. The existing chat indexes
-- add status, session_id, or retired_session_id predicates and cannot serve
-- that lookup, so each deleted session scans the global task table.
--
-- Keep created_at in the key so this broader index also covers migration 465's
-- cancelled-chat pointer lookup. Migration 473 drops that narrower index only
-- after this concurrent build has completed successfully.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_chat_session
ON agent_task_queue (chat_session_id, created_at DESC)
WHERE chat_session_id IS NOT NULL;

```

## server/go/migrations/473_drop_agent_task_queue_chat_with_session_index.up.sql

```sql
-- Migration 472's index has the same ordered keys and a broader predicate, so
-- the cancelled-chat pointer lookup remains covered without carrying both
-- indexes on the hottest write table.
DROP INDEX CONCURRENTLY IF EXISTS idx_agent_task_queue_chat_with_session_created_at;

```

## server/go/migrations/474_dingtalk_bot_identity_workspace_index.up.sql

```sql
-- Workspace teardown keeps the denormalized workspace predicate so it also
-- removes orphaned identities whose installation row is already gone.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dingtalk_bot_identity_workspace
ON dingtalk_bot_identity (workspace_id);

```

## server/go/migrations/475_issue_status_key_not_reserved.up.sql

```sql
-- Intentionally empty (MUL-7400).
--
-- This file reserved the `triage` status key: a CHECK that no issue_status row
-- may be keyed `triage`, so the server could read `status = 'triage'` as "in
-- Triage". Migration 483 moved Triage onto issue.triage_state, after which
-- nothing reads that key as Triage and the name protects nothing. The Go side
-- of the reservation is gone with it.
--
-- Emptied rather than reverted with a new migration because 475-477 have never
-- run outside development and CI: releases deploy from tags, and the newest tag
-- predates them. Migration 490 drops the constraint wherever a database did run
-- this file from main.

```

## server/go/migrations/476_reserve_triage_status_key.up.sql

```sql
-- Intentionally empty (MUL-7400).
--
-- This file was step 2 of reserving the `triage` status key: it renamed any
-- pre-existing custom `triage` status to `triage_2`, moved that workspace's
-- issues onto the new key, rewrote saved views, and validated 475's CHECK. All
-- of it existed to protect an equivalence — `status = 'triage'` means "in
-- Triage" — that migration 483 retired by giving Triage a column of its own.
--
-- What is left without that equivalence is a rewrite of live customer data
-- (status keys, issue rows, saved views) in the deploy path, buying nothing.
-- The key reservation is gone from the server as well, so a workspace that
-- already owns a custom `triage` status simply keeps it.

```

## server/go/migrations/477_issue_effective_status_triage.up.sql

```sql
-- Intentionally empty (MUL-7400).
--
-- This file added `triage` to the fast path of issue_effective_status(), the
-- SQL mirror of issuestatus.Effective, on the premise that no catalog row could
-- ever hold the key. That premise was migrations 475-476, which this change
-- also empties. Without the fast-path entry the key falls through to the
-- catalog lookup and, finding no row, returns unchanged — the same answer.
--
-- Migration 478 owns the current definition of the function.

```

## server/go/migrations/478_issue_status_category_expand.up.sql

```sql
-- MUL-7365: expand only. Pending 469 is skipped by cmd/migrate; applied 469
-- remains historical fact. No catalog rows (including archived rows) change.
-- The runner sends this file as one implicit transaction. Bound lock acquisition
-- and execution; NOT VALID avoids a table scan while holding the DDL lock.
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';

CREATE OR REPLACE FUNCTION issue_status_category(p_category TEXT)
RETURNS TEXT LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $function$
    SELECT CASE p_category
        WHEN 'backlog' THEN 'unstarted' WHEN 'todo' THEN 'unstarted'
        WHEN 'in_progress' THEN 'started' WHEN 'in_review' THEN 'started'
        WHEN 'blocked' THEN 'started' WHEN 'cancelled' THEN 'closed'
        ELSE p_category END
$function$;

ALTER TABLE issue_status
    DROP CONSTRAINT IF EXISTS issue_status_category_check,
    DROP CONSTRAINT IF EXISTS issue_status_system_is_canonical,
    ADD CONSTRAINT issue_status_category_check CHECK (
        category IN ('backlog', 'todo', 'in_progress', 'in_review', 'blocked',
                     'done', 'cancelled', 'unstarted', 'started', 'closed')
    ) NOT VALID,
    ADD CONSTRAINT issue_status_system_is_canonical CHECK (
        NOT is_system OR (key, category) IN (
            ('backlog', 'backlog'), ('backlog', 'unstarted'),
            ('todo', 'todo'), ('todo', 'unstarted'),
            ('in_progress', 'in_progress'), ('in_progress', 'started'),
            ('in_review', 'in_review'), ('in_review', 'started'),
            ('blocked', 'blocked'), ('blocked', 'started'),
            ('done', 'done'), ('cancelled', 'cancelled'), ('cancelled', 'closed')
        )
    ) NOT VALID;

CREATE OR REPLACE FUNCTION issue_effective_status(p_workspace_id UUID, p_status TEXT)
RETURNS TEXT LANGUAGE sql STABLE PARALLEL SAFE AS $function$
    SELECT CASE
        WHEN p_status IN ('backlog', 'todo', 'in_progress', 'in_review', 'done', 'blocked', 'cancelled') THEN p_status
        ELSE COALESCE((SELECT CASE s.category
            WHEN 'done' THEN 'done'
            WHEN 'cancelled' THEN 'cancelled'
            WHEN 'closed' THEN 'cancelled'
            ELSE p_status END
            FROM issue_status s WHERE s.workspace_id = p_workspace_id AND s.key = p_status), p_status)
    END
$function$;

```

## server/go/migrations/479_instance_telemetry_state.up.sql

```sql
-- One deployment identity and at most one durable pending snapshot. No user,
-- workspace or runtime identifier is referenced from this table.
CREATE TABLE instance_telemetry_state (
    singleton             BOOLEAN NOT NULL DEFAULT true CHECK (singleton),
    instance_id           UUID NOT NULL DEFAULT gen_random_uuid(),
    last_successful_day   DATE,
    pending_day           DATE,
    pending_body          BYTEA,
    next_attempt_at       TIMESTAMPTZ,
    attempt_count         INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (pending_day IS NULL AND pending_body IS NULL AND next_attempt_at IS NULL AND attempt_count = 0)
        OR
        (pending_day IS NOT NULL AND pending_body IS NOT NULL AND next_attempt_at IS NOT NULL)
    )
);

INSERT INTO instance_telemetry_state (singleton) VALUES (true);

```

## server/go/migrations/480_instance_telemetry_state_singleton_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS instance_telemetry_state_singleton_uidx
    ON instance_telemetry_state (singleton);

```

## server/go/migrations/481_instance_telemetry_state_primary_key.up.sql

```sql
ALTER TABLE instance_telemetry_state
    ADD CONSTRAINT instance_telemetry_state_pkey PRIMARY KEY USING INDEX instance_telemetry_state_singleton_uidx;

```

## server/go/migrations/482_agent_task_queue_telemetry_started_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_telemetry_started
    ON agent_task_queue (started_at)
    WHERE started_at IS NOT NULL;

```

## server/go/migrations/483_issue_triage_state.up.sql

```sql
-- Move Triage off `issue.status` and onto the issue's own attribute
-- (MUL-7213, design MUL-7189).
--
-- `status` answers "how far along is this work"; Triage answers "is this work
-- at all". Holding the second question in the first field makes every reader of
-- `status` re-answer it, which is where the scattered `<> 'triage'` checks came
-- from. A column of its own asks it once.
--
-- NULL is an ordinary issue and is the whole meaning of "not in Triage", so no
-- backfill and no default: adding a nullable column with no default is a
-- catalog-only change in PostgreSQL 11+, so this does not rewrite the table.
--
-- `pending` is the only state Triage can be in today. The outcomes a triager
-- records (declined, merged into another issue) are their own sub-issue and
-- extend this CHECK when they land; keeping the constraint narrow now is what
-- makes that a deliberate change rather than a silent typo.
--
-- The CHECK is added NOT VALID: a validated CHECK scans every existing issue
-- while holding the ALTER's ACCESS EXCLUSIVE lock, which stops all issue reads
-- and writes for the length of that scan even though the new column needs no
-- backfill. NOT VALID enforces the constraint on every write from this point
-- on and skips the scan; migration 489 validates the rows already on disk under
-- SHARE UPDATE EXCLUSIVE, which readers and writers run straight through.
--
-- The runner sends this file as one implicit transaction. Bound lock
-- acquisition and execution so this catalog-only change fails fast and retries
-- on the next run rather than parking a pending ACCESS EXCLUSIVE lock in front
-- of every issue query.
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';

ALTER TABLE issue
    ADD COLUMN triage_state TEXT,
    ADD CONSTRAINT issue_triage_state_known CHECK (triage_state IS NULL OR triage_state IN ('pending')) NOT VALID;

```

## server/go/migrations/484_issue_triage_state_index.up.sql

```sql
-- The Triage queue reads exactly the rows this index holds, and every other
-- issue surface reads none of them. A partial index keeps it the size of the
-- queue rather than the size of the issue table.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_triage_state
ON issue (workspace_id, created_at ASC)
WHERE triage_state IS NOT NULL;

```

## server/go/migrations/485_maintenance_job.up.sql

```sql
-- Operator-driven maintenance only; creating this table starts no work.
CREATE TABLE IF NOT EXISTS maintenance_job (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    job_type TEXT NOT NULL,
    job_version INTEGER NOT NULL CHECK (job_version > 0),
    scope_key TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ready', 'paused', 'completed', 'cancelled')),
    revision BIGINT NOT NULL DEFAULT 0,
    dry_run BOOLEAN NOT NULL DEFAULT true,
    options JSONB NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    checkpoint JSONB NOT NULL DEFAULT '{}',
    progress JSONB NOT NULL DEFAULT '{}',
    result JSONB NOT NULL DEFAULT '{}',
    last_error TEXT NOT NULL DEFAULT '',
    next_allowed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    CHECK (jsonb_typeof(options) = 'object' AND jsonb_typeof(parameters) = 'object'
        AND jsonb_typeof(checkpoint) = 'object' AND jsonb_typeof(progress) = 'object'
        AND jsonb_typeof(result) = 'object')
);

```

## server/go/migrations/486_maintenance_job_id_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_maintenance_job_id ON maintenance_job (id);

```

## server/go/migrations/487_maintenance_job_idempotency_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_maintenance_job_idempotency ON maintenance_job (idempotency_key);

```

## server/go/migrations/488_maintenance_job_active_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_maintenance_job_active ON maintenance_job (job_type, scope_key) WHERE status IN ('ready', 'paused');

```

## server/go/migrations/489_issue_triage_state_validate.up.sql

```sql
-- Validate the CHECK migration 483 added NOT VALID.
--
-- Split out so the scan runs under SHARE UPDATE EXCLUSIVE — readers and writers
-- continue — instead of inheriting migration 483's ACCESS EXCLUSIVE lock, which
-- would stop the issue table for the length of the scan. Migration 483 added
-- the column with no default and no backfill, so every row this scan reads is
-- NULL: the work is marking the constraint trusted, not repairing data.
ALTER TABLE issue VALIDATE CONSTRAINT issue_triage_state_known;

```

## server/go/migrations/490_drop_triage_status_key_reservation.up.sql

```sql
-- Drop the `triage` status-key reservation wherever it was applied (MUL-7400).
--
-- Migrations 475-477 are emptied by this change, which is enough for every
-- database that has not run them yet — production included, since releases
-- deploy from tags and no tag carries them. A database that did migrate off
-- main keeps the CHECK, and would refuse a custom status keyed `triage` that
-- the server now accepts: the reservation is gone from issuestatus, so the
-- write would fail on the constraint instead of being answered.
--
-- IF EXISTS makes this a no-op on the first group and the repair on the second.
-- Dropping a constraint is catalog-only; the timeouts bound the lock the same
-- way migration 478 does, in the same implicit transaction the runner gives
-- this file.
--
-- 476's rename is not reversed: a workspace whose custom `triage` became
-- `triage_2` keeps it, because the replacement is an ordinary custom key its
-- admin may already have seen, and handing `triage` back would rewrite live
-- data a second time to undo the first.
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';

ALTER TABLE issue_status DROP CONSTRAINT IF EXISTS issue_status_key_not_reserved;

```

## server/go/migrations/491_issue_status_category_backfill.up.sql

```sql
-- Self-host upgrades converge automatically. SaaS must finish the bounded
-- maintenance job BEFORE deploying this revision, so this updates zero rows.
-- Keep data work separate from the ACCESS EXCLUSIVE constraint transaction.
UPDATE issue_status
SET category = issue_status_category(category)
WHERE category IN ('backlog', 'todo', 'in_progress', 'in_review', 'blocked', 'cancelled');

```

## server/go/migrations/492_issue_status_category_contract.up.sql

```sql
-- All writers must already emit lifecycle categories. NOT VALID avoids a
-- table scan while holding ACCESS EXCLUSIVE; 493 validates after commit.
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';

ALTER TABLE issue_status
    DROP CONSTRAINT IF EXISTS issue_status_category_check,
    DROP CONSTRAINT IF EXISTS issue_status_system_is_canonical,
    ADD CONSTRAINT issue_status_category_check CHECK (
        category IN ('unstarted', 'started', 'done', 'closed')
    ) NOT VALID,
    ADD CONSTRAINT issue_status_system_is_canonical CHECK (
        NOT is_system OR (key, category) IN (
            ('backlog', 'unstarted'), ('todo', 'unstarted'),
            ('in_progress', 'started'), ('in_review', 'started'),
            ('blocked', 'started'), ('done', 'done'), ('cancelled', 'closed')
        )
    ) NOT VALID;

```

## server/go/migrations/493_issue_status_category_validate.up.sql

```sql
-- A separate transaction scans under SHARE UPDATE EXCLUSIVE, allowing normal
-- reads/writes. No ACCESS EXCLUSIVE operation belongs in this file.
SET LOCAL lock_timeout = '2s';
ALTER TABLE issue_status
    VALIDATE CONSTRAINT issue_status_category_check,
    VALIDATE CONSTRAINT issue_status_system_is_canonical;

```

## server/go/migrations/494_issue_status_category_read_contract.up.sql

```sql
-- Storage is now validated. Keep built-in identity (including cancelled) and
-- resolve archived custom terminal statuses; triage remains a custom key.
CREATE OR REPLACE FUNCTION issue_effective_status(p_workspace_id UUID, p_status TEXT)
RETURNS TEXT
LANGUAGE sql STABLE PARALLEL SAFE
AS $function$
    SELECT CASE
        WHEN p_status IN ('backlog', 'todo', 'in_progress', 'in_review', 'done', 'blocked', 'cancelled')
            THEN p_status
        ELSE COALESCE((
            SELECT CASE s.category
                WHEN 'done' THEN 'done'
                WHEN 'closed' THEN 'cancelled'
                ELSE p_status
            END
            FROM issue_status s
            WHERE s.workspace_id = p_workspace_id AND s.key = p_status
        ), p_status)
    END
$function$;
-- Retain issue_status_category for historical migration replay and maintenance
-- audit tooling; application queries no longer normalize stored categories.

```

## server/go/migrations/495_issue_to_label_label_id_index.up.sql

```sql
-- ListLabels counts assignments once per issue label, and label deletion also
-- looks up rows by label_id. The primary key starts with issue_id, so it cannot
-- selectively serve either path as the junction table grows.
CREATE INDEX CONCURRENTLY IF NOT EXISTS issue_to_label_label_idx
    ON issue_to_label (label_id);

```

## server/go/migrations/496_chat_session_agent_id_index.up.sql

```sql
-- Runtime teardown finds and locks every chat session owned by a system agent
-- before deleting that agent. The same column backs the ON DELETE CASCADE
-- foreign key, so an unindexed lookup extends the teardown transaction and its
-- chat-session lock window with a full-table scan.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_session_agent_id
    ON chat_session (agent_id);

```

## server/go/migrations/497_agent_task_queue_delegated_failure_evidence_index.up.sql

```sql
-- Delegated-failure recovery repeatedly counts attempts for one failed task and
-- selects its newest attempt by created_at/id. Keep this partial because
-- agent_task_queue is write-heavy and only recovery tasks need the lookup.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_delegated_failure_evidence
    ON agent_task_queue (trigger_evidence_ref_id, created_at DESC, id DESC)
    WHERE trigger_evidence_kind = 'delegated_failure';

```

## server/go/migrations/498_chat_session_runtime_id_index.up.sql

```sql
-- Deleting a runtime clears chat-session resume pointers through the runtime_id
-- foreign key. Equality to the deleted non-NULL runtime implies this predicate,
-- so the partial index serves the FK action without indexing unbound sessions.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_session_runtime_id
    ON chat_session (runtime_id)
    WHERE runtime_id IS NOT NULL;

```

## server/go/migrations/499_agent_task_issue_snapshot.up.sql

```sql
-- issue_snapshot records the comparable state of the issue AS THIS CLAIM SAW IT,
-- so the next run this agent takes on the same issue can be told whether the
-- issue itself moved instead of re-reading it unconditionally.
--
-- Written once per claim, next to the comment-delivery receipt and under the
-- same CAS. It is read back by a LATER claim only off the row whose provider
-- session that claim actually resumes — the row GetLastTaskSession returns, or
-- the operator-chosen source of a manual rerun — and only when that row
-- actually started. "The run that started last" is a different row whenever a
-- poisoned session is skipped or an older run is rerun, and comparing against
-- it would report "unchanged" to an agent whose resumed memory predates the
-- change.
--
-- One writer per row is why the column lives here and not on `issue`: a
-- content_revision on the issue row would have to be bumped by every one of the
-- dozen-odd writers that touch any compared field, and the first one missed
-- would report "unchanged" forever with no symptom. A snapshot taken at claim
-- time has exactly one writer, whatever the compared set happens to be.
--
-- Shape is {"v":1,...}: version plus sha256 of title and description. Hashes,
-- not bodies — this column is a comparison key, never a second copy of the
-- issue text. `v` gates the comparison: a snapshot written by a different
-- version is treated as unknown, which degrades to the pre-existing "read the
-- issue" instruction.
--
-- The set answers only "must the agent re-read the issue BODY?", so only title
-- and description qualify — they are the task itself and nothing but a read
-- delivers them. Status, assignee and priority are out: the claim ships the
-- current status and assignee on every response, so no comparison is needed to
-- learn them, and priority does not change the agent's work. Labels, parent,
-- due date, stage, project and metadata are out too.
--
-- Rows written by an earlier shape of this column also carry a "status" key;
-- it is ignored. Removing a field from the set is backward compatible, so it
-- does not bump `v` — only adding one, or changing how a value is derived,
-- makes an old row unable to answer the current question.
--
-- Nullable, and NULL is the normal state for every row written before this
-- migration. A reader must treat NULL as "not compared", never as "unchanged".
-- No index: the column is never a lookup key. It is only ever projected off a
-- row some other query already located by (agent_id, issue_id), alongside the
-- started_at that dates the comment delta.
ALTER TABLE agent_task_queue ADD COLUMN IF NOT EXISTS issue_snapshot JSONB;

```

## server/go/migrations/500_task_message_call_id.up.sql

```sql
ALTER TABLE task_message ADD COLUMN call_id TEXT;

```

## server/go/migrations/501_runtime_profile_runtime_type.up.sql

```sql
ALTER TABLE runtime_profile ADD COLUMN runtime_type text NOT NULL DEFAULT '';

```

## server/go/migrations/502_channel_reply_delivery.up.sql

```sql
-- One row per user turn: who is currently delivering that turn's reply into a
-- chat channel, what the provider has already accepted, and how far it got.
--
-- The streamed placeholder, the final answer and the failure notice are three
-- code paths, and across replicas three processes — the daemon's transcript
-- report and its completion callback are independent HTTP requests that land
-- wherever the load balancer sends them, and the event bus is in-process. A
-- process that cannot see the placeholder posts its own copy of the same
-- answer (GH #8049, #7750). This row is where they agree.
--
-- Keyed by turn, not by task: an automatic retry runs under a new task id and
-- must finish the reply its previous attempt started rather than answer beside
-- it. turn_id is the root of the agent_task_queue retry_of_task_id chain, so
-- the relationship is the real lineage and never a guess about which pending
-- reply looked closest.
CREATE TABLE IF NOT EXISTS channel_reply_delivery (
    turn_id UUID NOT NULL,
    -- The attempt holding the turn most recently; diagnostics, never identity.
    -- How far down the retry chain that attempt sits is added by migration 506,
    -- which is also where a database created by this file gets it.
    task_id UUID NOT NULL,
    binding_id UUID NOT NULL,
    installation_id UUID NOT NULL,
    channel_type TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    -- streaming: the placeholder is the live reply and may still be edited.
    -- terminal:  the final answer has taken over; no placeholder may reopen.
    -- settled:   delivery is over; nothing may send or edit for this turn.
    phase TEXT NOT NULL CHECK (phase IN ('streaming', 'terminal', 'settled')),
    -- The state of the one send that may be outstanding, placeholder or chunk.
    -- none:      nothing is out.
    -- in_flight: a send is out; the provider may already have accepted it.
    -- known:     accepted, and message_id identifies the editable message.
    -- unknown:   accepted or not — the response was lost. Telegram's
    --            sendMessage has no caller-supplied idempotency key, so
    --            re-sending here cannot be deduplicated by the provider.
    --            Delivery stops and this row keeps the evidence.
    send_state TEXT NOT NULL CHECK (send_state IN ('none', 'in_flight', 'known', 'unknown')),
    -- The message later paths edit. Independent of chunks_sent: a placeholder
    -- exists long before any part of the final answer has been delivered, and
    -- conflating the two silently truncates the reply.
    message_id TEXT NOT NULL DEFAULT '',
    -- Parts of the FINAL answer already in the chat. Never set by the
    -- placeholder.
    chunks_sent INTEGER NOT NULL DEFAULT 0 CHECK (chunks_sent >= 0),
    -- The delivery lease. Exactly one process may act on a turn at a time;
    -- every state write proves it still holds the token. A lease that expires
    -- is a process that died mid-delivery — the successor may take the turn
    -- over, but an outstanding send stays unknown rather than being retried.
    owner_token UUID,
    owner_expires_at TIMESTAMPTZ,
    settled_reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/503_channel_reply_delivery_turn_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_channel_reply_delivery_turn ON channel_reply_delivery (turn_id);

```

## server/go/migrations/504_channel_reply_delivery_installation_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_channel_reply_delivery_installation ON channel_reply_delivery (installation_id);

```

## server/go/migrations/505_channel_reply_delivery_binding_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_channel_reply_delivery_binding ON channel_reply_delivery (binding_id);

```

## server/go/migrations/506_channel_reply_delivery_attempt_depth.up.sql

```sql
-- How far down the retry chain the attempt holding a turn sits. Depth only
-- ever moves forward: once a retry has taken a turn over, a late frame from an
-- earlier attempt must not take it back and rewrite what the user is reading.
--
-- Its own migration rather than an edit to 500: a database that already
-- recorded 500 would never see a change made there, and every query touching
-- the column would fail on exactly the deployments this feature has already
-- been installed on. Written so a database created by 500 and one upgraded
-- through this file end up with the same schema.
ALTER TABLE channel_reply_delivery
    ADD COLUMN IF NOT EXISTS attempt_depth INTEGER NOT NULL DEFAULT 0;

ALTER TABLE channel_reply_delivery
    DROP CONSTRAINT IF EXISTS channel_reply_delivery_attempt_depth_check;

ALTER TABLE channel_reply_delivery
    ADD CONSTRAINT channel_reply_delivery_attempt_depth_check CHECK (attempt_depth >= 0);

```

## server/go/migrations/509_issue_wakeup.up.sql

```sql
CREATE TABLE issue_wakeup (
 id uuid NOT NULL, workspace_id uuid NOT NULL, issue_id uuid NOT NULL,
 agent_id uuid NOT NULL, created_by uuid NOT NULL, source_task_id uuid,
 parent_comment_id uuid, instruction text NOT NULL,
 kind text NOT NULL CHECK (kind IN ('event','at','every','cron')),
 mode text NOT NULL CHECK (mode IN ('once','continuous')),
 event_types text[] NOT NULL DEFAULT '{}', filter_agent_id uuid, filter_task_id uuid,
 interval_seconds bigint, cron_expression text, timezone text NOT NULL DEFAULT 'UTC',
 next_fire_at timestamptz, enabled boolean NOT NULL DEFAULT true,
 disabled_at timestamptz, revision bigint NOT NULL DEFAULT 1,
 last_task_id uuid, last_error text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE issue_wakeup_receipt (
 id uuid NOT NULL, wakeup_id uuid NOT NULL, revision bigint NOT NULL,
 event_key text NOT NULL, event_type text NOT NULL, payload jsonb NOT NULL,
 task_id uuid, processed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

```

## server/go/migrations/510_wakeup_id.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY issue_wakeup_id_idx ON issue_wakeup(id);

```

## server/go/migrations/511_wakeup_issue.up.sql

```sql
CREATE INDEX CONCURRENTLY issue_wakeup_issue_idx ON issue_wakeup(issue_id,workspace_id);

```

## server/go/migrations/512_wakeup_due.up.sql

```sql
CREATE INDEX CONCURRENTLY issue_wakeup_due_idx ON issue_wakeup(next_fire_at) WHERE enabled;

```

## server/go/migrations/513_wakeup_receipt_id.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY issue_wakeup_receipt_id_idx ON issue_wakeup_receipt(id);

```

## server/go/migrations/514_wakeup_receipt_key.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY issue_wakeup_receipt_key_idx ON issue_wakeup_receipt(wakeup_id,revision,event_key);

```

## server/go/migrations/515_wakeup_receipt_pending.up.sql

```sql
CREATE INDEX CONCURRENTLY issue_wakeup_receipt_pending_idx ON issue_wakeup_receipt(wakeup_id,created_at) WHERE processed_at IS NULL;

```

## server/go/migrations/516_wakeup_pending_scope.up.sql

```sql
-- Preserve the existing unique index and retry ON CONFLICT contract during a
-- rolling deployment. For wakeup runs the scheduling scope is the configuration
-- id; trigger_comment_id still holds the real result-delivery thread.
CREATE OR REPLACE FUNCTION set_agent_task_comment_thread() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 NEW.comment_thread_id := COALESCE(NULLIF(NEW.context->>'wakeup_id','')::uuid,comment_thread_root_id(NEW.trigger_comment_id));
 RETURN NEW;
END
$$;

```

## server/go/migrations/518_wakeup_event_capture.up.sql

```sql
-- Capture only matching wakeup inputs, in the source write's transaction.
-- This is not an event history: receipts are consumed by the normal task queue.
CREATE FUNCTION capture_issue_wakeup(p_issue uuid, p_type text, p_key text, p_agent uuid, p_task uuid, p_payload jsonb)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE w issue_wakeup;
BEGIN
 FOR w IN SELECT * FROM issue_wakeup WHERE issue_id=p_issue AND enabled AND kind='event'
   AND p_type=ANY(event_types) AND (filter_agent_id IS NULL OR filter_agent_id=p_agent)
   AND (filter_task_id IS NULL OR filter_task_id=p_task)
   AND NOT EXISTS (SELECT 1 FROM agent_task_queue t WHERE t.id=p_task AND t.context->>'wakeup_id'=issue_wakeup.id::text)
   ORDER BY id
 LOOP
  INSERT INTO issue_wakeup_receipt(id,wakeup_id,revision,event_key,event_type,payload)
   VALUES(gen_random_uuid(),w.id,w.revision,p_key,p_type,p_payload) ON CONFLICT DO NOTHING;
 END LOOP;
END $$;
CREATE FUNCTION capture_task_wakeup() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.issue_id IS NOT NULL AND NEW.status IS DISTINCT FROM OLD.status AND NEW.status IN ('completed','failed','cancelled') THEN
  PERFORM capture_issue_wakeup(NEW.issue_id,'task.'||NEW.status,NEW.id::text||':'||NEW.status,NEW.agent_id,NEW.id,
   jsonb_build_object('task_id',NEW.id,'agent_id',NEW.agent_id,'status',NEW.status));
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER capture_task_wakeup AFTER UPDATE OF status ON agent_task_queue FOR EACH ROW EXECUTE FUNCTION capture_task_wakeup();
CREATE FUNCTION capture_comment_wakeup() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM capture_issue_wakeup(NEW.issue_id,'comment.created',NEW.id::text,
  CASE WHEN NEW.author_type='agent' THEN NEW.author_id ELSE NULL END,NEW.source_task_id,
  jsonb_build_object('comment_id',NEW.id,'author_type',NEW.author_type,'author_id',NEW.author_id,'source_task_id',NEW.source_task_id));
 RETURN NEW;
END $$;
CREATE TRIGGER capture_comment_wakeup AFTER INSERT ON comment FOR EACH ROW EXECUTE FUNCTION capture_comment_wakeup();
CREATE FUNCTION stop_issue_wakeups() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE closing boolean;
BEGIN
 closing := TG_OP='DELETE';
 IF NOT closing THEN
  closing := NEW.status IN ('done','cancelled') OR EXISTS
   (SELECT 1 FROM issue_status s WHERE s.workspace_id=NEW.workspace_id AND s.key=NEW.status AND s.category IN ('done','closed'));
 END IF;
 IF closing THEN
  UPDATE issue_wakeup SET enabled=false,disabled_at=clock_timestamp(),updated_at=clock_timestamp()
   WHERE issue_id=OLD.id AND disabled_at IS NULL;
  UPDATE agent_task_queue SET status='cancelled',completed_at=now(),error='Issue closed; wakeup disabled'
   WHERE issue_id=OLD.id AND context->>'wakeup_id' IS NOT NULL AND status IN ('queued','deferred') AND started_at IS NULL;
 ELSE
  IF NEW.status IS DISTINCT FROM OLD.status THEN
   PERFORM capture_issue_wakeup(NEW.id,'issue.status_changed',NEW.id::text||':'||NEW.revision::text,
    (SELECT agent_id FROM agent_task_queue WHERE id=NULLIF(current_setting('workpal.source_task_id',true),'')::uuid),
    NULLIF(current_setting('workpal.source_task_id',true),'')::uuid,
    jsonb_build_object('issue_id',NEW.id,'status',NEW.status));
  END IF;
 END IF;
 RETURN COALESCE(NEW,OLD);
END $$;
CREATE TRIGGER stop_issue_wakeups AFTER UPDATE OF status ON issue FOR EACH ROW EXECUTE FUNCTION stop_issue_wakeups();

```

## server/go/migrations/519_wakeup_event_issue.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_wakeup_event_issue ON issue_wakeup(issue_id) WHERE enabled AND kind='event';

```

## server/go/migrations/520_collaboration_wakeup_events.up.sql

```sql
-- Extend transactional capture without an event archive or a second run lifecycle.
-- Payloads contain references and changed field names, never comment bodies,
-- attachment URLs, or arbitrary metadata values.
CREATE OR REPLACE FUNCTION capture_issue_wakeup(p_issue uuid, p_type text, p_key text, p_agent uuid, p_task uuid, p_payload jsonb)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE w issue_wakeup; owner_workspace uuid; evidence jsonb;
BEGIN
 IF NOT EXISTS (SELECT 1 FROM issue_wakeup WHERE issue_id=p_issue AND enabled AND kind='event' AND p_type=ANY(event_types)) THEN RETURN; END IF;
 IF p_agent IS NULL AND current_setting('workpal.actor_type',true)='agent' THEN
  p_agent := NULLIF(current_setting('workpal.actor_id',true),'')::uuid;
 END IF;
 SELECT i.workspace_id INTO owner_workspace FROM issue i
 WHERE i.id=p_issue AND i.status NOT IN ('done','cancelled') AND NOT EXISTS
 (SELECT 1 FROM issue_status s WHERE s.workspace_id=i.workspace_id AND s.key=i.status AND s.category IN ('done','closed'));
 IF owner_workspace IS NULL THEN RETURN; END IF;
 evidence := jsonb_build_object('event_id',p_key,'event_type',p_type,'version',1,
  'occurred_at',clock_timestamp(),'workspace_id',owner_workspace,'issue_id',p_issue,
  'source_task_id',p_task,'agent_id',p_agent,
  'actor_type',COALESCE(NULLIF(current_setting('workpal.actor_type',true),''),CASE WHEN p_agent IS NOT NULL THEN 'agent' ELSE 'system' END),
  'actor_id',COALESCE(NULLIF(current_setting('workpal.actor_id',true),''),p_agent::text)) || p_payload;
 FOR w IN SELECT * FROM issue_wakeup WHERE issue_id=p_issue AND workspace_id=owner_workspace AND enabled AND kind='event'
   AND p_type=ANY(event_types) AND (filter_agent_id IS NULL OR filter_agent_id=p_agent)
   AND (filter_task_id IS NULL OR filter_task_id=p_task)
   AND NOT EXISTS (SELECT 1 FROM agent_task_queue t WHERE t.id=p_task AND t.context->>'wakeup_id'=issue_wakeup.id::text)
   ORDER BY id
 LOOP
  INSERT INTO issue_wakeup_receipt(id,wakeup_id,revision,event_key,event_type,payload)
   VALUES(gen_random_uuid(),w.id,w.revision,p_key,p_type,evidence) ON CONFLICT DO NOTHING;
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION capture_task_wakeup() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE event_type text; event_key text; old_status text;
BEGIN
 IF NEW.issue_id IS NULL THEN RETURN NEW; END IF;
 IF TG_OP='UPDATE' THEN
  IF NEW.status IS NOT DISTINCT FROM OLD.status THEN RETURN NEW; END IF;
  old_status := OLD.status;
 END IF;
 event_type := CASE NEW.status WHEN 'running' THEN 'task.started' ELSE 'task.'||NEW.status END;
 IF NEW.status NOT IN ('queued','dispatched','running','deferred','waiting_local_directory','completed','failed','cancelled') THEN RETURN NEW; END IF;
 -- Terminal keys also match the locked registration check. Repeated queue /
 -- defer transitions are separate facts and must not share a lifetime key.
 event_key := CASE WHEN NEW.status IN ('completed','failed','cancelled') THEN NEW.id::text||':'||NEW.status ELSE gen_random_uuid()::text END;
 PERFORM capture_issue_wakeup(NEW.issue_id,event_type,event_key,NEW.agent_id,NEW.id,
  jsonb_build_object('task_id',NEW.id,'agent_id',NEW.agent_id,'status',NEW.status,'previous_status',old_status,
   'retry_of_task_id',NEW.retry_of_task_id,'rerun_of_task_id',NEW.rerun_of_task_id));
 RETURN NEW;
END $$;
DROP TRIGGER capture_task_wakeup ON agent_task_queue;
CREATE TRIGGER capture_task_wakeup AFTER INSERT OR UPDATE OF status ON agent_task_queue FOR EACH ROW EXECUTE FUNCTION capture_task_wakeup();

CREATE OR REPLACE FUNCTION capture_comment_wakeup() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c comment; event_type text; source_id uuid; source_agent uuid; payload jsonb; root_id uuid;
BEGIN
 c := CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
 IF NOT EXISTS (SELECT 1 FROM issue_wakeup WHERE issue_id=c.issue_id AND enabled AND kind='event') THEN RETURN c; END IF;
 source_id := NULLIF(current_setting('workpal.source_task_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  event_type := 'comment.created';
  source_id := COALESCE(source_id,c.source_task_id);
  source_agent := CASE WHEN c.author_type='agent' THEN c.author_id END;
 ELSIF TG_OP='DELETE' THEN
  -- Pruning an existing tombstone is storage cleanup, not another deletion.
  IF OLD.deleted_at IS NOT NULL THEN RETURN OLD; END IF;
  event_type := 'comment.deleted';
 ELSIF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL THEN
  event_type := 'comment.deleted';
 ELSIF NEW.deleted_at IS NOT NULL THEN RETURN NEW;
 ELSIF OLD.resolved_at IS NULL AND NEW.resolved_at IS NOT NULL THEN event_type := 'comment.resolved';
 ELSIF OLD.resolved_at IS NOT NULL AND NEW.resolved_at IS NULL THEN event_type := 'comment.unresolved';
 ELSIF NEW.content IS DISTINCT FROM OLD.content THEN event_type := 'comment.updated';
 ELSE RETURN NEW;
 END IF;
 IF source_id IS NOT NULL THEN SELECT agent_id INTO source_agent FROM agent_task_queue WHERE id=source_id; END IF;
 -- Keep author and actor distinct: an admin editing an agent's comment is
 -- not an event produced by that agent's original run.
 IF TG_OP<>'INSERT' AND source_id IS NULL THEN
  source_agent := CASE WHEN current_setting('workpal.actor_type',true)='agent' THEN NULLIF(current_setting('workpal.actor_id',true),'')::uuid END;
 END IF;
 root_id := c.id;
 IF c.parent_id IS NOT NULL THEN
  WITH RECURSIVE ancestors AS (
   SELECT id,parent_id,1 AS depth FROM comment WHERE id=c.parent_id AND issue_id=c.issue_id AND workspace_id=c.workspace_id
   UNION ALL SELECT p.id,p.parent_id,a.depth+1 FROM comment p JOIN ancestors a ON p.id=a.parent_id
    WHERE p.issue_id=c.issue_id AND p.workspace_id=c.workspace_id AND a.depth<256
  ) SELECT id INTO root_id FROM ancestors ORDER BY depth DESC LIMIT 1;
 END IF;
 payload := jsonb_build_object('comment_id',c.id,'parent_comment_id',c.parent_id,'thread_id',COALESCE(root_id,c.id),
  'author_type',c.author_type,'author_id',c.author_id);
 IF TG_OP='INSERT' THEN payload := payload || jsonb_build_object('actor_type',c.author_type,'actor_id',c.author_id); END IF;
 PERFORM capture_issue_wakeup(c.issue_id,event_type,gen_random_uuid()::text,source_agent,source_id,payload);
 RETURN c;
END $$;
DROP TRIGGER capture_comment_wakeup ON comment;
CREATE TRIGGER capture_comment_wakeup AFTER INSERT OR UPDATE OR DELETE ON comment FOR EACH ROW EXECUTE FUNCTION capture_comment_wakeup();

-- Closing still wins over every subscription. Capture of non-terminal changes
-- lives in its own trigger so revision-only writes never produce a new input.
CREATE OR REPLACE FUNCTION stop_issue_wakeups() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.status IN ('done','cancelled') OR EXISTS
 (SELECT 1 FROM issue_status s WHERE s.workspace_id=NEW.workspace_id AND s.key=NEW.status AND s.category IN ('done','closed')) THEN
  UPDATE issue_wakeup SET enabled=false,disabled_at=clock_timestamp(),updated_at=clock_timestamp()
   WHERE issue_id=OLD.id AND disabled_at IS NULL;
  UPDATE agent_task_queue SET status='cancelled',completed_at=now(),error='Issue closed; wakeup disabled'
   WHERE issue_id=OLD.id AND context->>'wakeup_id' IS NOT NULL AND status IN ('queued','deferred') AND started_at IS NULL;
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION capture_issue_collaboration_wakeup() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE source_id uuid; source_agent uuid; fields jsonb; field_name text; event_type text;
 before_row jsonb; after_row jsonb; event_key text;
BEGIN
 -- Avoid serializing potentially large issue documents on the ordinary path.
 IF NOT EXISTS (SELECT 1 FROM issue_wakeup WHERE issue_id=NEW.id AND enabled AND kind='event') THEN RETURN NEW; END IF;
 before_row := to_jsonb(OLD); after_row := to_jsonb(NEW); event_key := gen_random_uuid()::text;
 SELECT jsonb_agg(k ORDER BY k) INTO fields FROM unnest(ARRAY[
  'title','description','status','priority','assignee_type','assignee_id','parent_issue_id','project_id',
  'due_date','start_date','stage','properties','metadata','acceptance_criteria','context_refs','triage_state']) k
 WHERE before_row->k IS DISTINCT FROM after_row->k;
 IF fields IS NULL THEN RETURN NEW; END IF;
 source_id := NULLIF(current_setting('workpal.source_task_id',true),'')::uuid;
 SELECT agent_id INTO source_agent FROM agent_task_queue WHERE id=source_id;
 IF source_agent IS NULL AND current_setting('workpal.actor_type',true)='agent' THEN
  source_agent := NULLIF(current_setting('workpal.actor_id',true),'')::uuid;
 END IF;
 PERFORM capture_issue_wakeup(NEW.id,'issue.updated',event_key||':updated',source_agent,source_id,jsonb_build_object('changed_fields',fields));
 FOR field_name,event_type IN SELECT * FROM (VALUES
  ('status','issue.status_changed'),('assignee_id','issue.assignee_changed'),
  ('parent_issue_id','issue.parent_changed'),('project_id','issue.project_changed'),
  ('properties','issue.properties_changed'),('metadata','issue.metadata_changed')) v(f,e)
 LOOP
  IF fields ? field_name OR (field_name='assignee_id' AND fields ? 'assignee_type') THEN
   PERFORM capture_issue_wakeup(NEW.id,event_type,event_key||':'||field_name,source_agent,source_id,
    CASE WHEN field_name IN ('metadata','properties') THEN
     jsonb_build_object('changed_fields',(SELECT jsonb_agg(k ORDER BY k) FROM
      (SELECT jsonb_object_keys(before_row->field_name) k UNION SELECT jsonb_object_keys(after_row->field_name)) keys
      WHERE (before_row->field_name)->k IS DISTINCT FROM (after_row->field_name)->k))
    WHEN field_name='status' THEN jsonb_build_object('previous_status',OLD.status,'status',NEW.status,
     'previous_category',(SELECT category FROM issue_status WHERE workspace_id=OLD.workspace_id AND key=OLD.status),
     'category',(SELECT category FROM issue_status WHERE workspace_id=NEW.workspace_id AND key=NEW.status))
    WHEN field_name='assignee_id' THEN jsonb_build_object('previous_assignee_id',OLD.assignee_id,'assignee_id',NEW.assignee_id,
     'previous_assignee_type',OLD.assignee_type,'assignee_type',NEW.assignee_type)
    ELSE jsonb_build_object('previous_'||field_name,before_row->field_name,field_name,after_row->field_name) END);
  END IF;
 END LOOP;
 RETURN NEW;
END $$;
CREATE TRIGGER capture_issue_collaboration_wakeup AFTER UPDATE ON issue FOR EACH ROW EXECUTE FUNCTION capture_issue_collaboration_wakeup();

CREATE FUNCTION capture_issue_label_wakeup() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE row_data jsonb := CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END; source_id uuid; source_agent uuid;
BEGIN
 source_id := NULLIF(current_setting('workpal.source_task_id',true),'')::uuid;
 SELECT agent_id INTO source_agent FROM agent_task_queue WHERE id=source_id;
 PERFORM capture_issue_wakeup((row_data->>'issue_id')::uuid,'issue.labels_changed',gen_random_uuid()::text,source_agent,source_id,
  jsonb_build_object('label_id',row_data->'label_id','action',CASE WHEN TG_OP='INSERT' THEN 'added' ELSE 'removed' END));
 RETURN COALESCE(NEW,OLD);
END $$;
CREATE TRIGGER capture_issue_label_wakeup AFTER INSERT OR DELETE ON issue_to_label FOR EACH ROW EXECUTE FUNCTION capture_issue_label_wakeup();

CREATE FUNCTION capture_reaction_wakeup() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE row_data jsonb := CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
 owner_issue uuid; source_id uuid; source_agent uuid; target_type text; target_id uuid; payload jsonb;
BEGIN
 IF TG_TABLE_NAME='comment_reaction' THEN
  target_type := 'comment'; target_id := (row_data->>'comment_id')::uuid;
  SELECT issue_id INTO owner_issue FROM comment WHERE id=target_id AND workspace_id=(row_data->>'workspace_id')::uuid;
 ELSE target_type := 'issue'; target_id := (row_data->>'issue_id')::uuid; owner_issue := target_id;
 END IF;
 source_id := NULLIF(current_setting('workpal.source_task_id',true),'')::uuid;
 IF source_id IS NOT NULL THEN SELECT agent_id INTO source_agent FROM agent_task_queue WHERE id=source_id;
 ELSIF TG_OP='INSERT' AND row_data->>'actor_type'='agent' THEN source_agent := (row_data->>'actor_id')::uuid;
 END IF;
 payload := jsonb_build_object('reaction_id',row_data->'id','target_type',target_type,'target_id',target_id,'emoji',row_data->'emoji',
  'reaction_actor_type',row_data->'actor_type','reaction_actor_id',row_data->'actor_id');
 IF TG_OP='INSERT' THEN payload := payload || jsonb_build_object('actor_type',row_data->'actor_type','actor_id',row_data->'actor_id'); END IF;
 PERFORM capture_issue_wakeup(owner_issue,CASE WHEN TG_OP='INSERT' THEN 'reaction.added' ELSE 'reaction.removed' END,
  gen_random_uuid()::text,source_agent,source_id,payload);
 RETURN COALESCE(NEW,OLD);
END $$;
CREATE TRIGGER capture_comment_reaction_wakeup AFTER INSERT OR DELETE ON comment_reaction FOR EACH ROW EXECUTE FUNCTION capture_reaction_wakeup();
CREATE TRIGGER capture_issue_reaction_wakeup AFTER INSERT OR DELETE ON issue_reaction FOR EACH ROW EXECUTE FUNCTION capture_reaction_wakeup();

CREATE FUNCTION capture_attachment_wakeup() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE before_row jsonb; after_row jsonb; row_data jsonb; before_target uuid; after_target uuid;
 target_type text; source_id uuid; source_agent uuid; owner_issue uuid; event_type text;
BEGIN
 IF TG_OP<>'INSERT' THEN before_row:=to_jsonb(OLD); before_target:=COALESCE(OLD.comment_id,OLD.issue_id); END IF;
 IF TG_OP<>'DELETE' THEN after_row:=to_jsonb(NEW); after_target:=COALESCE(NEW.comment_id,NEW.issue_id); END IF;
 IF before_target IS NOT DISTINCT FROM after_target THEN RETURN COALESCE(NEW,OLD); END IF;
 source_id := NULLIF(current_setting('workpal.source_task_id',true),'')::uuid;
 SELECT agent_id INTO source_agent FROM agent_task_queue WHERE id=source_id;
 FOR row_data,event_type IN SELECT * FROM (VALUES (before_row,'attachment.detached'),(after_row,'attachment.attached')) v(r,e)
 LOOP
  -- Source-context snapshots and chat attachments are outside this issue contract.
  IF row_data IS NULL OR row_data->>'source_context_id' IS NOT NULL OR row_data->>'chat_session_id' IS NOT NULL THEN CONTINUE; END IF;
  owner_issue := (row_data->>'issue_id')::uuid;
  target_type := CASE WHEN row_data->>'comment_id' IS NOT NULL THEN 'comment' ELSE 'issue' END;
  IF target_type='comment' THEN
   SELECT issue_id INTO owner_issue FROM comment WHERE id=(row_data->>'comment_id')::uuid AND workspace_id=(row_data->>'workspace_id')::uuid;
  END IF;
  PERFORM capture_issue_wakeup(owner_issue,event_type,gen_random_uuid()::text,source_agent,source_id,
   jsonb_build_object('attachment_id',row_data->'id','target_type',target_type,
    'target_id',COALESCE(row_data->>'comment_id',row_data->>'issue_id')));
 END LOOP;
 RETURN COALESCE(NEW,OLD);
END $$;
CREATE TRIGGER capture_attachment_wakeup AFTER INSERT OR UPDATE OF issue_id,comment_id OR DELETE ON attachment FOR EACH ROW EXECUTE FUNCTION capture_attachment_wakeup();

```

## server/go/migrations/521_wakeup_workspace_summary.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_wakeup_workspace_enabled ON issue_wakeup(workspace_id,issue_id) WHERE enabled;

```

## server/go/migrations/522_wakeup_run_lookup.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS agent_task_wakeup_lookup_idx ON agent_task_queue ((context->>'wakeup_id'),created_at DESC) WHERE context->>'wakeup_id' IS NOT NULL;

```

## server/go/migrations/523_wakeup_registration_source.up.sql

```sql
-- Ignore events emitted by the run that registered this subscription.
-- Extend transactional capture without an event archive or a second run lifecycle.
-- Payloads contain references and changed field names, never comment bodies,
-- attachment URLs, or arbitrary metadata values.
CREATE OR REPLACE FUNCTION capture_issue_wakeup(p_issue uuid, p_type text, p_key text, p_agent uuid, p_task uuid, p_payload jsonb)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE w issue_wakeup; owner_workspace uuid; evidence jsonb;
BEGIN
 IF NOT EXISTS (SELECT 1 FROM issue_wakeup WHERE issue_id=p_issue AND enabled AND kind='event' AND p_type=ANY(event_types)) THEN RETURN; END IF;
 IF p_agent IS NULL AND current_setting('workpal.actor_type',true)='agent' THEN
  p_agent := NULLIF(current_setting('workpal.actor_id',true),'')::uuid;
 END IF;
 SELECT i.workspace_id INTO owner_workspace FROM issue i
 WHERE i.id=p_issue AND i.status NOT IN ('done','cancelled') AND NOT EXISTS
 (SELECT 1 FROM issue_status s WHERE s.workspace_id=i.workspace_id AND s.key=i.status AND s.category IN ('done','closed'));
 IF owner_workspace IS NULL THEN RETURN; END IF;
 evidence := jsonb_build_object('event_id',p_key,'event_type',p_type,'version',1,
  'occurred_at',clock_timestamp(),'workspace_id',owner_workspace,'issue_id',p_issue,
  'source_task_id',p_task,'agent_id',p_agent,
  'actor_type',COALESCE(NULLIF(current_setting('workpal.actor_type',true),''),CASE WHEN p_agent IS NOT NULL THEN 'agent' ELSE 'system' END),
  'actor_id',COALESCE(NULLIF(current_setting('workpal.actor_id',true),''),p_agent::text)) || p_payload;
 FOR w IN SELECT * FROM issue_wakeup WHERE issue_id=p_issue AND workspace_id=owner_workspace AND enabled AND kind='event'
   AND p_type=ANY(event_types) AND (filter_agent_id IS NULL OR filter_agent_id=p_agent)
   AND (filter_task_id IS NULL OR filter_task_id=p_task)
   AND (p_task IS NULL OR source_task_id IS DISTINCT FROM p_task)
   AND NOT EXISTS (SELECT 1 FROM agent_task_queue t WHERE t.id=p_task AND t.context->>'wakeup_id'=issue_wakeup.id::text)
   ORDER BY id
 LOOP
  INSERT INTO issue_wakeup_receipt(id,wakeup_id,revision,event_key,event_type,payload)
   VALUES(gen_random_uuid(),w.id,w.revision,p_key,p_type,evidence) ON CONFLICT DO NOTHING;
 END LOOP;
END $$;

```

## server/go/migrations/524_wakeup_workspace_history.up.sql

```sql
CREATE INDEX CONCURRENTLY issue_wakeup_workspace_history_idx ON issue_wakeup(workspace_id,created_at DESC,id DESC);

```

## server/go/migrations/525_wakeup_active_runs.up.sql

```sql
CREATE INDEX CONCURRENTLY agent_task_wakeup_active_idx ON agent_task_queue ((context->>'wakeup_id'), (status IN ('running','waiting_local_directory','dispatched')) DESC,created_at DESC,id DESC) WHERE context->>'wakeup_id' IS NOT NULL AND status IN ('queued','deferred','dispatched','running','waiting_local_directory');

```

## server/go/migrations/526_wakeup_terminal_runs.up.sql

```sql
CREATE INDEX CONCURRENTLY agent_task_wakeup_terminal_idx ON agent_task_queue ((context->>'wakeup_id'),created_at DESC,id DESC) WHERE context->>'wakeup_id' IS NOT NULL AND status NOT IN ('queued','deferred','dispatched','running','waiting_local_directory');

```

## server/go/migrations/527_wakeup_receipt_expiry.up.sql

```sql
CREATE INDEX CONCURRENTLY issue_wakeup_receipt_expiry_idx ON issue_wakeup_receipt(processed_at,id) WHERE processed_at IS NOT NULL;

```

## server/go/migrations/528_wakeup_receipt_coalescing.up.sql

```sql
-- Existing receipts retain their original evidence and drain normally.
ALTER TABLE issue_wakeup_receipt ADD COLUMN coalesce_key text;

```

## server/go/migrations/529_wakeup_pending_event.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY issue_wakeup_pending_event_idx ON issue_wakeup_receipt(wakeup_id,revision,coalesce_key) WHERE processed_at IS NULL AND coalesce_key IS NOT NULL;

```

## server/go/migrations/530_wakeup_bounded_capture.up.sql

```sql
-- Ignore events emitted by the run that registered this subscription.
-- Extend transactional capture without an event archive or a second run lifecycle.
-- Payloads contain references and changed field names, never comment bodies,
-- attachment URLs, or arbitrary metadata values.
CREATE OR REPLACE FUNCTION capture_issue_wakeup(p_issue uuid, p_type text, p_key text, p_agent uuid, p_task uuid, p_payload jsonb)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE w issue_wakeup; owner_workspace uuid; evidence jsonb; violated_constraint text;
BEGIN
 IF NOT EXISTS (SELECT 1 FROM issue_wakeup WHERE issue_id=p_issue AND enabled AND kind='event' AND p_type=ANY(event_types)) THEN RETURN; END IF;
 IF p_agent IS NULL AND current_setting('workpal.actor_type',true)='agent' THEN
  p_agent := NULLIF(current_setting('workpal.actor_id',true),'')::uuid;
 END IF;
 SELECT i.workspace_id INTO owner_workspace FROM issue i
 WHERE i.id=p_issue AND i.status NOT IN ('done','cancelled') AND NOT EXISTS
 (SELECT 1 FROM issue_status s WHERE s.workspace_id=i.workspace_id AND s.key=i.status AND s.category IN ('done','closed'));
 IF owner_workspace IS NULL THEN RETURN; END IF;
 evidence := jsonb_build_object('event_id',p_key,'event_type',p_type,'version',1,
  'occurred_at',clock_timestamp(),'workspace_id',owner_workspace,'issue_id',p_issue,
  'source_task_id',p_task,'agent_id',p_agent,
  'actor_type',COALESCE(NULLIF(current_setting('workpal.actor_type',true),''),CASE WHEN p_agent IS NOT NULL THEN 'agent' ELSE 'system' END),
  'actor_id',COALESCE(NULLIF(current_setting('workpal.actor_id',true),''),p_agent::text)) || p_payload;
 FOR w IN SELECT * FROM issue_wakeup WHERE issue_id=p_issue AND workspace_id=owner_workspace AND enabled AND kind='event'
   AND p_type=ANY(event_types) AND (filter_agent_id IS NULL OR filter_agent_id=p_agent)
   AND (filter_task_id IS NULL OR filter_task_id=p_task)
   AND (p_task IS NULL OR source_task_id IS DISTINCT FROM p_task)
   AND NOT EXISTS (SELECT 1 FROM agent_task_queue t WHERE t.id=p_task AND t.context->>'wakeup_id'=issue_wakeup.id::text)
   ORDER BY id
 LOOP
  -- One pending notification per event type. Preserve the first key for
  -- duplicate suppression and the latest source reference for state reads.
  BEGIN
   INSERT INTO issue_wakeup_receipt(id,wakeup_id,revision,event_key,event_type,payload,coalesce_key)
    VALUES(gen_random_uuid(),w.id,w.revision,p_key,p_type,
     evidence || jsonb_build_object('coalesced_count',1,'first_occurred_at',evidence->'occurred_at'),p_type)
   ON CONFLICT(wakeup_id,revision,coalesce_key) WHERE processed_at IS NULL AND coalesce_key IS NOT NULL
   -- Rotate the receipt identity on merge. An older dispatcher that read
   -- without FOR UPDATE can only consume its observed version, leaving the
   -- replacement pending instead of silently consuming unseen evidence.
   DO UPDATE SET id=EXCLUDED.id,payload=EXCLUDED.payload || jsonb_build_object(
    'coalesced_count',COALESCE((issue_wakeup_receipt.payload->>'coalesced_count')::bigint,1)+1,
    'first_occurred_at',issue_wakeup_receipt.payload->'first_occurred_at')
   WHERE issue_wakeup_receipt.event_key<>p_key AND issue_wakeup_receipt.payload->>'event_id' IS DISTINCT FROM p_key;
  EXCEPTION WHEN unique_violation THEN
   GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
   -- A retained receipt already handled this exact source fact. This also
   -- fences the locked registration snapshot against terminal-task capture.
   IF violated_constraint <> 'issue_wakeup_receipt_key_idx' THEN RAISE; END IF;
  END;

 END LOOP;
END $$;

-- Serialize only rule activation, not source events or normal dispatch.
-- 32 rules cover all 25 current event types plus time schedules on one issue;
-- 1000/workspace bounds fanout and scheduler load without limiting history.
CREATE FUNCTION guard_issue_wakeup_capacity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT NEW.enabled THEN RETURN NEW; END IF;
 IF TG_OP='UPDATE' AND OLD.enabled AND OLD.issue_id=NEW.issue_id AND OLD.workspace_id=NEW.workspace_id THEN RETURN NEW; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('issue-wakeup-capacity:'||NEW.workspace_id::text,0));
 IF (SELECT count(*) FROM (SELECT 1 FROM issue_wakeup WHERE workspace_id=NEW.workspace_id AND issue_id=NEW.issue_id AND enabled AND id<>NEW.id LIMIT 32) slots)>=32 THEN
  RAISE EXCEPTION 'An issue can have at most 32 enabled wakeups' USING ERRCODE='23514',CONSTRAINT='issue_wakeup_active_limit';
 END IF;
 IF (SELECT count(*) FROM (SELECT 1 FROM issue_wakeup WHERE workspace_id=NEW.workspace_id AND enabled AND id<>NEW.id LIMIT 1000) slots)>=1000 THEN
  RAISE EXCEPTION 'A workspace can have at most 1000 enabled wakeups' USING ERRCODE='23514',CONSTRAINT='issue_wakeup_active_limit';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_issue_wakeup_capacity BEFORE INSERT OR UPDATE OF enabled,issue_id,workspace_id ON issue_wakeup FOR EACH ROW EXECUTE FUNCTION guard_issue_wakeup_capacity();

```

## server/go/migrations/531_wakeup_actor_filter.up.sql

```sql
ALTER TABLE issue_wakeup
 ADD COLUMN filter_actor_type text,
 ADD COLUMN filter_actor_id uuid,
 ADD CONSTRAINT issue_wakeup_actor_filter CHECK (
  (filter_actor_type IS NULL AND filter_actor_id IS NULL) OR
  (filter_actor_type IS NOT NULL AND filter_actor_type IN ('member','agent') AND filter_actor_id IS NOT NULL AND kind='event')
 ) NOT VALID;

```

## server/go/migrations/532_wakeup_actor_capture.up.sql

```sql
-- Ignore events emitted by the run that registered this subscription.
-- Extend transactional capture without an event archive or a second run lifecycle.
-- Payloads contain references and changed field names, never comment bodies,
-- attachment URLs, or arbitrary metadata values.
CREATE OR REPLACE FUNCTION capture_issue_wakeup(p_issue uuid, p_type text, p_key text, p_agent uuid, p_task uuid, p_payload jsonb)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE w issue_wakeup; owner_workspace uuid; evidence jsonb; violated_constraint text;
BEGIN
 IF NOT EXISTS (SELECT 1 FROM issue_wakeup WHERE issue_id=p_issue AND enabled AND kind='event' AND p_type=ANY(event_types)) THEN RETURN; END IF;
 IF p_agent IS NULL AND current_setting('workpal.actor_type',true)='agent' THEN
  p_agent := NULLIF(current_setting('workpal.actor_id',true),'')::uuid;
 END IF;
 SELECT i.workspace_id INTO owner_workspace FROM issue i
 WHERE i.id=p_issue AND i.status NOT IN ('done','cancelled') AND NOT EXISTS
 (SELECT 1 FROM issue_status s WHERE s.workspace_id=i.workspace_id AND s.key=i.status AND s.category IN ('done','closed'));
 IF owner_workspace IS NULL THEN RETURN; END IF;
 evidence := jsonb_build_object('event_id',p_key,'event_type',p_type,'version',1,
  'occurred_at',clock_timestamp(),'workspace_id',owner_workspace,'issue_id',p_issue,
  'source_task_id',p_task,'agent_id',p_agent,
  'actor_type',COALESCE(NULLIF(current_setting('workpal.actor_type',true),''),CASE WHEN p_agent IS NOT NULL THEN 'agent' ELSE 'system' END),
  'actor_id',COALESCE(NULLIF(current_setting('workpal.actor_id',true),''),p_agent::text)) || p_payload;
 FOR w IN SELECT * FROM issue_wakeup WHERE issue_id=p_issue AND workspace_id=owner_workspace AND enabled AND kind='event'
   AND p_type=ANY(event_types)
   AND (filter_actor_type IS NULL OR (filter_actor_type=evidence->>'actor_type' AND filter_actor_id::text=evidence->>'actor_id'))
   AND (filter_agent_id IS NULL OR filter_agent_id=p_agent)
   AND (filter_task_id IS NULL OR filter_task_id=p_task)
   AND (p_task IS NULL OR source_task_id IS DISTINCT FROM p_task)
   AND NOT EXISTS (SELECT 1 FROM agent_task_queue t WHERE t.id=p_task AND t.context->>'wakeup_id'=issue_wakeup.id::text)
   ORDER BY id
 LOOP
  -- One pending notification per event type. Preserve the first key for
  -- duplicate suppression and the latest source reference for state reads.
  BEGIN
   INSERT INTO issue_wakeup_receipt(id,wakeup_id,revision,event_key,event_type,payload,coalesce_key)
    VALUES(gen_random_uuid(),w.id,w.revision,p_key,p_type,
     evidence || jsonb_build_object('coalesced_count',1,'first_occurred_at',evidence->'occurred_at'),p_type)
   ON CONFLICT(wakeup_id,revision,coalesce_key) WHERE processed_at IS NULL AND coalesce_key IS NOT NULL
   -- Rotate the receipt identity on merge. An older dispatcher that read
   -- without FOR UPDATE can only consume its observed version, leaving the
   -- replacement pending instead of silently consuming unseen evidence.
   DO UPDATE SET id=EXCLUDED.id,payload=EXCLUDED.payload || jsonb_build_object(
    'coalesced_count',COALESCE((issue_wakeup_receipt.payload->>'coalesced_count')::bigint,1)+1,
    'first_occurred_at',issue_wakeup_receipt.payload->'first_occurred_at')
   WHERE issue_wakeup_receipt.event_key<>p_key AND issue_wakeup_receipt.payload->>'event_id' IS DISTINCT FROM p_key;
  EXCEPTION WHEN unique_violation THEN
   GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
   -- A retained receipt already handled this exact source fact. This also
   -- fences the locked registration snapshot against terminal-task capture.
   IF violated_constraint <> 'issue_wakeup_receipt_key_idx' THEN RAISE; END IF;
  END;

 END LOOP;
END $$;

```

## server/go/migrations/533_wakeup_close_in_app.up.sql

```sql
-- Closing an issue disables its wakeups and cancels unstarted wakeup runs in
-- the application transaction that writes the status
-- (service.StopClosedIssueWakeups), not through a cross-table trigger.
DROP TRIGGER IF EXISTS stop_issue_wakeups ON issue;
DROP FUNCTION IF EXISTS stop_issue_wakeups();

```

## server/go/migrations/534_drop_comment_agent_delivery.up.sql

```sql
-- Remove the durable delivery receipts for the reverted comment-steering
-- feature. Fresh databases that never applied migrations 507/508 are unchanged;
-- staging databases that exercised the feature converge back to the old schema.
DROP TABLE IF EXISTS comment_agent_delivery;

```

## server/go/migrations/535_github_pr_address_index.up.sql

```sql
-- Match the pull-request address used by snapshot refreshes without making the
-- GitHub App installation, which is an authorization scope, part of identity.
-- Leading with pr_number prevents the head-SHA lookup, which has no PR number,
-- from preferring this index over its selective head_sha index.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_github_pull_request_pr_owner_repo
    ON github_pull_request (pr_number, repo_owner, repo_name);

```

## server/go/migrations/536_issue_duplicate_of.up.sql

```sql
-- Record which issue a cancelled issue duplicates (MUL-7349).
--
-- A duplicate is an ordinary cancelled issue with a pointer to the issue it
-- duplicates; there is no duplicate status. The pointer only lives while the
-- issue is cancelled: a write that leaves an already cancelled issue cancelled
-- keeps it, and every other write drops it. Reopening an issue is therefore how
-- a mark is removed, and cancelling it again does not bring the mark back.
--
-- This is the expand half of the feature: the column ships with the code that
-- maintains it, and nothing writes a pointer yet. A later release adds marking.
-- That order is what makes marking safe to roll back — the release it rolls
-- back to already clears the pointer on reopen and on delete, so no issue is
-- left carrying a mark the product no longer honours.
--
-- No foreign key (repository rule). Deleting the original clears the pointers
-- to it in the same transaction, the way deleting a parent detaches children.
--
-- A nullable column with no default is a catalog-only change, so this does not
-- rewrite the table. Bound lock acquisition so the ALTER fails fast and retries
-- on the next run instead of queueing an ACCESS EXCLUSIVE lock in front of
-- every issue query.
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';

ALTER TABLE issue ADD COLUMN IF NOT EXISTS duplicate_of_issue_id UUID;

```

## server/go/migrations/537_issue_duplicate_of_index.up.sql

```sql
-- Lists an issue's duplicates and finds them when it is deleted. Only
-- duplicates carry the pointer, so a partial index stays the size of that set.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_duplicate_of
ON issue (duplicate_of_issue_id)
WHERE duplicate_of_issue_id IS NOT NULL;

```

## server/go/migrations/538_task_supplement.up.sql

```sql
-- Keep negotiated capability outside agent_task_queue. Older application
-- builds use SELECT * for that hot table, so adding columns would make a
-- server rollback fail while scanning otherwise-valid task rows.
CREATE TABLE task_supplement_capability (
    task_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    issue_id UUID NOT NULL,
    capability TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Durable delivery receipts for explicit, human-authored additions to one
-- exact run. Relationships intentionally have no database foreign keys: task,
-- issue, comment and workspace teardown remain application-owned and never
-- acquire a new cascade/lock tree.
CREATE TABLE task_supplement (
    task_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    issue_id UUID NOT NULL,
    comment_id UUID NOT NULL,
    author_id UUID NOT NULL,
    client_request_id UUID NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'delivering', 'delivered', 'failed')),
    failure_reason TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at TIMESTAMPTZ
);

-- Terminal transition and receipt settlement share the task row update's
-- transaction and lock. This prevents a run from ending between two
-- application statements and leaving a pending receipt that can never move.
CREATE FUNCTION settle_terminal_task_supplements() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status IN ('queued', 'deferred', 'dispatched', 'waiting_local_directory', 'running')
       AND NEW.status IN ('completed', 'failed', 'cancelled') THEN
        UPDATE task_supplement
        SET status = 'failed',
            failure_reason = 'turn_ended',
            updated_at = now()
        WHERE task_id = NEW.id
          AND status IN ('pending', 'delivering');
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_settle_terminal_task_supplements
AFTER UPDATE OF status ON agent_task_queue
FOR EACH ROW EXECUTE FUNCTION settle_terminal_task_supplements();

```

## server/go/migrations/539_task_supplement_request_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS task_supplement_task_request_uidx
    ON task_supplement (task_id, client_request_id);

```

## server/go/migrations/540_task_supplement_capability_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS task_supplement_capability_task_uidx
    ON task_supplement_capability (task_id);

```

## server/go/migrations/541_task_supplement_comment_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS task_supplement_comment_uidx
    ON task_supplement (comment_id);

```

## server/go/migrations/542_task_supplement_primary_key.up.sql

```sql
-- Reuse the concurrently built unique index; do not build another index while
-- holding the table lock. Deploy only after the complete migration batch.
ALTER TABLE task_supplement
    ADD CONSTRAINT task_supplement_pkey PRIMARY KEY USING INDEX task_supplement_comment_uidx;

```

## server/go/migrations/543_task_supplement_teardown_guard.up.sql

```sql
-- Receipt state follows the terminal transition atomically. This does not
-- delete dependents: issue/workspace/comment deletion remains application-owned.
DROP TRIGGER IF EXISTS trg_settle_terminal_task_supplements ON agent_task_queue;
CREATE TRIGGER trg_settle_terminal_task_supplements
AFTER UPDATE OF status ON agent_task_queue
FOR EACH ROW
WHEN (current_setting('workpal.workspace_teardown', true) IS DISTINCT FROM 'on')
EXECUTE FUNCTION settle_terminal_task_supplements();

```

## server/go/migrations/544_task_supplement_application_settlement.up.sql

```sql
-- Task terminal transitions now settle pending supplements explicitly in the
-- application transaction. Remove the cross-table trigger so task completion
-- no longer acquires task_supplement locks through database-side cascade logic.
DROP TRIGGER IF EXISTS trg_settle_terminal_task_supplements ON agent_task_queue;
DROP FUNCTION IF EXISTS settle_terminal_task_supplements();

```

## server/go/migrations/545_pr_auto_complete.up.sql

```sql
-- PR auto-complete (MUL-7429). Two small per-issue records:
--
--   issue_pr_automation: an explicit "do not auto-complete this issue from PR
--   merges" choice. Absent row = follow the workspace setting.
--
--   issue_pull_request_exclusion: a PR a person removed from an issue. The
--   webhook must not re-link it from the title/branch on the next delivery.
--   pull_request_id points at github_pull_request or vcs_pull_request (both use
--   uuid ids).
--
-- No foreign keys: issue and workspace deletion are application-owned and
-- sweep both tables explicitly (DeleteIssue, DeleteWorkspaceData).
CREATE TABLE IF NOT EXISTS issue_pr_automation (
    issue_id               UUID PRIMARY KEY,
    workspace_id           UUID NOT NULL,
    auto_complete_disabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by_type        TEXT,
    updated_by_id          UUID,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS issue_pull_request_exclusion (
    issue_id         UUID NOT NULL,
    pull_request_id  UUID NOT NULL,
    workspace_id     UUID NOT NULL,
    excluded_by_type TEXT,
    excluded_by_id   UUID,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (issue_id, pull_request_id)
);

```

## server/go/migrations/546_issue_pr_automation_workspace_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_pr_automation_workspace
    ON issue_pr_automation (workspace_id);

```

## server/go/migrations/547_issue_pull_request_exclusion_workspace_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_pull_request_exclusion_workspace
    ON issue_pull_request_exclusion (workspace_id);

```

## server/go/migrations/548_task_supplement_comment_task_index.up.sql

```sql
-- One comment can steer several running agents at once, so a delivery receipt
-- is identified by the (comment, run) pair instead of by the comment alone.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS task_supplement_comment_task_uidx
    ON task_supplement (comment_id, task_id);

```

## server/go/migrations/549_task_supplement_comment_task_primary_key.up.sql

```sql
-- Reuse the concurrently built index. Dropping the old constraint also drops
-- its single-column index; lookups by comment_id use the new key's prefix.
-- Daemons claim receipts continuously, so fail fast and retry on the next run
-- rather than queueing their claims behind a pending ACCESS EXCLUSIVE lock.
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';

ALTER TABLE task_supplement
    DROP CONSTRAINT IF EXISTS task_supplement_pkey,
    ADD CONSTRAINT task_supplement_pkey PRIMARY KEY USING INDEX task_supplement_comment_task_uidx;
-- Left behind by a previous rollback (548 down); it would keep one run per comment.
DROP INDEX IF EXISTS task_supplement_comment_uidx;

```

## server/go/migrations/550_comment_suppressed_agents.up.sql

```sql
-- The agents an author chose not to start for this comment, so completion
-- replay honors that choice too instead of waking them once their run ends.
--
-- Nullable with no default, so this is a metadata-only change. The runner
-- sends this file as one implicit transaction: bound lock acquisition and
-- execution so it fails fast and retries on the next run rather than parking a
-- pending ACCESS EXCLUSIVE lock in front of every comment query.
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';

ALTER TABLE comment ADD COLUMN IF NOT EXISTS suppressed_agent_ids UUID[] NULL;

```

## server/go/migrations/551_pr_merge_status.up.sql

```sql
-- PR merge automation target (MUL-7726). The workspace setting
-- settings.pr_merge_status picks what merging every PR linked to an issue does:
-- "none", or the key of the status the issue moves to. Absent means Done.
--
-- Until now a merge completed an issue only when a PR said "Closes MUL-1" in
-- its title or body, and settings.pr_auto_complete_enabled = false turned that
-- off. Pin "none" on existing workspaces whose history says a merge never
-- completed their issues regardless of the text, so the new Done default only
-- reaches workspaces that never linked a PR or only ever merged keyword PRs:
--
--   * pr_auto_complete_enabled = false                         -> none
--   * a linked PR exists, and not every merged link carried a
--     closing keyword (or nothing merged yet)                  -> none
--   * no linked PR, or every merged link carried a keyword     -> left absent
--
-- Pinned workspaces also get pr_auto_complete_enabled = false, the switch
-- desktop clients from before this change still show, so they show it off.
-- Only workspaces without an explicit pr_merge_status are touched, so a replay
-- is harmless. The scan reads link rows once; the write touches only the
-- pinned workspaces.
WITH link_history AS (
    SELECT i.workspace_id,
           bool_or(pr.state = 'merged') AS any_merged,
           bool_and(pr.state <> 'merged' OR ipr.close_intent) AS merged_with_keyword
    FROM issue_pull_request ipr
    JOIN issue i ON i.id = ipr.issue_id
    JOIN github_pull_request pr ON pr.id = ipr.pull_request_id
    GROUP BY i.workspace_id
    UNION ALL
    SELECT i.workspace_id,
           bool_or(pr.state = 'merged') AS any_merged,
           bool_and(pr.state <> 'merged' OR ipr.close_intent) AS merged_with_keyword
    FROM issue_vcs_pull_request ipr
    JOIN issue i ON i.id = ipr.issue_id
    JOIN vcs_pull_request pr ON pr.id = ipr.pull_request_id
    GROUP BY i.workspace_id
),
pinned AS (
    SELECT workspace_id
    FROM link_history
    GROUP BY workspace_id
    HAVING NOT (bool_or(any_merged) AND bool_and(merged_with_keyword))
)
UPDATE workspace AS w
SET settings = (CASE WHEN jsonb_typeof(w.settings) = 'object' THEN w.settings ELSE '{}'::jsonb END)
    || '{"pr_merge_status": "none", "pr_auto_complete_enabled": false}'::jsonb
WHERE NOT (jsonb_typeof(w.settings) = 'object' AND w.settings ? 'pr_merge_status')
  AND (
      (jsonb_typeof(w.settings) = 'object' AND w.settings->>'pr_auto_complete_enabled' = 'false')
      OR w.id IN (SELECT workspace_id FROM pinned)
  );

```

## server/go/migrations/552_agent_task_history_page_index.up.sql

```sql
-- Match ListAgentTasks visibility and keyset order for bounded history reads.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_history_page
ON agent_task_queue (agent_id, created_at DESC, id DESC)
WHERE NOT (escalation_for_task_id IS NOT NULL AND started_at IS NULL
           AND status IN ('deferred', 'cancelled'));

```

## server/go/migrations/553_wakeup_expiry.up.sql

```sql
-- Every wakeup can carry an end: an absolute deadline, or a relative wait that
-- restarts from "now" whenever the rule is (re)enabled. on_timeout decides
-- whether reaching the deadline wakes the target once to handle it or simply
-- ends the rule. timed_out_at records that the deadline, not a trigger or a
-- person, ended the rule. All columns are nullable: existing rules keep their
-- previous open-ended behavior.
ALTER TABLE issue_wakeup
 ADD COLUMN IF NOT EXISTS expires_at timestamptz,
 ADD COLUMN IF NOT EXISTS expiry_seconds bigint,
 ADD COLUMN IF NOT EXISTS on_timeout text CHECK (on_timeout IN ('wake','end')),
 ADD COLUMN IF NOT EXISTS timed_out_at timestamptz;

```

## server/go/migrations/554_wakeup_expiry_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS issue_wakeup_expiry_idx ON issue_wakeup(expires_at) WHERE enabled AND expires_at IS NOT NULL;

```

## server/go/migrations/555_wakeup_system_rule.up.sql

```sql
-- Platform-owned wakeup rules are ordinary issue_wakeup rows. system_rule names
-- the rule ('child_done': wake the issue's assignee when a stage of its
-- sub-issues finishes). Such a row has no fixed agent or creator: it targets
-- the issue's assignee at the moment it fires, so agent_id and created_by stay
-- NULL for it. customized_at records that a person changed the rule on this
-- issue; until then it follows the workspace default. All changes are
-- additive for existing rows.
ALTER TABLE issue_wakeup
 ADD COLUMN IF NOT EXISTS system_rule text CHECK (system_rule IN ('child_done')),
 ADD COLUMN IF NOT EXISTS customized_at timestamptz,
 ALTER COLUMN agent_id DROP NOT NULL,
 ALTER COLUMN created_by DROP NOT NULL;

-- System rules exist once per parent issue and do not use the per-issue or
-- per-workspace capacity people and agents share.
CREATE OR REPLACE FUNCTION guard_issue_wakeup_capacity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT NEW.enabled OR NEW.system_rule IS NOT NULL THEN RETURN NEW; END IF;
 IF TG_OP='UPDATE' AND OLD.enabled AND OLD.issue_id=NEW.issue_id AND OLD.workspace_id=NEW.workspace_id THEN RETURN NEW; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('issue-wakeup-capacity:'||NEW.workspace_id::text,0));
 IF (SELECT count(*) FROM (SELECT 1 FROM issue_wakeup WHERE workspace_id=NEW.workspace_id AND issue_id=NEW.issue_id AND enabled AND system_rule IS NULL AND id<>NEW.id LIMIT 32) slots)>=32 THEN
  RAISE EXCEPTION 'An issue can have at most 32 enabled wakeups' USING ERRCODE='23514',CONSTRAINT='issue_wakeup_active_limit';
 END IF;
 IF (SELECT count(*) FROM (SELECT 1 FROM issue_wakeup WHERE workspace_id=NEW.workspace_id AND enabled AND system_rule IS NULL AND id<>NEW.id LIMIT 1000) slots)>=1000 THEN
  RAISE EXCEPTION 'A workspace can have at most 1000 enabled wakeups' USING ERRCODE='23514',CONSTRAINT='issue_wakeup_active_limit';
 END IF;
 RETURN NEW;
END $$;

```

## server/go/migrations/556_wakeup_system_rule_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS issue_wakeup_system_rule_idx ON issue_wakeup(issue_id,system_rule) WHERE system_rule IS NOT NULL;

```

## server/go/migrations/557_wakeup_conditions.up.sql

```sql
-- Platform-evaluated conditions and runaway protection for issue wakeups.
--
-- condition holds a structured predicate (a field value, sub-issues finishing,
-- a linked pull request, another issue's status). Such a rule stays
-- kind='event'; the scheduler evaluates it and only wakes the target when the
-- predicate becomes true. condition_state remembers the last satisfied
-- fingerprint so a rule fires on the change, not on every evaluation.
--
-- max_fires/fire_count cap repeating rules; paused_reason records why the
-- platform, not a person, stopped a rule (the cap, a detected loop, or a
-- burst of triggers). All columns are nullable or defaulted: existing rules
-- behave as before.
ALTER TABLE issue_wakeup
 ADD COLUMN IF NOT EXISTS condition jsonb,
 ADD COLUMN IF NOT EXISTS condition_state text NOT NULL DEFAULT '',
 ADD COLUMN IF NOT EXISTS max_fires integer CHECK (max_fires BETWEEN 1 AND 1000),
 ADD COLUMN IF NOT EXISTS fire_count integer NOT NULL DEFAULT 0,
 ADD COLUMN IF NOT EXISTS paused_reason text CHECK (paused_reason IN ('max_fires','loop','rate'));

```

## server/go/migrations/558_issue_child_event.up.sql

```sql
-- Changes to a parent's set of sub-issues, recorded in the writing transaction
-- for every writer (HTTP, batch, PR automation, any future path). They drive
-- the parent's child_done system wakeup and sub-issue conditions: the server
-- processes the rows right after commit and a scheduler sweep retries rows
-- that were not processed. No foreign keys; issue and workspace deletion
-- remove these rows in the application deletion graph.
--
-- kind: closed | reopened (a sub-issue entered or left a closed status,
-- built-in or custom), attached | detached (it joined or left the parent),
-- restaged (its stage changed). source_task_id is the agent run that made the
-- change, when an agent made it, so a rule does not wake that run's agent for
-- what it just did.
CREATE TABLE IF NOT EXISTS issue_child_event (
 id uuid NOT NULL DEFAULT gen_random_uuid(),
 workspace_id uuid NOT NULL,
 parent_id uuid NOT NULL,
 child_id uuid NOT NULL,
 kind text NOT NULL CHECK (kind IN ('closed','reopened','attached','detached','restaged')),
 source_task_id uuid,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 claimed_at timestamptz,
 processed_at timestamptz
);

CREATE OR REPLACE FUNCTION record_issue_child_event() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_closed boolean; new_closed boolean; source uuid;
BEGIN
 source := NULLIF(current_setting('workpal.source_task_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  INSERT INTO issue_child_event(workspace_id,parent_id,child_id,kind,source_task_id) VALUES(NEW.workspace_id,NEW.parent_issue_id,NEW.id,'attached',source);
  RETURN NULL;
 END IF;
 IF OLD.parent_issue_id IS DISTINCT FROM NEW.parent_issue_id THEN
  IF OLD.parent_issue_id IS NOT NULL THEN
   INSERT INTO issue_child_event(workspace_id,parent_id,child_id,kind,source_task_id) VALUES(OLD.workspace_id,OLD.parent_issue_id,OLD.id,'detached',source);
  END IF;
  IF NEW.parent_issue_id IS NOT NULL THEN
   INSERT INTO issue_child_event(workspace_id,parent_id,child_id,kind,source_task_id) VALUES(NEW.workspace_id,NEW.parent_issue_id,NEW.id,'attached',source);
  END IF;
  RETURN NULL;
 END IF;
 IF OLD.status IS DISTINCT FROM NEW.status THEN
  new_closed := NEW.status IN ('done','cancelled') OR EXISTS(SELECT 1 FROM issue_status s WHERE s.workspace_id=NEW.workspace_id AND s.key=NEW.status AND s.category IN ('done','closed'));
  old_closed := OLD.status IN ('done','cancelled') OR EXISTS(SELECT 1 FROM issue_status s WHERE s.workspace_id=OLD.workspace_id AND s.key=OLD.status AND s.category IN ('done','closed'));
  IF new_closed AND NOT old_closed THEN
   INSERT INTO issue_child_event(workspace_id,parent_id,child_id,kind,source_task_id) VALUES(NEW.workspace_id,NEW.parent_issue_id,NEW.id,'closed',source);
  ELSIF old_closed AND NOT new_closed THEN
   INSERT INTO issue_child_event(workspace_id,parent_id,child_id,kind,source_task_id) VALUES(NEW.workspace_id,NEW.parent_issue_id,NEW.id,'reopened',source);
  END IF;
 END IF;
 IF OLD.stage IS DISTINCT FROM NEW.stage THEN
  INSERT INTO issue_child_event(workspace_id,parent_id,child_id,kind,source_task_id) VALUES(NEW.workspace_id,NEW.parent_issue_id,NEW.id,'restaged',source);
 END IF;
 RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS issue_child_event_insert ON issue;
CREATE TRIGGER issue_child_event_insert AFTER INSERT ON issue FOR EACH ROW
 WHEN (NEW.parent_issue_id IS NOT NULL)
 EXECUTE FUNCTION record_issue_child_event();

DROP TRIGGER IF EXISTS issue_child_event_update ON issue;
CREATE TRIGGER issue_child_event_update AFTER UPDATE OF status,parent_issue_id,stage ON issue FOR EACH ROW
 WHEN (OLD.parent_issue_id IS DISTINCT FROM NEW.parent_issue_id
  OR (NEW.parent_issue_id IS NOT NULL AND (OLD.status IS DISTINCT FROM NEW.status OR OLD.stage IS DISTINCT FROM NEW.stage)))
 EXECUTE FUNCTION record_issue_child_event();

```

## server/go/migrations/559_issue_child_event_id.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS issue_child_event_id_idx ON issue_child_event(id);

```

## server/go/migrations/560_issue_child_event_pending.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS issue_child_event_pending_idx ON issue_child_event(parent_id,created_at) WHERE processed_at IS NULL;

```

## server/go/migrations/561_search_index_change.up.sql

```sql
-- Local search index change log (MUL-7754).
--
-- Web and Desktop keep a per-workspace copy of issue, comment, and project text
-- for instant search. Clients catch up by asking which entities changed since
-- the database snapshot they last synced to. `updated_at` cannot answer that:
-- issues and comments are hard-deleted (including cascaded comment deletes), and
-- a timestamp is assigned before commit, so a late-committing writer would be
-- skipped. Triggers record one row per entity with the xid of its latest write;
-- readers compare that xid against pg_snapshot values, which is exact under any
-- commit order. This is the same trigger-populated dirty-key shape as migration
-- 077, and it covers every write path (API, CLI, daemon, agents) at once.
--
-- One row per entity keeps the table bounded: later writes overwrite the xid.
-- Rows carry no content; readers join to the live tables, so a missing row (or
-- a tombstoned comment) means "deleted". No foreign keys: workspace deletion
-- sweeps this table explicitly and skips the triggers via the teardown flag.
--
-- The runner sends this file as one implicit transaction. CREATE TRIGGER takes a
-- short SHARE ROW EXCLUSIVE lock on issue/comment/project, so bound the wait and
-- retry on the next start rather than queue writers behind it.
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';

CREATE TABLE IF NOT EXISTS search_index_change (
    entity_type  TEXT        NOT NULL CHECK (entity_type IN ('issue', 'comment', 'project')),
    entity_id    UUID        NOT NULL,
    workspace_id UUID        NOT NULL,
    change_xid   xid8        NOT NULL,
    changed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_type, entity_id)
);

-- Highest xid removed by retention pruning. A client whose snapshot could still
-- be missing a pruned change must rebuild its copy instead of catching up.
CREATE TABLE IF NOT EXISTS search_index_prune_mark (
    singleton          BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    pruned_through_xid xid8    NOT NULL
);

-- Keep this function trivial: it runs inside every issue/comment/project write,
-- so an error here would fail the user's write. All inputs are NOT NULL columns.
CREATE OR REPLACE FUNCTION record_search_index_change()
RETURNS TRIGGER LANGUAGE plpgsql AS $function$
DECLARE
    changed_id UUID;
    changed_workspace_id UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN
        changed_id := OLD.id;
        changed_workspace_id := OLD.workspace_id;
    ELSE
        changed_id := NEW.id;
        changed_workspace_id := NEW.workspace_id;
    END IF;

    INSERT INTO search_index_change (entity_type, entity_id, workspace_id, change_xid, changed_at)
    VALUES (TG_ARGV[0], changed_id, changed_workspace_id, pg_current_xact_id(), now())
    ON CONFLICT (entity_type, entity_id) DO UPDATE
        SET workspace_id = EXCLUDED.workspace_id,
            change_xid = EXCLUDED.change_xid,
            changed_at = EXCLUDED.changed_at;
    RETURN NULL;
END
$function$;

-- Every issue column is part of the indexed search result, so any update counts.
DROP TRIGGER IF EXISTS trg_issue_search_index_change ON issue;
CREATE TRIGGER trg_issue_search_index_change
AFTER INSERT OR UPDATE OR DELETE ON issue
FOR EACH ROW
WHEN (current_setting('workpal.workspace_teardown', true) IS DISTINCT FROM 'on')
EXECUTE FUNCTION record_search_index_change('issue');

-- Comments only contribute their text and placement; resolve/revision bumps do
-- not change what search can match.
DROP TRIGGER IF EXISTS trg_comment_search_index_change ON comment;
CREATE TRIGGER trg_comment_search_index_change
AFTER INSERT OR DELETE ON comment
FOR EACH ROW
WHEN (current_setting('workpal.workspace_teardown', true) IS DISTINCT FROM 'on')
EXECUTE FUNCTION record_search_index_change('comment');

DROP TRIGGER IF EXISTS trg_comment_update_search_index_change ON comment;
CREATE TRIGGER trg_comment_update_search_index_change
AFTER UPDATE OF content, deleted_at, issue_id, created_at ON comment
FOR EACH ROW
WHEN (current_setting('workpal.workspace_teardown', true) IS DISTINCT FROM 'on')
EXECUTE FUNCTION record_search_index_change('comment');

DROP TRIGGER IF EXISTS trg_project_search_index_change ON project;
CREATE TRIGGER trg_project_search_index_change
AFTER INSERT OR UPDATE OR DELETE ON project
FOR EACH ROW
WHEN (current_setting('workpal.workspace_teardown', true) IS DISTINCT FROM 'on')
EXECUTE FUNCTION record_search_index_change('project');

```

## server/go/migrations/562_search_index_change_workspace_index.up.sql

```sql
-- Serves the catch-up read: one workspace, an xid range, ordered by the keyset
-- (change_xid, entity_type, entity_id) the client pages through.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_index_change_workspace_xid
    ON search_index_change (workspace_id, change_xid, entity_type, entity_id);

```

## server/go/migrations/563_search_index_change_changed_at_index.up.sql

```sql
-- Serves retention pruning, which deletes the oldest rows in bounded batches.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_index_change_changed_at
    ON search_index_change (changed_at);

```

## server/go/migrations/564_issue_property_list_types.up.sql

```sql
-- Custom issue property list types: multi_text / multi_url.
--
-- Adds 'multi_text' and 'multi_url' to the type allowlist. Both store an
-- array of free-form strings (text entries or http(s) URLs) in insertion
-- order; validation, dedup, and the entry cap live in the handler, which is
-- also where each element is validated exactly like a single text / url
-- value. This constraint is only the outer guard.
--
-- Like the actor types (341), the values ride the existing properties jsonb
-- bag: the @> containment filter for element-equality, the jsonb_path_ops GIN
-- index, and the client value schema all keep working unchanged.
--
-- NOT VALID + VALIDATE keeps the ACCESS EXCLUSIVE lock instantaneous;
-- existing rows cannot carry the new types, so validation is a formality.
ALTER TABLE issue_property DROP CONSTRAINT IF EXISTS issue_property_type_check;
ALTER TABLE issue_property ADD CONSTRAINT issue_property_type_check
    CHECK (type IN ('text', 'number', 'select', 'multi_select', 'date', 'checkbox', 'url', 'actor', 'multi_actor', 'multi_text', 'multi_url')) NOT VALID;
ALTER TABLE issue_property VALIDATE CONSTRAINT issue_property_type_check;

```

## server/go/migrations/565_channel_typing_cleanup.up.sql

```sql
-- Durable per-input settlement survives an OnSettled callback before Add starts.
ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS channel_typing_settled boolean NOT NULL DEFAULT false;

-- No foreign keys: cleanup anchors must survive session, task and installation
-- deletion. The snapshot contains encrypted installation credentials only.
CREATE TABLE IF NOT EXISTS channel_typing_reaction (
 id uuid NOT NULL,
 workspace_id uuid NOT NULL,
 chat_session_id uuid NOT NULL,
 chat_message_id uuid NOT NULL,
 installation_id uuid NOT NULL,
 channel_message_id text NOT NULL,
 installation_snapshot jsonb NOT NULL,
 reaction_id text NOT NULL DEFAULT '',
 add_finished boolean NOT NULL DEFAULT false,
 cleanup_required boolean NOT NULL DEFAULT false,
 cleaned_at timestamptz,
 retry_after timestamptz NOT NULL DEFAULT now(),
 attempts integer NOT NULL DEFAULT 0,
 created_at timestamptz NOT NULL DEFAULT now()
);

```

## server/go/migrations/566_channel_typing_reaction_id_idx.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS channel_typing_reaction_id_idx ON channel_typing_reaction (id);

```

## server/go/migrations/567_channel_typing_reaction_retry_idx.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS channel_typing_reaction_retry_idx ON channel_typing_reaction (retry_after, chat_session_id) WHERE cleaned_at IS NULL;

```

## server/go/migrations/568_channel_typing_reaction_gc_idx.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS channel_typing_reaction_gc_idx ON channel_typing_reaction (cleaned_at) WHERE cleaned_at IS NOT NULL;

```

## server/go/migrations/569_channel_typing_limits.up.sql

```sql
ALTER TABLE channel_typing_reaction ADD COLUMN IF NOT EXISTS abandoned_at timestamptz;
ALTER TABLE channel_typing_reaction ADD COLUMN IF NOT EXISTS quota_slot integer;

-- Give existing pending rows a bounded share of each workspace's quota.
-- Excess rows become explicit failed outcomes; never retain their credentials.
WITH ranked AS (
 SELECT id, row_number() OVER (PARTITION BY workspace_id ORDER BY created_at DESC, id) AS slot
 FROM channel_typing_reaction WHERE cleaned_at IS NULL AND abandoned_at IS NULL
)
UPDATE channel_typing_reaction r SET
 quota_slot = CASE WHEN ranked.slot <= 1000 THEN ranked.slot::integer END,
 abandoned_at = CASE WHEN ranked.slot > 1000 THEN now() END,
 cleanup_required = cleanup_required OR ranked.slot > 1000,
 installation_snapshot = CASE WHEN ranked.slot > 1000 THEN '{}'::jsonb ELSE installation_snapshot END
FROM ranked WHERE r.id = ranked.id;

UPDATE channel_typing_reaction SET installation_snapshot = '{}'::jsonb
WHERE cleaned_at IS NOT NULL;

```

## server/go/migrations/570_channel_typing_quota_idx.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS channel_typing_reaction_quota_idx ON channel_typing_reaction (workspace_id, quota_slot) WHERE cleaned_at IS NULL AND abandoned_at IS NULL;

```

## server/go/migrations/571_channel_typing_expiry_idx.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS channel_typing_reaction_expiry_idx ON channel_typing_reaction (created_at, id) WHERE cleaned_at IS NULL AND abandoned_at IS NULL;

```

## server/go/migrations/572_channel_typing_abandoned_idx.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS channel_typing_reaction_abandoned_idx ON channel_typing_reaction (abandoned_at) WHERE abandoned_at IS NOT NULL;

```

## server/go/migrations/573_issue_workflow.up.sql

```sql
-- Project workflows (MUL-7420).
--
-- A workflow is a named, workspace-level selection of statuses from the
-- issue_status catalog, in the order a project's board shows them, with an
-- optional handoff on each step: entering the step assigns the issue to the
-- step's handler and starts its run with the step's instructions.
--
-- Statuses stay shared: steps reference issue_status by key, so issue.status
-- keeps holding a catalog key and cross-project filters, sorting and saved
-- views keep working unchanged. Projects opt in through project.workflow_id; a
-- project without one keeps the whole catalog (the implicit Default workflow),
-- so existing workspaces see no behavior change.
--
-- steps is JSONB because the editor saves a workflow as one unit and nothing
-- queries individual steps across workflows. Status keys and handler ids are
-- validated in application code; no foreign keys by project rule.
--
-- id is attached as the primary key in 575 from the index built CONCURRENTLY
-- in 574 (repo convention, see 332-334).
CREATE TABLE IF NOT EXISTS issue_workflow (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 64),
    description TEXT NOT NULL DEFAULT '' CHECK (char_length(description) <= 256),
    initial_status_key TEXT NOT NULL,
    steps JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(steps) = 'array'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/574_issue_workflow_pkey_index.up.sql

```sql
-- Backing index for issue_workflow's primary key, attached in 575.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS issue_workflow_pkey_uidx
    ON issue_workflow (id);

```

## server/go/migrations/575_issue_workflow_primary_key.up.sql

```sql
-- Attach the CONCURRENTLY-built unique index as the table's primary key.
ALTER TABLE issue_workflow
    ADD CONSTRAINT issue_workflow_pkey PRIMARY KEY USING INDEX issue_workflow_pkey_uidx;

```

## server/go/migrations/576_issue_workflow_workspace_name_index.up.sql

```sql
-- Workflow names are unique per workspace, case-insensitively, because the
-- project picker and the CLI address a workflow by name.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_workflow_workspace_name
    ON issue_workflow (workspace_id, lower(name));

```

## server/go/migrations/577_project_workflow_id.up.sql

```sql
-- The workflow a project uses. NULL means the implicit Default workflow (the
-- whole issue_status catalog, no handoffs), which is what every existing
-- project keeps. Nullable with no default, so adding it is metadata-only.
ALTER TABLE project ADD COLUMN IF NOT EXISTS workflow_id UUID;

```

## server/go/migrations/578_agent_task_workflow_step.up.sql

```sql
-- The workflow step a run is working on (MUL-7420): the issue's status when
-- the task was queued, moved along by the run's own status changes. When the
-- issue has left that step — someone else moved it while the run worked — the
-- run's status changes are refused instead of undoing that move.
--
-- Written by the task INSERTs from the issue row, and by the status-change
-- path when the run moves the issue itself; nothing else writes it. NULL on
-- rows written before this migration and on tasks without an issue, and NULL
-- means "not checked", never "matches".
ALTER TABLE agent_task_queue ADD COLUMN IF NOT EXISTS workflow_step TEXT;

```

## server/go/migrations/579_wakeup_skip_handed_to_agent.up.sql

```sql
-- A write that hands an issue to an agent — assigning it, or entering a
-- project workflow step it handles (MUL-7420) — delivers that change to the
-- agent as its own run. Recording the same write for the agent's event wakeups
-- would start a second run for one fact, so the write names the agent in the
-- transaction-local workpal.handed_to_agent and its issue.* events skip that
-- agent's subscriptions. Everyone else's wakeups — including platform rules,
-- which have no agent_id — and every task, comment and reaction event, are
-- captured as before.
CREATE OR REPLACE FUNCTION capture_issue_wakeup(p_issue uuid, p_type text, p_key text, p_agent uuid, p_task uuid, p_payload jsonb)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE w issue_wakeup; owner_workspace uuid; evidence jsonb; violated_constraint text;
BEGIN
 IF NOT EXISTS (SELECT 1 FROM issue_wakeup WHERE issue_id=p_issue AND enabled AND kind='event' AND p_type=ANY(event_types)) THEN RETURN; END IF;
 IF p_agent IS NULL AND current_setting('workpal.actor_type',true)='agent' THEN
  p_agent := NULLIF(current_setting('workpal.actor_id',true),'')::uuid;
 END IF;
 SELECT i.workspace_id INTO owner_workspace FROM issue i
 WHERE i.id=p_issue AND i.status NOT IN ('done','cancelled') AND NOT EXISTS
 (SELECT 1 FROM issue_status s WHERE s.workspace_id=i.workspace_id AND s.key=i.status AND s.category IN ('done','closed'));
 IF owner_workspace IS NULL THEN RETURN; END IF;
 evidence := jsonb_build_object('event_id',p_key,'event_type',p_type,'version',1,
  'occurred_at',clock_timestamp(),'workspace_id',owner_workspace,'issue_id',p_issue,
  'source_task_id',p_task,'agent_id',p_agent,
  'actor_type',COALESCE(NULLIF(current_setting('workpal.actor_type',true),''),CASE WHEN p_agent IS NOT NULL THEN 'agent' ELSE 'system' END),
  'actor_id',COALESCE(NULLIF(current_setting('workpal.actor_id',true),''),p_agent::text)) || p_payload;
 FOR w IN SELECT * FROM issue_wakeup WHERE issue_id=p_issue AND workspace_id=owner_workspace AND enabled AND kind='event'
   AND p_type=ANY(event_types)
   AND (filter_actor_type IS NULL OR (filter_actor_type=evidence->>'actor_type' AND filter_actor_id::text=evidence->>'actor_id'))
   AND (filter_agent_id IS NULL OR filter_agent_id=p_agent)
   AND (filter_task_id IS NULL OR filter_task_id=p_task)
   AND (p_task IS NULL OR source_task_id IS DISTINCT FROM p_task)
   AND NOT EXISTS (SELECT 1 FROM agent_task_queue t WHERE t.id=p_task AND t.context->>'wakeup_id'=issue_wakeup.id::text)
   AND (p_type NOT LIKE 'issue.%' OR agent_id IS NULL OR agent_id IS DISTINCT FROM NULLIF(current_setting('workpal.handed_to_agent',true),'')::uuid)
   ORDER BY id
 LOOP
  -- One pending notification per event type. Preserve the first key for
  -- duplicate suppression and the latest source reference for state reads.
  BEGIN
   INSERT INTO issue_wakeup_receipt(id,wakeup_id,revision,event_key,event_type,payload,coalesce_key)
    VALUES(gen_random_uuid(),w.id,w.revision,p_key,p_type,
     evidence || jsonb_build_object('coalesced_count',1,'first_occurred_at',evidence->'occurred_at'),p_type)
   ON CONFLICT(wakeup_id,revision,coalesce_key) WHERE processed_at IS NULL AND coalesce_key IS NOT NULL
   -- Rotate the receipt identity on merge. An older dispatcher that read
   -- without FOR UPDATE can only consume its observed version, leaving the
   -- replacement pending instead of silently consuming unseen evidence.
   DO UPDATE SET id=EXCLUDED.id,payload=EXCLUDED.payload || jsonb_build_object(
    'coalesced_count',COALESCE((issue_wakeup_receipt.payload->>'coalesced_count')::bigint,1)+1,
    'first_occurred_at',issue_wakeup_receipt.payload->'first_occurred_at')
   WHERE issue_wakeup_receipt.event_key<>p_key AND issue_wakeup_receipt.payload->>'event_id' IS DISTINCT FROM p_key;
  EXCEPTION WHEN unique_violation THEN
   GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
   -- A retained receipt already handled this exact source fact. This also
   -- fences the locked registration snapshot against terminal-task capture.
   IF violated_constraint <> 'issue_wakeup_receipt_key_idx' THEN RAISE; END IF;
  END;

 END LOOP;
END $$;

```

## server/go/migrations/581_issue_workflow_is_default.up.sql

```sql
-- The workspace Default workflow becomes a real, editable row (MUL-7420).
-- Projects without a workflow_id use it. Before the row exists, Default is
-- the built-in statuses plus the custom statuses no other workflow lists;
-- the row is created from that snapshot the first time workflows are read
-- with the feature on, so statuses added for one workflow no longer pile up
-- in Default and in every cross-project board. At most one per workspace
-- (582).
ALTER TABLE issue_workflow ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT false;

```

## server/go/migrations/582_issue_workflow_default_index.up.sql

```sql
-- One Default workflow per workspace (581).
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_workflow_workspace_default
    ON issue_workflow (workspace_id) WHERE is_default;

```

## server/go/migrations/583_runtime_profile_add_muse.up.sql

```sql
-- Add Meta Muse Code as a first-party protocol family. NOT VALID
-- preserves historical-row tolerance while enforcing the expanded whitelist
-- for new rows.
ALTER TABLE runtime_profile DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check;

ALTER TABLE runtime_profile ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'codearts',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'reasonix',
        'dsh',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw',
        'mcode',
        'muse',
        'dim',
        'zeroclaw'
    )) NOT VALID;

```

## server/go/migrations/584_quick_action_optional_target.up.sql

```sql
ALTER TABLE quick_action
    DROP CONSTRAINT IF EXISTS quick_action_assignee_type_check,
    ALTER COLUMN assignee_id DROP NOT NULL,
    ADD CONSTRAINT quick_action_assignee_type_check CHECK (
        (assignee_type = '' AND assignee_id IS NULL) OR
        (assignee_type IN ('agent', 'squad') AND assignee_id IS NOT NULL)
    );

```

## server/go/migrations/585_issue_workflow_owner.up.sql

```sql
-- Workflow owner (MUL-8120). Any member may create a workflow; its owner and
-- workspace owners/admins may edit or delete it. Nullable: the Default
-- workflow belongs to the workspace and has no owner, and code that predates
-- this column keeps inserting rows without one.
ALTER TABLE issue_workflow ADD COLUMN IF NOT EXISTS owner_id UUID;

-- Workflows created before owners were recorded go to the workspace's
-- earliest owner. Workflows are a few rows per workspace, so one statement
-- is enough.
UPDATE issue_workflow wf
SET owner_id = (
    SELECT m.user_id FROM member m
    WHERE m.workspace_id = wf.workspace_id AND m.role = 'owner'
    ORDER BY m.created_at, m.id
    LIMIT 1
)
WHERE wf.owner_id IS NULL
  AND NOT wf.is_default;

```

## server/go/migrations/586_cloud_agent_connection.up.sql

```sql
-- One managed cloud-agent provider connection per workspace and provider.
-- Secrets and the run journal are sealed with WORKPAL_VCS_SECRET_KEY.
CREATE TABLE cloud_agent_connection (
 workspace_id uuid NOT NULL,
 provider text NOT NULL,
 owner_id uuid NOT NULL,
 token_id uuid NOT NULL,
 config_encrypted text NOT NULL,
 journal_encrypted text NOT NULL DEFAULT '',
 enabled boolean NOT NULL DEFAULT true,
 revision bigint NOT NULL DEFAULT 1,
 status text NOT NULL DEFAULT 'starting',
 last_error text NOT NULL DEFAULT '',
 busy_until timestamptz,
 updated_at timestamptz NOT NULL DEFAULT now()
);

```

## server/go/migrations/587_cloud_agent_connection_provider_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY cloud_agent_connection_provider_index ON cloud_agent_connection (workspace_id, provider);

```

## server/go/migrations/588_daemon_token_owner.up.sql

```sql
-- MUL-8154: bind daemon tokens to the runtime owner they were issued for.
-- A daemon_id can be re-registered by another member after its runtimes are
-- deleted; a token bound only to (workspace_id, daemon_id) would then reach
-- the new owner's runtimes. Daemon routes require owner_id to match the
-- runtime's owner for every non-Qoder-managed token.
--
-- No backfill: the issuing owner of a pre-existing token cannot be recovered
-- (the daemon's current owner may be a later re-registrant), so existing
-- non-Qoder tokens stay NULL and are refused. They are short-lived Remote MCP
-- credentials (24h) that are re-issued on the next claim. Qoder-managed
-- tokens are governed by cloud_agent_connection and stay NULL by design.
-- Plain column, no foreign key (repository rule): a token whose owner is
-- deleted simply never matches a runtime owner again.
ALTER TABLE daemon_token ADD COLUMN IF NOT EXISTS owner_id UUID;

```

## server/go/migrations/589_member_delegation_day.up.sql

```sql
-- One row per (member, UTC day) on which that member personally started an
-- agent run: commented, mentioned, assigned, promoted, created an assigned
-- issue, triggered, reran, chatted or quick-created. Written at the moment of
-- the human action, so it keeps every human who acted and the day they acted
-- even when a later comment folds into a queued run and re-attributes it, and
-- it never records runs that only inherit a human (retries, system wakeups,
-- delegation, autopilot). Not written when telemetry is off (DO_NOT_TRACK).
--
-- Feeds the self-host telemetry "delegating member" counts; no other reader.
-- No FK to "user" by design (workspace DB rules); readers join current
-- members. The primary key is built concurrently in 590/591, following
-- client_usage_daily (207-209), so no migration builds an index inline.
CREATE TABLE member_delegation_day (
    user_id       UUID NOT NULL,
    activity_date DATE NOT NULL
);

```

## server/go/migrations/590_member_delegation_day_unique_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS member_delegation_day_user_date_uidx ON member_delegation_day (user_id, activity_date);

```

## server/go/migrations/591_member_delegation_day_primary_key.up.sql

```sql
ALTER TABLE member_delegation_day ADD CONSTRAINT member_delegation_day_pkey PRIMARY KEY USING INDEX member_delegation_day_user_date_uidx;

```

## server/go/migrations/592_runtime_shared_with.up.sql

```sql
-- Explicit workspace user grants keep visibility private for older servers.
ALTER TABLE agent_runtime ADD COLUMN shared_with uuid[] NOT NULL DEFAULT '{}';

```

## server/go/migrations/593_runtime_profile_add_devin.up.sql

```sql
-- Expand the current whitelist without scanning historical rows. Replacing
-- both parts in one ALTER keeps the constraint present atomically.
ALTER TABLE runtime_profile
    DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check,
    ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'codearts',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'reasonix',
        'dsh',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw',
        'mcode',
        'muse',
        'dim',
        'zeroclaw',
        'devin'
    )) NOT VALID;

```

## server/go/migrations/594_agent_task_process_cleanup_index.up.sql

```sql
-- Both cleanup failures and pending cancellation acknowledgements participate
-- in the start guard. Exclude ordinary history while serving the OR predicate
-- and the latest-unsafe-run ordering from one small index.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_process_cleanup
    ON agent_task_queue (agent_id, runtime_id, completed_at DESC, id DESC)
    WHERE failure_reason = 'cleanup_unconfirmed'
       OR (status = 'cancelled' AND result->>'process_cleanup_pending' = 'true');

```

## server/go/migrations/595_issue_view_preference_sidebar.up.sql

```sql
-- The sidebar's starred views become one more per-user preference
-- container: `prefs.order` lists the starred items ("builtin:<key>" /
-- "view:<uuid>") in sidebar order. scope_id is backfilled with the user id,
-- like the my scope. A separate scope keeps older clients, which write the
-- workspace doc wholesale, from ever clobbering it.
ALTER TABLE issue_view_preference DROP CONSTRAINT issue_view_preference_scope_type_check;
ALTER TABLE issue_view_preference ADD CONSTRAINT issue_view_preference_scope_type_check
    CHECK (scope_type IN ('workspace', 'my', 'project', 'sidebar'));

```

## server/go/migrations/596_issue_view_preference_sidebar_projects.up.sql

```sql
-- The sidebar's Projects section settings follow the user across devices:
-- one per-user document holding which projects are listed and in what
-- order, and how expanded rows list their issues. Its own scope, keyed by
-- the user id like the sidebar scope, so the starred-views list (which
-- writes its document wholesale) can never clobber it.
ALTER TABLE issue_view_preference DROP CONSTRAINT issue_view_preference_scope_type_check;
ALTER TABLE issue_view_preference ADD CONSTRAINT issue_view_preference_scope_type_check
    CHECK (scope_type IN ('workspace', 'my', 'project', 'sidebar', 'sidebar_projects'));

```

## server/go/migrations/597_issue_unread.up.sql

```sql
-- An agent result on an issue that a member has not seen yet (MUL-8438). Backs
-- the sidebar's unread dot. A row is written for each subscribed member when an
-- agent run on the issue ends, and removed when the member opens the issue.
-- Rows exist only while unread, so the table stays small and starts empty: no
-- issue lights up for runs that ended before this shipped.
--
-- outcome: completed | failed (from the run), or manual (marked unread by the
-- member). agent_id and task_id name the run, and are null for manual.
--
-- No foreign keys; issue and workspace deletion remove these rows in the
-- application deletion graph. Readers join current members. The primary key is
-- built concurrently in 598/599, following member_delegation_day (589-591).
CREATE TABLE IF NOT EXISTS issue_unread (
    workspace_id UUID NOT NULL,
    user_id      UUID NOT NULL,
    issue_id     UUID NOT NULL,
    outcome      TEXT NOT NULL CHECK (outcome IN ('completed', 'failed', 'manual')),
    agent_id     UUID,
    task_id      UUID,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/598_issue_unread_unique_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS issue_unread_workspace_user_issue_uidx ON issue_unread (workspace_id, user_id, issue_id);

```

## server/go/migrations/599_issue_unread_primary_key.up.sql

```sql
ALTER TABLE issue_unread ADD CONSTRAINT issue_unread_pkey PRIMARY KEY USING INDEX issue_unread_workspace_user_issue_uidx;

```

## server/go/migrations/600_wecom_install_session.up.sql

```sql
-- Scan-code install sessions for the WeCom smart bot.
--
-- The QR install is a multi-minute, multi-request conversation with WeCom:
-- generate a QR, then poll until an admin scans it and the bot's credentials
-- come back. None of that can live in the request that started it, so the
-- session is a row and a background worker drives it.
--
-- Why the encrypted columns: scode is the polling handle and qr_code_url embeds
-- it, so together they are a bearer credential for "finish creating this bot".
-- They are sealed with the same WORKPAL_WECOM_SECRET_KEY that seals the bot
-- secret, which is also why a deployment without that key cannot run the scan
-- flow at all.
--
-- lease_token + lease_expires_at make the poll single-writer across replicas:
-- WeCom rate-limits query_result, and two replicas polling one scode burn that
-- budget twice as fast for no benefit.
--
-- No foreign keys (repo rule): the workspace teardown path deletes these rows
-- explicitly, and installation_id is a plain reference to the row the session
-- produced on success.
CREATE TABLE wecom_install_session (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- request_key_hash is the SHA-256 of the client's idempotency key. Hashed
    -- rather than stored raw so a DB dump does not carry client-chosen strings.
    request_key_hash        TEXT NOT NULL,
    workspace_id            UUID NOT NULL,
    agent_id                UUID NOT NULL,
    initiator_user_id       UUID NOT NULL,
    scode_encrypted         TEXT,
    qr_code_url_encrypted   TEXT,
    status                  TEXT NOT NULL DEFAULT 'creating'
        CHECK (status IN ('creating', 'pending', 'success', 'error')),
    -- poll_after is the earliest next poll. WeCom requires a minimum interval
    -- between query_result calls, so the schedule lives on the row instead of
    -- in a worker's memory, where a restart would lose it.
    poll_after              TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at              TIMESTAMPTZ,
    lease_token             TEXT,
    lease_expires_at        TIMESTAMPTZ,
    installation_id         UUID,
    -- error_reason is a stable machine code the frontend switches on;
    -- error_message is operator-facing detail and is never shown as-is.
    error_reason            TEXT,
    error_message           TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/601_wecom_install_session_due_idx.up.sql

```sql
-- Drives the worker's claim scan: the oldest due session still being driven.
-- Partial on the two live states because settled sessions accumulate until the
-- retention purge and must not bloat the index the poll loop walks.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wecom_install_session_due
    ON wecom_install_session (poll_after, created_at)
    WHERE status IN ('creating', 'pending');

```

## server/go/migrations/602_wecom_install_session_request_idx.up.sql

```sql
-- Makes begin idempotent per (workspace, initiator, idempotency key), so a
-- double-clicked button or a retried request reuses one session instead of
-- burning a second WeCom generate call and showing the admin a second QR.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_wecom_install_session_request
    ON wecom_install_session (workspace_id, initiator_user_id, request_key_hash);

```

## server/go/migrations/603_wecom_install_session_agent_pending_idx.up.sql

```sql
-- At most one live scan session per agent. Two concurrent QRs for one agent
-- would race to bind it, and the loser's bot would be created on WeCom's side
-- and then silently owned by nobody.
--
-- Partial on the live states so a settled session never blocks a retry.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_wecom_install_session_agent_pending
    ON wecom_install_session (workspace_id, agent_id)
    WHERE status IN ('creating', 'pending');

```

## server/go/migrations/604_wecom_install_session_begin_rate_idx.up.sql

```sql
-- Serves the per-workspace begin rate check, which counts recent sessions to
-- stop one workspace from spending the deployment's shared WeCom generate quota.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wecom_install_session_begin_rate
    ON wecom_install_session (workspace_id, created_at, initiator_user_id);

```

## server/go/migrations/605_agent_runtime_max_concurrent_tasks.up.sql

```sql
-- Optional runtime-wide concurrency cap (GitHub #9626, #7015). An agent's
-- max_concurrent_tasks only bounds that agent; several agents bound to the
-- same runtime can still run at the same time. When set, the claim path also
-- refuses work once the runtime has this many dispatched / running /
-- waiting_local_directory tasks across all of its agents.
--
-- NULL means "no runtime cap", so every existing row keeps today's behavior.
-- Range (1..50) is validated in the handler, matching the agent limit; there
-- is no CHECK constraint so the ALTER stays a catalog-only change with no
-- table scan. Not written by the registration / heartbeat upserts, so a daemon
-- restart never clears it.
--
-- No index on this column: it is read by primary key only. The per-runtime
-- running count is served by idx_agent_task_queue_runtime_active (606).
ALTER TABLE agent_runtime ADD COLUMN IF NOT EXISTS max_concurrent_tasks INTEGER;

```

## server/go/migrations/606_agent_task_queue_runtime_active_index.up.sql

```sql
-- Single statement: CREATE INDEX CONCURRENTLY cannot run inside a transaction
-- or share a multi-command migration file.
--
-- Serves CountActiveTasksByRuntime, the runtime-wide concurrency cap check
-- (GitHub #9626) that runs on every claim for a runtime with a cap set. The
-- (runtime_id, id) index from migration 273 has no status column, so that
-- count had to read every historical task row on the runtime and filter by
-- status; cost grew with the runtime's history while the claim held the agent
-- row lock and the runtime claim lock. Partial on the capacity-bearing
-- statuses, so it only holds the few in-flight rows per runtime and stays
-- small no matter how much history accumulates.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_task_queue_runtime_active
    ON agent_task_queue (runtime_id)
    WHERE status IN ('dispatched', 'running', 'waiting_local_directory');

```

## server/go/migrations/607_inbox_item_section.up.sql

```sql
-- MUL-8483: the Inbox section ("action" or "activity") a notification was
-- routed to by its recipient's preferences at write time.
--
-- NULL means "classify by type", the rule every row followed before routing
-- existed, so existing rows need no backfill and older servers keep writing
-- valid rows. Values are validated in code (inbox.ItemSection ignores anything
-- else); there is no CHECK constraint so the ALTER stays a catalog-only change
-- with no table scan.
ALTER TABLE inbox_item ADD COLUMN IF NOT EXISTS section TEXT;

```

## server/go/migrations/608_task_usage_credits.up.sql

```sql
-- Provider-reported credits for a usage record.
--
-- Some providers bill in their own credit unit and expose no token counts at
-- all: Qoder Cloud Agents reports `session.usage.total_credits` and
-- `span.model_request_end.model_usage.credits`, nothing else. Converting those
-- to USD would need an exchange rate the provider does not publish, so the
-- figure is stored as-is next to the token counters and shown in its own unit.
--
-- UNIT: millionths of a credit, so fractional credits stay exact integers.
-- NULL means "the provider reported no credits" — every pre-existing row and
-- every token-metered provider.
ALTER TABLE task_usage
    ADD COLUMN IF NOT EXISTS credits_micros BIGINT;

```

## server/go/migrations/610_runtime_profile_add_zcode.up.sql

```sql
-- Expand the current whitelist without scanning historical rows. Replacing
-- both parts in one ALTER keeps the constraint present atomically.
ALTER TABLE runtime_profile
    DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check,
    ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'codearts',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'reasonix',
        'dsh',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw',
        'mcode',
        'muse',
        'dim',
        'zeroclaw',
        'devin',
        'zcode'
    )) NOT VALID;

```

## server/go/migrations/611_user_whats_new_seen_version.up.sql

```sql
-- Newest release whose "What's new" highlights the user has seen, as
-- MAJOR.MINOR.PATCH. NULL means the user has never dismissed the card; the
-- client then counts releases dated after the account was created.
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS whats_new_seen_version TEXT;

```

## server/go/migrations/612_skill_version.up.sql

```sql
-- Append-only content history for workspace skills (MUL-4066).
--
-- Every write that changes a skill's name, description, SKILL.md content, or
-- supporting files appends one immutable row holding a full snapshot of those
-- fields. The live skill / skill_file rows stay the source of truth for task
-- execution; this table only powers the version list and restore. Restoring
-- an old version writes its snapshot back to skill / skill_file and appends a
-- new row, so history only moves forward.
--
-- Skills that predate this table get their first row lazily: the first write
-- after deploy snapshots the pre-write state as a 'baseline' version before
-- applying the change. No backfill runs at migration time.
--
-- No FK, no cascade (workspace DB rules): DeleteSkill and workspace teardown
-- remove a skill's versions explicitly.
CREATE TABLE IF NOT EXISTS skill_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    skill_id UUID NOT NULL,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    files JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_hash TEXT NOT NULL,
    source TEXT NOT NULL,
    restored_from_version INTEGER NULL,
    created_by UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/613_skill_version_index.up.sql

```sql
-- Single-statement migration: CREATE INDEX CONCURRENTLY cannot run inside a
-- transaction or a multi-command string.
--
-- One version number per skill. Serves the version list, latest-version
-- lookup, and per-skill cleanup on delete.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_skill_version_skill_version
    ON skill_version (skill_id, version);

```

## server/go/migrations/614_project_creator.up.sql

```sql
-- Existing projects have unknown creators and remain deletable only by
-- workspace owners/admins. The mutable lead is not evidence of authorship.
ALTER TABLE project
    ADD COLUMN creator_type TEXT,
    ADD COLUMN creator_id UUID;

```

## server/go/migrations/615_attachment_image_dimensions.up.sql

```sql
-- Nullable metadata preserves compatibility with older servers and uploads.
ALTER TABLE attachment
    ADD COLUMN width integer,
    ADD COLUMN height integer;

```

## server/go/migrations/616_member_pinned.up.sql

```sql
ALTER TABLE member ADD COLUMN IF NOT EXISTS pinned_at TIMESTAMPTZ;

```

## server/go/migrations/617_connected_apps.up.sql

```sql
-- MUL-8516: Connected Apps v2 (workspace team accounts, personal accounts,
-- per-agent levels, per-action rules, confirmation requests, activity).
--
-- A personal account stays in user_composio_connection (one row per user,
-- usable in every workspace the user belongs to). A team account is new: one
-- Composio connected account owned by the workspace, created by an admin, used
-- by every agent the workspace adds it to. Its composio_user_id is
-- "ws_<workspace_id>" so a team account never shares a Composio user with a
-- person.
--
-- No foreign keys (repo rule): workspace and agent teardown delete these rows
-- explicitly. Every index is built concurrently in 618-628, following
-- wecom_install_session (600-604), so no migration builds an index inline on a
-- live table. The tables start empty, so the window between this migration
-- and its indexes carries no load.
CREATE TABLE IF NOT EXISTS workspace_composio_connection (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id         UUID NOT NULL,
    toolkit_slug         TEXT NOT NULL,
    auth_config_id       TEXT NOT NULL,
    connected_account_id TEXT NOT NULL,
    composio_user_id     TEXT NOT NULL,
    connected_by         UUID NOT NULL,
    status               TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'expired', 'revoked')),
    connected_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Which apps an agent may use, through which kind of account, at which level.
--   account_scope: team     = the workspace's team account
--                  personal = the account of whoever triggered the run
--   level:         read           = read tools only
--                  write          = everything the action rules allow
--                  confirm_writes = every non-read call needs confirmation
CREATE TABLE IF NOT EXISTS agent_app (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  UUID NOT NULL,
    agent_id      UUID NOT NULL,
    toolkit_slug  TEXT NOT NULL,
    account_scope TEXT NOT NULL CHECK (account_scope IN ('team', 'personal')),
    level         TEXT NOT NULL DEFAULT 'confirm_writes'
        CHECK (level IN ('read', 'write', 'confirm_writes')),
    created_by    UUID,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-action rules. owner_user_id NULL is the workspace's rule for the team
-- account; a user id is that member's own rule for their personal account in
-- this workspace. A missing row means the built-in default for the class.
CREATE TABLE IF NOT EXISTS app_action_rule (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  UUID NOT NULL,
    owner_user_id UUID,
    toolkit_slug  TEXT NOT NULL,
    action_class  TEXT NOT NULL
        CHECK (action_class IN ('read', 'write', 'send', 'delete', 'share')),
    policy        TEXT NOT NULL CHECK (policy IN ('allow', 'confirm', 'block')),
    updated_by    UUID,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A call an agent made that waits on a person: an action that needs
-- confirmation, or an app the person still has to connect. The arguments are
-- what the agent asked for; approved_arguments is what the approver accepted
-- (equal unless they edited it) and is exactly what Workpal executes.
CREATE TABLE IF NOT EXISTS app_action_request (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       UUID NOT NULL,
    kind               TEXT NOT NULL DEFAULT 'action' CHECK (kind IN ('action', 'connect')),
    status             TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'failed', 'cancelled')),
    task_id            UUID NOT NULL,
    agent_id           UUID NOT NULL,
    issue_id           UUID,
    chat_session_id    UUID,
    approver_user_id   UUID NOT NULL,
    account_scope      TEXT NOT NULL CHECK (account_scope IN ('team', 'personal')),
    toolkit_slug       TEXT NOT NULL,
    tool_slug          TEXT NOT NULL DEFAULT '',
    action_class       TEXT NOT NULL DEFAULT 'send',
    arguments          JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- One sentence from the agent: why it wants to make this call.
    summary            TEXT NOT NULL DEFAULT '',
    approved_arguments JSONB,
    result             JSONB,
    error              TEXT,
    reason             TEXT,
    expires_at         TIMESTAMPTZ NOT NULL,
    reminded_at        TIMESTAMPTZ,
    decided_by         UUID,
    decided_at         TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per tool call that reached the gateway, whatever its outcome. Backs
-- the activity list on app pages. Arguments are not stored here.
CREATE TABLE IF NOT EXISTS app_tool_call (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id          UUID NOT NULL,
    task_id               UUID,
    agent_id              UUID NOT NULL,
    issue_id              UUID,
    chat_session_id       UUID,
    triggered_by          UUID,
    account_scope         TEXT NOT NULL,
    account_owner_user_id UUID,
    toolkit_slug          TEXT NOT NULL,
    tool_slug             TEXT NOT NULL,
    action_class          TEXT NOT NULL,
    outcome               TEXT NOT NULL
        CHECK (outcome IN ('ok', 'error', 'blocked', 'pending', 'approved', 'rejected', 'rate_limited')),
    request_id            UUID,
    error                 TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Which apps members may connect. 'all' is every app in the catalog,
-- 'curated' only the curated ones, 'custom' only allowed_toolkits. No row
-- means 'all'.
CREATE TABLE IF NOT EXISTS workspace_app_setting (
    workspace_id     UUID PRIMARY KEY,
    catalog_mode     TEXT NOT NULL DEFAULT 'all' CHECK (catalog_mode IN ('all', 'curated', 'custom')),
    allowed_toolkits TEXT[] NOT NULL DEFAULT '{}',
    updated_by       UUID,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- An admin's correction of how one tool is classified in this workspace. It
-- wins over the curated table and the name heuristics.
CREATE TABLE IF NOT EXISTS app_tool_class_override (
    workspace_id UUID NOT NULL,
    toolkit_slug TEXT NOT NULL,
    tool_slug    TEXT NOT NULL,
    action_class TEXT NOT NULL
        CHECK (action_class IN ('read', 'write', 'send', 'delete', 'share')),
    updated_by   UUID,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, toolkit_slug, tool_slug)
);

-- Carry over agents that allowlisted toolkits under the first version. That
-- version mounted the agent owner's own accounts; the closest equivalent is a
-- personal app, and confirm_writes keeps every write behind a confirmation
-- until the owner chooses otherwise. The feature flag never shipped, so this
-- touches only internal workspaces. DISTINCT guards duplicate slugs in a row.
INSERT INTO agent_app (workspace_id, agent_id, toolkit_slug, account_scope, level, created_by)
SELECT DISTINCT a.workspace_id, a.id, lower(btrim(slug)), 'personal', 'confirm_writes', a.owner_id
FROM agent a, unnest(a.composio_toolkit_allowlist) AS slug
WHERE a.composio_toolkit_allowlist IS NOT NULL
  AND cardinality(a.composio_toolkit_allowlist) > 0
  AND btrim(slug) <> '';

```

## server/go/migrations/618_workspace_composio_connection_account_idx.up.sql

```sql
-- Upsert key for a team account callback; one row per Composio account.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_workspace_composio_connection_account
    ON workspace_composio_connection (workspace_id, connected_account_id);

```

## server/go/migrations/619_workspace_composio_connection_status_idx.up.sql

```sql
-- Hot read: the workspace's active team accounts (app list, run setup, gateway).
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workspace_composio_connection_status
    ON workspace_composio_connection (workspace_id, status, toolkit_slug);

```

## server/go/migrations/620_agent_app_agent_toolkit_idx.up.sql

```sql
-- One entry per app per agent; the upsert key for the agent's app list.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_app_agent_toolkit
    ON agent_app (agent_id, toolkit_slug);

```

## server/go/migrations/621_agent_app_workspace_toolkit_idx.up.sql

```sql
-- "Which agents use this app" on app pages and the disconnect impact check.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_app_workspace_toolkit
    ON agent_app (workspace_id, toolkit_slug);

```

## server/go/migrations/622_app_action_rule_scope_idx.up.sql

```sql
-- One rule per class for the team account and per member for their personal
-- account. NULL owner (team) folds to the nil UUID so it is unique too.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_app_action_rule_scope
    ON app_action_rule (workspace_id, toolkit_slug, action_class, COALESCE(owner_user_id, '00000000-0000-0000-0000-000000000000'::uuid));

```

## server/go/migrations/623_app_action_request_issue_idx.up.sql

```sql
-- Requests shown on an issue's timeline.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_app_action_request_issue
    ON app_action_request (issue_id, created_at)
    WHERE issue_id IS NOT NULL;

```

## server/go/migrations/624_app_action_request_pending_idx.up.sql

```sql
-- The expiry sweep and a member's pending list only ever read pending rows.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_app_action_request_pending
    ON app_action_request (expires_at)
    WHERE status = 'pending';

```

## server/go/migrations/625_app_tool_call_workspace_idx.up.sql

```sql
-- Activity on an app page, newest first.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_app_tool_call_workspace
    ON app_tool_call (workspace_id, toolkit_slug, created_at DESC);

```

## server/go/migrations/626_app_action_request_task_idx.up.sql

```sql
-- Requests of one run: duplicate detection and the chat view.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_app_action_request_task
    ON app_action_request (task_id);

```

## server/go/migrations/627_app_tool_call_issue_idx.up.sql

```sql
-- Apps an issue's runs used: the call chips and the issue sidebar.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_app_tool_call_issue
    ON app_tool_call (issue_id, created_at)
    WHERE issue_id IS NOT NULL;

```

## server/go/migrations/628_app_action_request_chat_idx.up.sql

```sql
-- Requests shown in a chat session.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_app_action_request_chat
    ON app_action_request (chat_session_id, created_at)
    WHERE chat_session_id IS NOT NULL;

```

## server/go/migrations/629_user_star_prompt.up.sql

```sql
-- Bookkeeping for the "Star us on GitHub" prompt. The prompt shows a bounded
-- number of times with a cooldown between showings, and never again once the
-- user clicks through to GitHub.
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS star_prompt_shown_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS star_prompt_last_shown_at TIMESTAMPTZ;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS star_prompt_starred_at TIMESTAMPTZ;

```

## server/go/migrations/630_project_visibility.up.sql

```sql
-- MUL-8472: private projects. 'workspace' keeps today's behavior (every
-- workspace member sees the project and its issues); 'private' limits it to
-- project_member rows plus workspace owners/admins.
--
-- The constant default makes this a catalog-only change. Values are validated
-- in code (handler.validProjectVisibilities); there is no CHECK constraint so
-- the ALTER does not scan the table, the same trade-off as inbox_item.section.
ALTER TABLE project ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'workspace';

```

## server/go/migrations/631_project_member.up.sql

```sql
-- MUL-8472: membership of a private project. Rows only matter while the
-- project is private; a workspace-visible project keeps its rows so flipping
-- it back to private restores the same list.
--
-- No foreign keys (repo rule): project deletion, member removal and workspace
-- teardown delete these rows in application code.
CREATE TABLE IF NOT EXISTS project_member (
    workspace_id UUID NOT NULL,
    project_id   UUID NOT NULL,
    user_id      UUID NOT NULL,
    added_by     UUID,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, user_id)
);

```

## server/go/migrations/632_project_member_user_idx.up.sql

```sql
-- Serves the per-request "which private projects can this user see" lookup and
-- the member-removal cleanup, both keyed by (workspace, user).
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_project_member_workspace_user
    ON project_member (workspace_id, user_id);

```

## server/go/migrations/633_issue_environment.up.sql

```sql
-- Local environments (dev servers) a daemon started or detected for one of an
-- issue's tasks. The daemon reports a full snapshot per task; an environment it
-- stops reporting is ended rather than deleted, so the issue sidebar can show
-- what ran recently.
CREATE TABLE IF NOT EXISTS issue_environment (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    issue_id     UUID NOT NULL,
    task_id      UUID NOT NULL,
    runtime_id   UUID,
    agent_id     UUID,
    local_key    TEXT NOT NULL,
    source       TEXT NOT NULL CHECK (source IN ('config', 'detected')),
    name         TEXT NOT NULL,
    label        TEXT NOT NULL DEFAULT '',
    url          TEXT NOT NULL DEFAULT '',
    port         INTEGER,
    state        TEXT NOT NULL CHECK (state IN ('starting', 'running', 'exited', 'stopped')),
    detail       TEXT NOT NULL DEFAULT '',
    started_at   TIMESTAMPTZ NOT NULL,
    expires_at   TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at     TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/634_issue_environment_task_key_idx.up.sql

```sql
-- One row per environment per task: the daemon's snapshot upserts on it.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_issue_environment_task_key
    ON issue_environment (task_id, local_key);

```

## server/go/migrations/635_issue_environment_issue_idx.up.sql

```sql
-- The issue sidebar's environment list.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_environment_issue
    ON issue_environment (issue_id, created_at);

```

## server/go/migrations/636_site_counter.up.sql

```sql
-- Running totals shown on the public marketing site, keyed by name (e.g. how
-- many turns every visitor together has blown the footer star). Rows are
-- created on first increment.
CREATE TABLE IF NOT EXISTS site_counter (
    name TEXT PRIMARY KEY,
    value BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/637_issue_environment_kind.up.sql

```sql
-- What an environment is: a server reached at its URL, or a desktop app whose
-- window only the machine running it can bring forward. A constant default
-- adds the column without rewriting the table.
ALTER TABLE issue_environment ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'server';

```

## server/go/migrations/638_issue_environment_control.up.sql

```sql
-- Controlling an issue's local environments from the sidebar (MUL-8923).
--
-- repo is the checkout directory a declared environment runs from, which
-- tells apart two repositories in one run that declare the same name.
-- excerpt holds the last redacted lines a crashed environment printed, so the
-- sidebar can say why it crashed while its machine is offline. controllable
-- marks rows reported by a daemon that accepts the commands below; rows from
-- older daemons stay read-only.
ALTER TABLE issue_environment
    ADD COLUMN IF NOT EXISTS repo TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS excerpt TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS controllable BOOLEAN NOT NULL DEFAULT false;

-- A stop, restart, start or log read a member asked a daemon to perform. The
-- daemon claims pending rows for its runtime and reports the outcome; control
-- rows double as the record of who did what. Log rows carry the output they
-- read and are deleted shortly after.
CREATE TABLE IF NOT EXISTS issue_environment_command (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id   UUID NOT NULL,
    issue_id       UUID NOT NULL,
    runtime_id     UUID NOT NULL,
    environment_id UUID,
    task_id        UUID,
    action         TEXT NOT NULL CHECK (action IN ('stop', 'restart', 'start', 'logs')),
    local_key      TEXT NOT NULL DEFAULT '',
    repo           TEXT NOT NULL DEFAULT '',
    name           TEXT NOT NULL DEFAULT '',
    actor_type     TEXT NOT NULL,
    actor_id       UUID,
    status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'claimed', 'succeeded', 'failed')),
    error          TEXT NOT NULL DEFAULT '',
    output         TEXT,
    result_key     TEXT NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_at     TIMESTAMPTZ,
    completed_at   TIMESTAMPTZ
);

-- The environments a task's repositories declare, as the daemon found them
-- when the task finished, so the sidebar can offer to start them.
CREATE TABLE IF NOT EXISTS issue_environment_config (
    task_id      UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    issue_id     UUID NOT NULL,
    runtime_id   UUID NOT NULL,
    environments JSONB NOT NULL DEFAULT '[]',
    reported_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/639_issue_environment_command_pending_idx.up.sql

```sql
-- A daemon's claim of the commands queued for one of its runtimes.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_environment_command_pending
    ON issue_environment_command (runtime_id, created_at)
    WHERE status = 'pending';

```

## server/go/migrations/640_issue_environment_command_issue_idx.up.sql

```sql
-- The issue sidebar's pending and most recent actions per environment.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_environment_command_issue
    ON issue_environment_command (issue_id, created_at);

```

## server/go/migrations/641_issue_environment_command_logs_idx.up.sql

```sql
-- The sweep that deletes log reads once their output is no longer needed.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_environment_command_logs
    ON issue_environment_command (created_at)
    WHERE action = 'logs';

```

## server/go/migrations/642_issue_environment_config_issue_idx.up.sql

```sql
-- The latest declared environments per machine for an issue.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_environment_config_issue
    ON issue_environment_config (issue_id, reported_at);

```

## server/go/migrations/643_issue_requester.up.sql

```sql
ALTER TABLE issue ADD COLUMN requester_user_id UUID NULL;

```

## server/go/migrations/644_issue_requester_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_workspace_requester ON issue (workspace_id, requester_user_id) WHERE requester_user_id IS NOT NULL;

```

## server/go/migrations/645_issue_member_creator_index.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_workspace_member_creator ON issue (workspace_id, creator_id) WHERE creator_type = 'member';

```

## server/go/migrations/646_theme_store_download.up.sql

```sql
-- How many times each community store theme has been downloaded from this
-- server: every install and every update counts once. Keyed by the registry's
-- theme id, so it is global, not workspace-owned. Rows are created on the
-- first download.
CREATE TABLE IF NOT EXISTS theme_store_download (
    theme_id TEXT PRIMARY KEY,
    downloads BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/647_project_subscriber.up.sql

```sql
-- Members who watch every issue in a project. Issue-level subscriptions stay
-- the source of per-issue intent; this row only adds the project's issues to
-- the member's notification fanout.
--
-- No foreign keys (repo rule): project deletion, member removal and workspace
-- teardown delete these rows in application code.
CREATE TABLE IF NOT EXISTS project_subscriber (
    workspace_id UUID NOT NULL,
    project_id   UUID NOT NULL,
    user_id      UUID NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, user_id)
);

```

## server/go/migrations/648_project_subscriber_user_idx.up.sql

```sql
-- Serves the member-removal cleanup, keyed by (workspace, user).
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_project_subscriber_workspace_user
    ON project_subscriber (workspace_id, user_id);

```

## server/go/migrations/649_task_context_receipt.up.sql

```sql
-- Per-run context receipt (MUL-9013): which context sources the daemon handed
-- a run, with sizes, short hashes, delivery and load evidence. Metadata only;
-- the daemon never sends source content. One row per task, replaced when the
-- daemon re-reports for a fresh-session retry.
--
-- No foreign keys (repo rule): workspace teardown (DeleteTaskBatch and the
-- workspace leaf sweep) and issue deletion remove these rows in application
-- code. issue_id is copied from the task so issue deletion can find them
-- after the legacy issue -> agent_task_queue cascade has run.
CREATE TABLE IF NOT EXISTS task_context_receipt (
    task_id      UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    issue_id     UUID,
    receipt      JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/650_task_context_receipt_workspace_idx.up.sql

```sql
-- Serves the workspace teardown sweep of task_context_receipt.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_context_receipt_workspace
    ON task_context_receipt (workspace_id);

```

## server/go/migrations/651_task_context_receipt_issue_idx.up.sql

```sql
-- Serves issue deletion's sweep of task_context_receipt.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_context_receipt_issue
    ON task_context_receipt (issue_id) WHERE issue_id IS NOT NULL;

```

## server/go/migrations/652_runtime_profile_add_droid.up.sql

```sql
-- Expand the current whitelist without scanning historical rows. Replacing
-- both parts in one ALTER keeps the constraint present atomically.
ALTER TABLE runtime_profile
    DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check,
    ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'codearts',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'reasonix',
        'dsh',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw',
        'mcode',
        'muse',
        'dim',
        'zeroclaw',
        'devin',
        'zcode',
        'droid'
    )) NOT VALID;

```

## server/go/migrations/653_chat_submission_receipt.up.sql

```sql
-- Acceptance receipts outlive message cancellation and attachment deletion.
-- Writers and session/parent deleters hold the chat_session row lock.
CREATE TABLE chat_submission_receipt (
    chat_session_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    initiator_user_id UUID NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id UUID NOT NULL,
    submission_id UUID NOT NULL,
    request_fingerprint BYTEA NOT NULL,
    response JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/654_chat_submission_receipt_key.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_chat_submission_receipt_key ON chat_submission_receipt (chat_session_id, workspace_id, initiator_user_id, actor_type, actor_id, submission_id);

```

## server/go/migrations/655_chat_submission_receipt_workspace.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_submission_receipt_workspace ON chat_submission_receipt (workspace_id);

```

## server/go/migrations/656_runtime_profile_add_amp.up.sql

```sql
-- Expand the current whitelist without scanning historical rows. Replacing
-- both parts in one ALTER keeps the constraint present atomically.
ALTER TABLE runtime_profile
    DROP CONSTRAINT IF EXISTS runtime_profile_protocol_family_check,
    ADD CONSTRAINT runtime_profile_protocol_family_check
    CHECK (protocol_family IN (
        'claude',
        'codebuddy',
        'codex',
        'copilot',
        'opencode',
        'codearts',
        'openclaw',
        'hermes',
        'pi',
        'cursor',
        'kimi',
        'reasonix',
        'dsh',
        'kiro',
        'antigravity',
        'qoder',
        'qoderclicn',
        'traecli',
        'deveco',
        'grok',
        'qwen',
        'qwenpaw',
        'mcode',
        'muse',
        'dim',
        'zeroclaw',
        'devin',
        'zcode',
        'droid',
        'amp'
    )) NOT VALID;

```

## server/go/migrations/657_inbox_item_snoozed_until.up.sql

```sql
-- MUL-9215: when a member snoozes an issue in the Inbox, every active row they
-- have on it carries the time it comes back. NULL means not snoozed, so
-- existing rows need no backfill and older servers keep writing valid rows.
-- The column is nullable with no default, which keeps the ALTER a catalog-only
-- change with no table scan.
ALTER TABLE inbox_item ADD COLUMN IF NOT EXISTS snoozed_until TIMESTAMPTZ;

```

## server/go/migrations/658_project_archive.up.sql

```sql
-- MUL-8861: archiving hides a project from the default lists, pickers and
-- agent project resolution without touching its status or its issues.
-- NULL means not archived, so existing rows need no backfill and older
-- servers keep writing valid rows. Nullable with no default, so the ALTER is
-- catalog-only. The archiving actor can be a member or an agent.
ALTER TABLE project
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_by_type TEXT,
    ADD COLUMN IF NOT EXISTS archived_by_id UUID;

```

## server/go/migrations/659_issue_view_preference_projects_page.up.sql

```sql
-- The All Projects page's display settings (layout, grouping, sort, columns,
-- filters) follow the user across devices: one per-user document, keyed by
-- the user id like the sidebar scopes.
ALTER TABLE issue_view_preference DROP CONSTRAINT issue_view_preference_scope_type_check;
ALTER TABLE issue_view_preference ADD CONSTRAINT issue_view_preference_scope_type_check
    CHECK (scope_type IN ('workspace', 'my', 'project', 'sidebar', 'sidebar_projects', 'projects_page'));

```

## server/go/migrations/660_inbox_item_snoozed_at.up.sql

```sql
-- MUL-9333: when the snooze on an issue started. The Snoozed view counts the
-- rows that arrived after it ("2 updates while snoozed"). Set together with
-- snoozed_until and cleared with it. Nullable with no default, so the ALTER is
-- a catalog-only change with no table scan and no backfill.
ALTER TABLE inbox_item ADD COLUMN IF NOT EXISTS snoozed_at TIMESTAMPTZ;

```

## server/go/migrations/661_chat_task_supplement.up.sql

```sql
ALTER TABLE task_supplement_capability ALTER COLUMN issue_id DROP NOT NULL;

CREATE TABLE chat_task_supplement (
    task_id UUID NOT NULL,
    message_id UUID NOT NULL,
    chat_session_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    author_id UUID NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'delivering', 'delivered', 'requeued', 'withdrawn')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/662_chat_task_supplement_message.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY uq_chat_task_supplement_message ON chat_task_supplement (message_id);

```

## server/go/migrations/663_chat_task_supplement_task.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_chat_task_supplement_task ON chat_task_supplement (task_id, created_at, message_id);

```

## server/go/migrations/664_chat_task_supplement_workspace.up.sql

```sql
CREATE INDEX CONCURRENTLY idx_chat_task_supplement_workspace ON chat_task_supplement (workspace_id, chat_session_id);

```

## server/go/migrations/665_weixin_state.up.sql

```sql
CREATE TABLE weixin_login_session (
    id uuid NOT NULL,
    workspace_id uuid NOT NULL,
    agent_id uuid NOT NULL,
    initiator_user_id uuid NOT NULL,
    state_encrypted bytea NOT NULL,
    status text NOT NULL DEFAULT 'wait',
    installation_id uuid,
    lease_token uuid,
    lease_expires_at timestamptz,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE weixin_account_state (
    installation_id uuid NOT NULL,
    bot_id text NOT NULL,
    user_id text NOT NULL,
    get_updates_buf text NOT NULL DEFAULT '',
    context_token_encrypted bytea NOT NULL DEFAULT '',
    context_time_ms bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now()
);

```

## server/go/migrations/666_weixin_login_expiry_idx.up.sql

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS weixin_login_expiry_idx ON weixin_login_session (expires_at);

```

## server/go/migrations/667_issue_origin_weixin_chat.up.sql

```sql
-- Extend issue.origin_type for issues created by the WeChat `/issue`
-- command. origin_id stores the chat_session id, matching the existing Lark,
-- Slack, DingTalk, and WeCom channel origins.
--
-- This only widens the allowed set. Recreate the CHECK as NOT VALID so the
-- ACCESS EXCLUSIVE lock is held briefly; migration 668 performs the table scan
-- under SHARE UPDATE EXCLUSIVE without blocking normal reads and writes.
ALTER TABLE issue DROP CONSTRAINT IF EXISTS issue_origin_type_check;
ALTER TABLE issue ADD CONSTRAINT issue_origin_type_check
    CHECK (origin_type IN ('autopilot', 'quick_create', 'lark_chat', 'slack_chat', 'agent_create', 'dingtalk_chat', 'wecom_chat', 'telegram_chat', 'weixin_chat'))
    NOT VALID;

```

## server/go/migrations/668_issue_origin_weixin_chat_validate.up.sql

```sql
-- Validate the widened CHECK separately from migration 667 so the validation
-- scan does not inherit migration 667's ACCESS EXCLUSIVE lock.
ALTER TABLE issue VALIDATE CONSTRAINT issue_origin_type_check;

```

## server/go/migrations/669_weixin_login_session_unique_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY weixin_login_session_pkey ON weixin_login_session (id);

```

## server/go/migrations/670_weixin_login_session_primary_key.up.sql

```sql
ALTER TABLE weixin_login_session ADD CONSTRAINT weixin_login_session_pkey PRIMARY KEY USING INDEX weixin_login_session_pkey;

```

## server/go/migrations/671_weixin_account_state_unique_index.up.sql

```sql
CREATE UNIQUE INDEX CONCURRENTLY weixin_account_state_pkey ON weixin_account_state (installation_id);

```

## server/go/migrations/672_weixin_account_state_primary_key.up.sql

```sql
ALTER TABLE weixin_account_state ADD CONSTRAINT weixin_account_state_pkey PRIMARY KEY USING INDEX weixin_account_state_pkey;

```

## server/go/migrations/673_runtime_rate_limit.up.sql

```sql
-- Latest subscription rate-limit snapshot per runtime (MUL-9427): how much of
-- the agent CLI account's 5-hour / weekly windows is used and when each
-- resets, as the CLI itself reported during the runtime's most recent task.
-- One row per runtime, replaced by newer observations.
--
-- No foreign keys (repo rule): runtime deletion (DeleteAgentRuntime,
-- DeleteAgentRuntimesByProfile) and workspace teardown remove these rows in
-- the same statements that delete the runtimes.
CREATE TABLE IF NOT EXISTS runtime_rate_limit (
    runtime_id   UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    snapshot     JSONB NOT NULL,
    observed_at  TIMESTAMPTZ NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

```

## server/go/migrations/674_runtime_profile_daemon.up.sql

```sql
-- NULL identifies existing profiles; only their existing daemons may refresh them.
-- Do not infer a creating machine from replicated runtime rows.
ALTER TABLE runtime_profile ADD COLUMN IF NOT EXISTS daemon_id TEXT;

```

## server/go/migrations/675_chat_wakeup.up.sql

```sql
-- Chat wakeups (MUL-9439): an agent in a chat turn records when to come back to
-- this conversation and what to do then. The platform watches the condition or
-- the clock and starts one chat turn in the same session when it is due.
--
-- kind:
--   condition — the platform polls a stored fact (an issue's status, a run
--               ending, a pull request merging, a person replying) and fires
--               once when it holds.
--   at        — fires once at fire_at.
--   check     — the agent itself looks every interval_seconds; a check that
--               finds nothing checks in silently and the conversation stays
--               quiet. It ends when the agent finishes it or it expires.
--
-- Every wakeup has an end. expires_at is required; reaching it before the
-- condition holds starts one last turn so the agent can say where things
-- stand instead of going quiet.
--
-- requester_id is the person the turn answers to: whoever sent the message
-- that asked for it, which in a group chat need not be the session creator.
--
-- No foreign keys (repo rule): DeleteChatSession, workspace teardown and
-- system-agent deletion remove a session's wakeups in the same transaction,
-- and the dispatcher drops a wakeup whose session is gone.
CREATE TABLE IF NOT EXISTS chat_wakeup (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    chat_session_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    requester_id UUID NOT NULL,
    source_task_id UUID,
    source_message_id UUID,
    title TEXT NOT NULL,
    instruction TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('condition', 'at', 'check')),
    condition JSONB,
    condition_state TEXT NOT NULL DEFAULT '',
    interval_seconds BIGINT,
    fire_at TIMESTAMPTZ,
    next_eval_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'fired', 'expired', 'cancelled', 'failed')),
    end_reason TEXT,
    ended_at TIMESTAMPTZ,
    check_count INTEGER NOT NULL DEFAULT 0,
    last_check_note TEXT,
    last_checked_at TIMESTAMPTZ,
    last_checkin_task_id UUID,
    last_task_id UUID,
    last_fired_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((kind = 'condition') = (condition IS NOT NULL)),
    CHECK ((kind = 'at') = (fire_at IS NOT NULL)),
    CHECK ((kind = 'check') = (interval_seconds IS NOT NULL))
);

-- Indexes are built concurrently in 676–678.

-- The hidden input row of a wakeup turn names its wakeup, so clients can head
-- the reply with what brought the agent back. NULL for every other row.
ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS wakeup_id UUID;

```

## server/go/migrations/676_chat_wakeup_due_idx.up.sql

```sql
-- Serves the dispatcher's scan for wakeups that are due.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_wakeup_due
    ON chat_wakeup (next_eval_at) WHERE status = 'active';

```

## server/go/migrations/677_chat_wakeup_session_idx.up.sql

```sql
-- Serves a conversation's wakeup list, its active-count limit and its cleanup.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_wakeup_session
    ON chat_wakeup (chat_session_id, created_at DESC);

```

## server/go/migrations/678_chat_wakeup_requester_idx.up.sql

```sql
-- Serves the per-person active limit and workspace teardown.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_wakeup_requester
    ON chat_wakeup (workspace_id, requester_id, created_at DESC);

```

## server/go/migrations/679_entitlement_limit_overage.up.sql

```sql
-- Per-workspace record of attempts that went over an entitlement limit, for
-- every gate and both acting modes. Under observe the attempt was admitted and
-- only recorded here; under enforce it was rejected. Rollout dashboards, over-
-- limit notices and grace periods read this table instead of metrics, which
-- carry no workspace label.
--
-- One row per workspace, gate and Cloud-defined period. limit_value is the
-- latest limit seen in the period and peak_usage the highest usage an attempt
-- would have reached, so peak_usage - limit_value is how far over the limit the
-- workspace went.
--
-- The scope unique index is built concurrently in 680. No foreign keys (repo
-- rule): workspace deletion removes these rows explicitly.
CREATE TABLE IF NOT EXISTS entitlement_limit_overage (
    workspace_id UUID NOT NULL,
    gate TEXT NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    limit_value BIGINT NOT NULL CHECK (limit_value >= 0),
    peak_usage BIGINT NOT NULL CHECK (peak_usage >= 0),
    observed_count BIGINT NOT NULL DEFAULT 0 CHECK (observed_count >= 0),
    enforced_count BIGINT NOT NULL DEFAULT 0 CHECK (enforced_count >= 0),
    first_exceeded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_exceeded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (period_start < period_end)
);

```

## server/go/migrations/680_entitlement_limit_overage_scope_idx.up.sql

```sql
-- Upsert key for RecordEntitlementLimitExceeded and the per-workspace lookup.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_entitlement_limit_overage_scope
    ON entitlement_limit_overage (workspace_id, gate, period_start, period_end);

```

## server/go/migrations/681_project_folder.up.sql

```sql
-- Project folders (MUL-9390): a one-level, workspace-wide grouping of
-- projects. A project sits in at most one folder (project.folder_id); NULL
-- means it is in none. Folders do not nest and are not an access boundary: a
-- private project stays visible only to its members wherever it is filed.
--
-- No foreign keys (repo rule): DeleteProjectFolder clears project.folder_id in
-- the same transaction, and workspace teardown removes the folders with the
-- projects. Clients treat a folder_id they cannot resolve as no folder.
--
-- The name index is built concurrently in 682.
CREATE TABLE IF NOT EXISTS project_folder (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    name TEXT NOT NULL,
    creator_type TEXT,
    creator_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE project ADD COLUMN IF NOT EXISTS folder_id UUID;

```

## server/go/migrations/682_project_folder_name_idx.up.sql

```sql
-- One folder per name in a workspace, case-insensitively, and the lookup for
-- listing a workspace's folders.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_project_folder_workspace_name
    ON project_folder (workspace_id, LOWER(name));

```

## server/go/ee/projectfolder/queries.sql

```sql
-- name: ListProjectFolders :many
SELECT * FROM project_folder
WHERE workspace_id = $1
ORDER BY LOWER(name), created_at;

-- name: ListFiledProjects :many
SELECT id, folder_id FROM project
WHERE workspace_id = $1 AND folder_id IS NOT NULL;

-- name: CreateProjectFolder :one
INSERT INTO project_folder (workspace_id, name, creator_type, creator_id)
VALUES ($1, $2, $3, $4)
RETURNING *;

-- name: RenameProjectFolder :one
UPDATE project_folder SET
    name = $3,
    updated_at = now()
WHERE id = $1 AND workspace_id = $2
RETURNING *;

-- name: DeleteProjectFolder :one
DELETE FROM project_folder
WHERE id = $1 AND workspace_id = $2
RETURNING id;

-- Filing a project is not an edit of the project, so neither query touches
-- updated_at (and with it the project's last activity).

-- name: ClearProjectFolder :exec
UPDATE project SET folder_id = NULL
WHERE workspace_id = $1 AND folder_id = $2;

-- name: FileProject :execrows
-- Affects no row when the folder is not in the workspace.
UPDATE project SET folder_id = sqlc.arg('folder_id')
WHERE project.id = sqlc.arg('project_id') AND project.workspace_id = sqlc.arg('workspace_id')
  AND EXISTS (
    SELECT 1 FROM project_folder f
    WHERE f.id = sqlc.arg('folder_id') AND f.workspace_id = sqlc.arg('workspace_id')
  );

-- name: UnfileProject :exec
UPDATE project SET folder_id = NULL
WHERE id = $1 AND workspace_id = $2;

```

## Query contracts

### server/go/pkg/db/queries/activity.sql

Queries: ListActivitiesForIssue :many, GetActivity :one, CreateActivity :one, HasSquadLeaderNoActionEvaluationForTask :one, CountAssigneeChangesByActor :many, GetLastIssueStatusChange :one

### server/go/pkg/db/queries/agent.sql

Queries: ListAgents :many, ListAllAgents :many, ListAllAgentsAnyKind :many, GetAgent :one, GetAgentForUpdate :one, LockAgentForTaskEnqueue :one, GetAgentInWorkspace :one, LockAgentForAutopilotAssignment :one, CreateAgent :one, CreateAgentBuilder :one, DeleteSystemAgentByID :exec, RebindAgentBuilderRuntime :one, UpdateAgent :one, ClearAgentComposioToolkitAllowlist :one, ClearAgentThinkingLevel :one, ClearAgentServiceTier :one, ClearAgentMcpConfig :one, UpdateAgentCustomEnv :one, UpdateAgentDisabledRuntimeSkills :one, ArchiveAgent :one, ArchiveAgentsByRuntime :many, ArchiveAgentsByIDs :many, ListActiveAgentsByRuntime :many, ListActiveAgentsByRuntimeForUpdate :many, ListUserAgentIDsByRuntime :many, ListUserAgentsByRuntimeForUpdate :many, ListNonOwnerAgentsByRuntime :many, ListNonOwnerAgentsByRuntimeForUpdate :many, RestoreAgent :one, ListAgentTasks :many, CreateAgentTask :one, CreateDeferredChannelIssueTask :one, PromoteDeferredChannelIssueTask :one, SetDeferredChannelIssueTaskRuntimeOverlay :execrows, CreateQuickCreateTask :one, LinkTaskToIssue :exec, CreateRetryTask :one, SetTaskWorkflowStep :exec, CreateManualQuickCreateRetryTask :one, DeleteUnstartedQuickCreateRetryTask :execrows, CancelAgentTasksByIssue :many, CancelPendingTasksByIssueAndAgent :many, CancelPendingTasksByIssueAndAgentInThread :many, ReassignPendingAgentTasksToRuntime :one, CancelAgentTasksByAgent :many, CancelAgentTasksByTriggerComment :many, CancelAgentTasksByChatSession :many, GetAgentTask :one, GetAgentTaskStatus :one, GetAgentTaskForDelegatedFailureUpdate :one, HasRetryTaskForParent :one, GetAgentTaskInWorkspace :one, ClaimAgentTask :one, SetTaskDeliveredCommentIDs :one, SetTaskIssueSnapshot :exec, RequeueAgentTaskAfterClaimFailure :one, ReclaimStaleDispatchedTaskForRuntime :one, ReclaimStaleDispatchedTasksForRuntimes :many, ExtendAgentTaskPrepareLease :one, LockAgentTaskStartClaim :one, MarkAgentTaskWaitingLocalDirectory :one, CompleteAgentTask :one, GetLastTaskSession :one, GetLatestTaskRolloutMissing :one, GetLatestChatTaskRolloutMissing :one, FailAgentTask :one, UpdateAgentTaskSession :exec, RecoverOrphanedTasksForRuntime :many, FailStaleTasks :many, ExpireStaleQueuedTasks :many, FailExpiredRuntimeReconnectRetries :many, CancelAgentTask :one, CancelAgentTaskByUser :one, SetAgentTaskBranchName :exec, SetAgentTaskDurableWorkDir :exec, IsTaskSessionRetired :one, SetAgentTaskRetiredSessionIDIfCancelled :execrows, SetAgentTaskErrorIfEmpty :exec, CancelAgentTaskWithReason :one, CancelQueuedAgentTask :one, CancelQueuedAgentTasksForSession :many, MarkChatFinalizeDeferred :one, ClaimChatFinalizeDeferred :one, ListChatFinalizeDeferredExpired :many, CountRunningTasks :one, GetAgentForClaimUpdate :one, HasTaskForIssue :one, HasActiveTaskForIssue :one, HasPendingTaskForIssue :one, HasPendingTaskForIssueAndAgent :one, HasPendingTaskForIssueAndAgentInThread :one, HasPendingTaskForIssueAndAgentExcludingTriggerComment :one, HasPendingTaskForIssueAndAgentExcludingTriggerCommentInThread :one, MergeCommentIntoPendingTask :one, RegisterPlannedCommentForActiveTask :one, MergeDelegatedFailureCommentIntoPendingTask :one, HasTaskCoveringDelegatedFailureComment :one, CountDelegatedFailureRecoveryTasks :one, AcknowledgeExhaustedDelegatedFailureRecovery :one, SettleDelegatedFailureRecoveriesForTask :execrows, SettleDelegatedFailureRecoveryComment :execrows, ListPendingDelegatedFailureRecoveries :many, HasActiveTaskForIssueAndAgent :one, HasActiveTaskForIssueAndAgentInThread :one, GetLatestTaskRoleForIssueAndAgent :one, ListPendingTasksByRuntime :many, ListQueuedClaimCandidatesByRuntime :many, CancelSupersededDeferredRetriesForRuntimes :many, PromoteDueDeferredTasksForRuntime :many, ListQueuedClaimCandidatesByRuntimes :many, NextDeferredTaskFireAtForRuntimes :one, PromoteDueDeferredTasksForRuntimes :many, ListActiveTasksByIssue :many, ListActiveTasksByIssueFamily :many, GetWorkspaceAgentRunCounts :many, GetWorkspaceAgentActivity30d :many, ListWorkspaceAgentTaskSnapshot :many, ListWorkspaceWorkingAgents :many, ListTasksByIssue :many, ListTasksByIssueSubtree :many, UpdateAgentStatus :one, RefreshAgentStatusFromTasks :one, GetAgentBySystemKey :one, CreateSystemUserAgent :one, GetCommentThreadRootID :one

### server/go/pkg/db/queries/agent_builder.sql

Queries: UpsertAgentBuilderDraft :one, DeleteAgentBuilderDraft :exec, DeleteAgentBuilderDraftsBySystemRuntimeAgents :exec

### server/go/pkg/db/queries/agent_invocation_target.sql

Queries: ListAgentInvocationTargets :many, ListAgentInvocationTargetsByAgentIDs :many, CreateAgentInvocationTarget :exec, DeleteAgentInvocationTargets :exec, DeleteAgentInvocationTargetsByMember :exec, DeleteAgentInvocationTargetsBySystemRuntimeAgents :exec

### server/go/pkg/db/queries/attachment.sql

Queries: CreateAttachment :one, ListAttachmentsByIssue :many, ListAttachmentsByComment :many, GetAttachment :one, GetAttachmentByIDOnly :one, ListAttachmentsByCommentIDs :many, ListSourceContextIssueAttachments :many, ListSourceContextCommentAttachments :many, ListAttachmentURLsByIssueOrComments :many, ListAttachmentURLsByCommentID :many, DeleteCommentAttachments :many, LinkAttachmentsToComment :exec, ReplaceCommentAttachments :execrows, LinkAttachmentsToChatMessage :many, DetachAttachmentsFromUserChatMessageByTask :many, CountUnboundChatAttachmentsForTask :one, BindChatAttachmentsToMessage :many, ListAttachmentsByChatMessage :many, ListAttachmentsByChatMessageIDs :many, LockAttachmentsForIssueLink :many, LockUnboundAttachmentsForCommentLink :many, LockAttachmentsForCommentLink :many, LockAttachmentRow :one, LinkAttachmentsToIssue :one, DeleteAttachment :one, ListAttachmentsByIDs :many, CreateSourceContextAttachment :one, ListAttachmentsBySourceContext :many, DeleteAttachmentsBySourceContext :many, ListSourceContextAttachmentURLsByWorkspace :many, DeleteSourceContextAttachmentsByWorkspace :exec

### server/go/pkg/db/queries/autopilot.sql

Queries: ListAutopilots :many, GetAutopilot :one, GetAutopilotInWorkspace :one, LockAutopilotForUpdate :one, CreateAutopilot :one, UpdateAutopilot :one, ArchiveAutopilot :exec, PauseAutopilotsByUnboundAgents :many, PauseAutopilotsByUnrunnableSquad :many, PauseAutopilotsByArchivedProject :many, UpdateAutopilotLastRunAt :exec, CreateAutopilotRuleVersion :one, GetActiveAutopilotRuleVersion :one, ListAutopilotTriggers :many, GetAutopilotTrigger :one, GetAutopilotTriggerForAutopilot :one, CreateAutopilotTrigger :one, SetAutopilotTriggerPublisher :exec, SetAutopilotTriggerPublishersByAutopilot :exec, UpdateAutopilotTrigger :one, DeleteAutopilotTrigger :exec, AdvanceTriggerNextRun :exec, GetWebhookTriggerByToken :one, TouchAutopilotTriggerFiredAt :exec, RotateAutopilotTriggerWebhookToken :one, SetAutopilotTriggerWebhookToken :one, SetAutopilotTriggerSigningSecret :one, CreateAutopilotRun :one, GetAutopilotRunByTriggerAndPlanned :one, GetAutopilotRunByWebhookDelivery :one, ResumeFailedWebhookIssueDelivery :one, GetAutopilotRunByQuotaReservation :one, RecoverPartialAutopilotRun :one, GetAutopilotRun :one, ListAutopilotRuns :many, UpdateAutopilotRunIssueCreated :one, SetAutopilotRunDispatchTask :execrows, UpdateAutopilotRunRunning :one, UpdateAutopilotRunSkipped :one, UpdateAutopilotRunTerminalWithQuota :one, ListSchedulableAutopilotTriggers :many, CreateAutopilotTask :one, GetAutopilotTaskByRun :one, GetAutopilotRunByIssue :one, GetLatestAutopilotRunForIssueAttribution :one, FailAutopilotRunsByIssue :many, SelectAutopilotsExceedingFailureThreshold :many, SystemPauseAutopilot :one, ListAutopilotSubscribers :many, ListAutopilotSubscribersForAutopilots :many, AddAutopilotSubscriber :exec, DeleteAutopilotSubscribersForAutopilot :exec, DeleteAutopilotSubscribersByMember :exec, ListAutopilotCollaborators :many, AddAutopilotCollaborator :one, DeleteAutopilotCollaborator :exec, DeleteAutopilotCollaboratorsForAutopilot :exec, IsAutopilotCollaborator :one, ListAutopilotIDsForCollaborator :many

### server/go/pkg/db/queries/autopilot_quota.sql

Queries: EnsureAutopilotQuotaPeriod :one, GetAutopilotQuotaPeriod :one, GetAutopilotQuotaReservationByKey :one, CreateAutopilotQuotaReservation :one, IncrementAutopilotQuotaReserved :one, IncrementAutopilotQuotaBlocked :one, MarkAutopilotQuotaRejectionNotified :one, ConsumeAutopilotQuotaReservation :one, ReleaseAutopilotQuotaReservation :one, ListRecoverableAutopilotQuotaReservations :many

### server/go/pkg/db/queries/channel.sql

Queries: UpsertChannelInstallation :one, UpsertChannelInstallationByAppID :one, GetChannelInstallation :one, GetChannelInstallationInWorkspace :one, GetChannelInstallationByAppID :one, GetChannelInstallationOwnerByAppID :one, LockChannelInstallationAppIDSlot :exec, GetChannelInstallationSlotOwnerByAppID :one, ReclaimDeadChannelInstallationByAppID :one, ClearChannelInstallationBotScopedRows :one, DeleteChannelInstallationsBySystemRuntimeAgents :exec, ListChannelInstallationsByWorkspace :many, ListActiveChannelInstallations :many, ListAllActiveChannelInstallations :many, SetChannelInstallationStatus :exec, SetChannelInstallationConfig :exec, BackfillChannelInstallationRegionToFeishuLark :execrows, AcquireChannelWSLease :one, ReleaseChannelWSLease :exec, CreateChannelUserBinding :one, GetChannelUserBindingByUserID :one, FindChannelBindingForMember :one, FindChannelBindingForMemberOnAgentInstallation :one, FindReusableChannelUserBinding :one, DeleteChannelUserBindingsByWorkspaceMember :exec, DeleteChannelUserBindingsByInstallation :exec, CreateChannelChatSessionBinding :one, CreateChannelChatSessionBindingGeneration :one, GetChannelChatSessionBinding :one, LockCurrentChannelChatSessionBinding :one, LockCurrentChannelChatSessionBindingBySession :one, RetireChannelChatSessionBinding :one, GetChannelChatSessionBindingBySession :one, GetChannelChatSessionBindingBySessionAny :one, ListChannelChatSessionBindingsBySessions :many, UpdateChannelChatSessionBindingReplyTarget :exec, LockChannelChatSessionBindingForContext :one, ClearChannelChatSessionPendingFreshForRevision :exec, AdvanceChannelChatContextGeneration :one, LockChannelChatContextGenerationByRevision :one, ResolveChannelChatContextHistoryStart :exec, SetChannelChatContextInitiator :one, SetChannelChatContextReplyTarget :exec, ClearChannelChatContextPendingFresh :exec, GetChannelChatContextGeneration :one, DeleteChannelChatSessionBindingBySession :exec, DeleteChannelChatSessionBindingsByInstallation :exec, CreateChannelTaskDeliveryFromSession :one, GetChannelTaskDelivery :one, CopyChannelTaskDelivery :exec, RecordChannelOutboundMessage :exec, ListChannelOutboundMessageIDsForBinding :many, ListChannelOutboundMessagesByIDs :many, ClaimChannelInboundDedup :one, MarkChannelInboundDedupProcessed :execrows, ReleaseChannelInboundDedup :execrows, PurgeChannelInboundDedup :exec, RecordChannelInboundDrop :exec, ListChannelInboundAuditByInstallation :many, NullChannelInboundAuditInstallationID :exec, CreateChannelOutboundCardMessage :one, GetChannelOutboundCardByTask :one, UpdateChannelOutboundCardStatus :exec, DeleteChannelOutboundCardMessagesBySession :exec, CreateChannelBindingToken :one, FindLiveChannelBindingToken :one, ConsumeChannelBindingToken :one, PurgeExpiredChannelBindingTokens :exec, DeleteChannelBindingTokensByInstallation :exec, RecordChannelMediaPendingObject :one, ClaimChannelMediaPendingObjectsForBind :many, ClaimNextChannelMediaPendingObjectForReconcile :one, ReleaseChannelMediaPendingObject :exec, TombstoneChannelMediaPendingObject :execrows, DeleteChannelMediaPendingObject :execrows, ChannelMediaObjectIsReferenced :one, GetChannelReplyTurn :one, AcquireChannelReplyDelivery :one, GetChannelReplyDelivery :one, ReleaseChannelReplyDelivery :execrows, RenewChannelReplyDelivery :execrows, MarkChannelReplyDeliverySending :execrows, RecordChannelReplyDeliveryPlaceholder :execrows, RecordChannelReplyDeliveryChunk :execrows, ResetChannelReplyDeliverySend :execrows, MarkChannelReplyDeliverySendUnknown :execrows, SettleChannelReplyDelivery :execrows, CloseChannelReplyDeliveryTurn :one, IsChannelMessageTypingActive :one

### server/go/pkg/db/queries/channel_typing.sql

Queries: RegisterChannelTypingReaction :one, FinishChannelTypingReactionAdd :one, AcknowledgeChannelTypingReactionCleanup :exec, ClaimChannelTypingReactionCleanup :many, SettleChannelTypingInputs :exec, PruneChannelTypingReactionCleanup :exec, ExpireChannelTypingReactionCleanup :many, SkipChannelTypingReactionAdd :exec, ListRequestedChannelTypingReactions :many

### server/go/pkg/db/queries/chat.sql

Queries: CreateChatSession :one, ClearChatSessionProjectByProject :exec, GetChatSession :one, GetChatSessionInWorkspace :one, ListChatSessionCreators :many, GetPublicChatSessionInWorkspace :one, ListChatSessionsByCreator :many, ListAllChatSessionsByCreator :many, ListAgentBuilderSessionsByCreator :many, UpdateChatSessionTitle :one, MarkChatSessionExplicitlyCreated :one, InitializeChatSessionTitle :one, ReplaceImplicitChatSessionTitle :one, InitializeChatSessionMediaTitle :one, UpdateChatSessionProject :one, UpdateChatSessionTitleIfCurrent :one, SetChatSessionPinned :one, SetChatSessionArchived :one, UpdateChatSessionSession :exec, ClearChatSessionSessionIfMatches :exec, AdvanceCancelledChatSessionPointer :exec, LockChatSessionForDelete :one, LockChatSessionForAppend :one, LockChatSessionForRuntimeBind :one, LockChatSessionForEnqueue :one, LockChatSessionForDraftWrite :one, DeleteChatSession :exec, TouchChatSession :exec, CreateChatMessage :one, TaskHasChannelIngestedMessages :one, GetTaskChannelOrigin :one, SetChatMessageChannelOutboundProvenanceByTask :execrows, ListChannelOutboundMessageIDsForContext :many, GetChannelMediaPendingUntil :one, ClearChatMessageChannelMediaPending :exec, UpdateChatMessageContentForChannelMedia :execrows, LinkChatMessageToTask :exec, LinkUnownedChannelChatMessagesToTask :exec, ListUnownedChannelChatContextRevisions :many, DeferChatTaskForSealedPendingMedia :one, DeleteUserChatMessageByTask :one, ReleaseOnboardingKickoffFromTask :exec, ListChatMessages :many, ListChatMessagesForLegacyTask :many, ListChatInputMessages :many, ListChatMessagesPageForChannelContext :many, ReanchorClaimedDirectChatInput :exec, ReanchorNextQueuedDirectChatInput :exec, ListChatMessagesPage :many, GetChatMessage :one, CreateChatTask :one, PromoteChannelChatTasksIfMediaReady :many, SetChatTaskInputOwnerSelf :one, GetLastChatTaskSession :one, HasActiveChatTaskForSession :one, HasPendingChatTurnForSession :one, GetPendingChatTask :one, ListPendingChatTasksForSession :many, PrioritizeQueuedChatTask :one, ListPendingChatTasksByCreator :many, HasPendingChatTasksByCreator :one, MarkChatSessionRead :exec, ChatSessionHasUserMessage :one, ChatSessionHasPublicUserMessage :one, CreateChatDraftRestore :one, ListChatDraftRestoresBySession :many, DeleteChatDraftRestore :execrows, DeleteChatDraftRestoresBySession :exec, LockChatSessionForTask :one, LockChatSessionsByWorkspace :many, LockChatSessionsBySystemRuntimeAgents :many, DeleteChatDraftRestoresBySystemRuntimeAgents :exec, GetChatMessageByTaskAssistant :one, TaskInputIsOnboardingKickoffOnly :one, CreateMikaOnboardingOpening :one, AdoptOrphanOnboardingKickoff :exec, GetLatestAssistantChatMessageForSession :one, SetChatMessageQuickActionsByTask :one, GetOldestActiveChatSessionForCreatorAgent :one

### server/go/pkg/db/queries/chat_cancel.sql

Queries: HasTaskMessages :one

### server/go/pkg/db/queries/chat_pinned_agent.sql

Queries: ListChatPinnedAgents :many, CreateChatPinnedAgent :one, DeleteChatPinnedAgent :exec, DeleteChatPinnedAgentsByWorkspace :exec, DeleteChatPinnedAgentsBySystemRuntimeAgents :exec, GetMaxChatPinnedAgentPosition :one

### server/go/pkg/db/queries/chat_submission.sql

Queries: GetChatSubmissionReceipt :one, CreateChatSubmissionReceipt :exec, DeleteChatSubmissionReceiptsBySession :exec, DeleteChatSubmissionReceiptsBySystemRuntimeAgents :exec

### server/go/pkg/db/queries/chat_supplement.sql

Queries: LockRunningChatTaskForSupplement :one, CreateChatTaskSupplement :exec, ClaimNextChatTaskSupplement :one, AckChatTaskSupplement :one, LockUndeliveredChatTaskSupplements :many, RequeueChatTaskSupplement :exec, RetainChatTaskSupplementsForRetry :exec, DeleteChatTaskSupplementsBySession :exec, HasChatTaskAssistantOutcome :one, ListChatGuidanceInProviderSession :many, DeleteChatTaskSupplementsByWorkspace :exec, DeleteChatSupplementCapabilitiesBySession :exec, WithdrawChatTaskSupplementsByRuntime :exec, WithdrawChatTaskSupplementsByTasks :exec, WithdrawChatTaskSupplementsByAgent :exec

### server/go/pkg/db/queries/chat_wakeup.sql

Queries: CreateChatWakeup :one, GetChatWakeup :one, GetChatWakeupInSession :one, LockChatWakeupInSession :one, LockChatWakeup :one, CountActiveChatWakeupsForSession :one, CountActiveChatWakeupsForRequester :one, ListChatWakeupsForSession :many, ListChatWakeupsForSessionOwner :many, ListDueChatWakeupIDs :many, SetChatWakeupEvaluation :exec, DeferChatWakeup :exec, RecordChatWakeupFire :one, RecordChatWakeupRetry :one, EndChatWakeup :one, UpdateChatWakeupConfig :one, CheckInChatWakeup :one, EndActiveChatWakeupsForSession :many, GetChatWakeupInputForTask :one, DeleteChatWakeupInput :exec, GetChatWakeupTaskStatus :one, DeleteChatWakeupsBySession :exec, DeleteChatWakeup :exec, DeleteChatWakeupsBySystemRuntimeAgents :exec

### server/go/pkg/db/queries/client_usage.sql

Queries: UpsertClientUsageDaily :one

### server/go/pkg/db/queries/comment.sql

Queries: ListCommentsForIssue :many, ListCommentsByIDsForIssue :many, ListCommentOriginsForIssue :many, ListChildCommentsForParents :many, ListCommentsSinceForIssue :many, ListRootCommentsForIssue :many, ListRootCommentsSinceForIssue :many, ListThreadCommentsForIssuePaged :many, ListRecentThreadCommentsForIssue :many, CountComments :one, CountNewCommentsSince :one, GetLatestMemberCommentForIssueSince :one, ListReconcilableCommentsForIssueSince :many, GetComment :one, GetCommentInWorkspace :one, GetThreadRoot :one, CreateComment :one, GetDelegatedFailureRecoveryComment :one, GetDelegatedFailureRecoveryExhaustionComment :one, UpdateComment :one, BumpCommentRevision :one, HasAgentCommentedSince :one, HasAgentRepliedInThread :one, LockCommentForDelete :one, LockLiveComment :one, CommentHasReplies :one, TombstoneComment :one, DeleteLeafComment :one, DeleteReplylessCommentTombstone :one, TouchIssueForCommentDelete :one, ResolveComment :one, ClearOtherThreadResolutions :many, UnresolveComment :one, ListCommentAncestorPath :many, ListCommentThreadHistory :many, LockCommentAncestorPath :many, ListThreadMemberAuthors :many

### server/go/pkg/db/queries/composio.sql

Queries: UpsertUserComposioConnection :one, ListActiveUserComposioConnections :many, GetUserComposioConnection :one, MarkUserComposioConnectionRevoked :exec

### server/go/pkg/db/queries/connected_apps.sql

Queries: UpsertWorkspaceComposioConnection :one, ListWorkspaceComposioConnections :many, GetWorkspaceComposioConnection :one, SetWorkspaceComposioConnectionStatus :exec, RevokeOtherWorkspaceComposioConnections :many, TouchWorkspaceComposioConnection :exec, TouchUserComposioConnection :exec, SetComposioConnectionStatusByAccount :exec, ListUserComposioConnectionsAnyStatus :many, ListAgentApps :many, ListAgentAppsInWorkspace :many, UpsertAgentApp :one, DeleteAgentAppsExcept :exec, ListAppActionRules :many, ListAppActionRulesForRun :many, UpsertAppActionRule :one, CreateAppActionRequest :one, FindPendingAppActionRequest :one, GetAppActionRequest :one, ListPendingAppActionRequestsForIssue :many, ListDecidedAppActionRequestsForIssue :many, ListPendingAppActionRequestsForChatSession :many, ListDecidedAppActionRequestsForChatSession :many, CancelAppActionRequest :one, CancelPendingAppActionRequestsForApprover :many, ListPendingAppActionRequestsForApprover :many, DecideAppActionRequest :one, SetAppActionRequestOutcome :one, ExpireDueAppActionRequests :many, ClaimAppActionRequestReminders :many, CancelPendingTeamAppActionRequests :many, CountPendingTeamAppActionRequests :one, CountActiveTasksForAgents :one, CountActiveAutopilotsForAgents :one, InsertAppToolCall :exec, ListTeamAppToolCalls :many, ListPersonalAppToolCalls :many, GetWorkspaceAppSetting :one, UpsertWorkspaceAppSetting :one, ListAppToolClassOverrides :many, GetAppToolClassOverride :one, UpsertAppToolClassOverride :exec, DeleteAppToolClassOverride :exec, CountRecentAppAccountCalls :one, HasBlockedAppToolCall :one, ListIssueAppToolCalls :many, ListPendingConnectRequestsForUser :many, AppendQueuedTaskHandoffNote :execrows, SetAgentComposioToolkitAllowlist :exec

### server/go/pkg/db/queries/contact_sales.sql

Queries: CreateContactSalesInquiry :one, CountRecentContactSalesByEmail :one

### server/go/pkg/db/queries/conversation_root.sql

Queries: ListConversationRootOwners :many

### server/go/pkg/db/queries/daemon_token.sql

Queries: CreateDaemonToken :one, GetDaemonTokenByHash :one, DeleteDaemonTokensByWorkspaceAndDaemons :many, DeleteExpiredDaemonTokens :exec, ListLegacyDaemonTokenOwners :many

### server/go/pkg/db/queries/dingtalk.sql

Queries: ListDingTalkUserBindingsForMember :many, LockDingTalkInstallationOwner :exec, GetDingTalkInstallationOwnerForUpdate :one, UpsertDingTalkBotIdentity :one, RecordDingTalkGroupPresence :one, RecordDingTalkGroupActivity :one, ListDingTalkGroupPresencesByWorkspace :many, CountInactiveDingTalkGroupPresencesByWorkspace :many, ListDingTalkBotIdentitiesByWorkspace :many, ForgetDingTalkGroupPresence :one, DeleteDingTalkInstallationForReplacement :one

### server/go/pkg/db/queries/entitlement_overage.sql

Queries: RecordEntitlementLimitExceeded :one, ListWorkspaceEntitlementLimitOverages :many, ListEntitlementLimitOveragesForPeriod :many, SyncEntitlementLimitOverageLimit :exec

### server/go/pkg/db/queries/feedback.sql

Queries: CreateFeedback :one, CountRecentFeedbackByUser :one

### server/go/pkg/db/queries/feishu_verification.sql

Queries: RecordFeishuInboundReceipt :exec, SetFeishuInstallationBotUnionID :exec, BackfillLegacyFeishuInboundReceipts :execrows

### server/go/pkg/db/queries/github.sql

Queries: ListGitHubInstallationsByWorkspace :many, ListGitHubInstallationsWithConnectedBy :many, ListGitHubInstallationsByInstallationID :many, GetGitHubInstallationByID :one, CreateGitHubInstallation :one, DeleteGitHubInstallation :exec, DeleteGitHubInstallationByInstallationID :many, UpdateGitHubInstallationAccountByInstallationID :many, UpsertPendingGitHubInstallation :one, DeletePendingGitHubInstallation :exec, GetPendingGitHubInstallation :one, UpsertGitHubPullRequest :one, GetGitHubPullRequest :one, ListPullRequestsByIssue :many, ListIssuePullRequestSummaries :many, GetIssueReviewHeadSha :one, ListIssueIDsForPullRequest :many, LinkIssueToPullRequest :execrows, LinkIssueToPullRequestManually :execrows, ListAutoLinkedIssueIDsForPullRequest :many, UnlinkIssueFromPullRequest :execrows, GetGitHubPullRequestInWorkspace :one, FindGitHubPullRequestByURL :one

### server/go/pkg/db/queries/github_snapshot.sql

Queries: ListGitHubPRRowsByAddress :many, UpdateGitHubPRSnapshot :execrows, DeleteGitHubPRCheckRuns :exec, InsertGitHubPRCheckRun :exec, ListStaleUndecidedGitHubPRs :many, ListStaleConflictWatchedGitHubPRs :many, ListConflictWatchedGitHubPRNumbersInRepo :many, ListGitHubPRNumbersByHeadSHA :many, GetGitHubPullRequestByID :one

### server/go/pkg/db/queries/inbox.sql

Queries: ListInboxItems :many, ListArchivedInboxItems :many, GetInboxItemInWorkspace :one, CreateInboxItem :one, MarkInboxRead :one, MarkInboxUnread :one, ArchiveInboxItem :one, DeleteInboxGroup :execrows, ArchiveInboxByIssue :execrows, UnarchiveInboxItem :one, UnarchiveInboxByIssue :execrows, ArchiveInboxByIssueAndType :many, CountUnreadInbox :one, CountUnreadInboxByWorkspace :many, MarkAllInboxRead :execrows, MarkInboxReadByIssue :execrows, ArchiveAllInbox :execrows, ArchiveAllReadInbox :execrows, ArchiveCompletedInbox :execrows, SnoozeInboxGroup :many, UnsnoozeInboxGroup :many, ListSnoozedInbox :many

### server/go/pkg/db/queries/inbox_archive.sql

Queries: ListArchivedInboxPage :many, ArchivedInboxFacets :many

### server/go/pkg/db/queries/invitation.sql

Queries: CreateInvitation :one, GetInvitation :one, ListPendingInvitationsByWorkspace :many, ListPendingInvitationsForUser :many, AcceptInvitation :one, DeclineInvitation :one, RevokeInvitation :execrows, GetPendingInvitationByEmail :one, HasPendingInvitationForEmail :one, ExpireStalePendingInvitations :many

### server/go/pkg/db/queries/issue.sql

Queries: ListIssues :many, GetIssue :one, CountIssuesInTriage :one, GetIssueTriageState :one, GetIssueGCStatus :one, ListIssueGCStatuses :many, GetIssueInWorkspace :one, GetIssueMetadataInWorkspace :one, LockIssueForChannelMediaBind :one, LockIssueForAttachmentWrite :one, LockIssueForDescriptionUpdate :one, MaterializeIssueChannelMediaMarkdown :one, LockIssueForDelete :one, DetachDirectChildIssues :many, CreateIssue :one, GetIssueByNumber :one, UpdateIssue :one, UpdateIssueStatus :one, LockIssuesForDuplicateMark :many, IssueHasDuplicates :one, ListIssueDuplicates :many, GetIssueRefInWorkspace :one, ListIssueRefsInWorkspace :many, ClearIssueDuplicatesOf :many, CreateIssueWithOrigin :one, LockIssueDuplicateKey :exec, FindActiveDuplicateIssue :one, FindRecentAutopilotDuplicateIssue :one, DeleteIssue :exec, ListOpenIssues :many, CountIssues :one, ListChildIssues :many, ListChildrenByParents :many, GetIssueByOrigin :one, CountCreatedIssueAssignees :many, ChildIssueProgress :many, SetIssueMetadataKey :one, DeleteIssueMetadataKey :one, MarkIssueFirstExecuted :one, ResolveIssueRequester :one

### server/go/pkg/db/queries/issue_environment.sql

Queries: ListOpenIssueEnvironmentsByTask :many, UpsertIssueEnvironment :one, EndIssueEnvironmentsMissingFromSnapshot :exec, ListIssueEnvironments :many, GetIssueEnvironment :one, CreateIssueEnvironmentCommand :one, HasOpenIssueEnvironmentControl :one, ClaimIssueEnvironmentCommands :many, CompleteIssueEnvironmentCommand :one, GetIssueEnvironmentCommand :one, ListIssueEnvironmentControls :many, DeleteIssueEnvironmentLogCommandsBefore :execrows, UpsertIssueEnvironmentConfig :exec, ListLatestIssueEnvironmentConfigs :many, GetIssueEnvironmentConfig :one

### server/go/pkg/db/queries/issue_label.sql

Queries: ListLabels :many, GetLabel :one, CreateLabel :one, UpdateLabel :one, DeleteLabel :one, DeleteIssueLabelAssignmentsByLabel :exec, DeleteAgentLabelAssignmentsByLabel :exec, DeleteSkillLabelAssignmentsByLabel :exec, DeleteAgentLabelAssignmentsByAgent :exec, DeleteSkillLabelAssignmentsBySkill :exec, DeleteAgentLabelAssignmentsBySystemRuntimeAgents :exec, AttachLabelToIssueOnCreate :exec, AttachLabelToIssue :one, DetachLabelFromIssue :one, ListLabelsByIssue :many, ListLabelsForIssues :many, ListLabelsByAgent :many, ListLabelsForAgents :many, AttachLabelToAgent :exec, DetachLabelFromAgent :exec, ListLabelsBySkill :many, ListLabelsForSkills :many, AttachLabelToSkill :exec, DetachLabelFromSkill :exec

### server/go/pkg/db/queries/issue_property.sql

Queries: ListIssueProperties :many, GetIssueProperty :one, CountActiveIssueProperties :one, CreateIssueProperty :one, UpdateIssueProperty :one, SetIssuePropertyValue :one, DeleteIssuePropertyValue :one, CountIssuesUsingPropertyOptions :many

### server/go/pkg/db/queries/issue_reaction.sql

Queries: AddIssueReaction :one, RemoveIssueReaction :one, ListIssueReactions :many

### server/go/pkg/db/queries/issue_status.sql

Queries: SeedIssueStatusEntries :exec, ListIssueStatusEntries :many, GetIssueStatusEntryByKey :one, GetIssueStatusEntryByID :one, CreateIssueStatusEntry :one, UpdateIssueStatusEntry :one, ArchiveIssueStatusEntry :one, CountIssuesUsingStatusKey :one, DeleteIssueStatusEntriesForWorkspace :exec, LockIssueStatusCatalog :exec, LockIssueStatusCatalogShared :exec, ListIssueStatusKeysByCategories :many, ListActiveCustomIssueStatusEntries :many, ReorderIssueStatusEntries :execrows

### server/go/pkg/db/queries/issue_unread.sql

Queries: MarkIssueUnreadForSubscribers :many, ListIssueUnread :many, MarkIssueRead :execrows, MarkIssueUnreadManually :execrows

### server/go/pkg/db/queries/issue_view.sql

Queries: CreateIssueView :one, ListIssueViewsForUser :many, ListAllIssueViewsForUser :many, CountIssueViewsByOwner :one, GetIssueView :one, UpdateIssueView :one, DeleteIssueView :one, DeleteIssueViewsByProjectScope :exec, DeletePrivateIssueViewsByOwner :exec, DeleteIssueViewPreferencesByUser :exec

### server/go/pkg/db/queries/issue_view_preference.sql

Queries: GetIssueViewPreference :one, UpsertIssueViewPreference :one

### server/go/pkg/db/queries/issue_workflow.sql

Queries: ListIssueWorkflows :many, GetDefaultIssueWorkflow :one, CreateDefaultIssueWorkflow :many, ListNamedIssueWorkflowSteps :many, RemoveStatusFromDefaultIssueWorkflow :exec, ListProjectsUsingDefaultIssueWorkflow :many, GetIssueWorkflow :one, CreateIssueWorkflow :one, UpdateIssueWorkflow :one, DeleteIssueWorkflow :execrows, DeleteIssueWorkflowsForWorkspace :exec, ListIssueWorkflowNamesUsingStatusKey :many, ListProjectsUsingIssueWorkflow :many, CountProjectIssuesByStatus :many, RemapProjectIssueStatus :many, LockProjectForWorkflowChange :one, SetProjectWorkflow :one

### server/go/pkg/db/queries/member.sql

Queries: ListMembers :many, ListWorkspaceManagerUserIDs :many, GetMember :one, GetMemberByUserAndWorkspace :one, GetRealtimeMemberships :many, CreateMember :one, UpdateMemberRole :one, DeleteMember :exec, ListMembersWithUser :many

### server/go/pkg/db/queries/member_delegation.sql

Queries: RecordMemberDelegationDay :exec

### server/go/pkg/db/queries/notification_preference.sql

Queries: GetNotificationPreference :one, UpsertNotificationPreference :one, PatchNotificationPreference :one, ListNotificationPreferencesByUsers :many

### server/go/pkg/db/queries/personal_access_token.sql

Queries: CreatePersonalAccessToken :one, GetPersonalAccessTokenByHash :one, ListPersonalAccessTokensByUser :many, RevokePersonalAccessToken :one, UpdatePersonalAccessTokenLastUsed :exec, ExtendPersonalAccessTokenExpiry :one

### server/go/pkg/db/queries/pinned_item.sql

Queries: ListPinnedItems :many, CreatePinnedItem :one, DeletePinnedItem :exec, UpdatePinnedItemPosition :exec, GetMaxPinnedItemPosition :one, DeletePinnedItemsByItem :exec

### server/go/pkg/db/queries/plugin.sql

Queries: LockPluginPackageKey :exec, CreatePluginPackage :one, UpdatePluginPackageName :one, GetWorkspacePluginPackageByKey :one, GetWorkspacePluginPackage :one, ListWorkspacePluginPackages :many, DeletePluginPackage :exec, CreatePluginPackageVersion :one, ListPluginPackageVersions :many, GetWorkspacePluginPackageVersion :one, DeletePluginPackageVersionsByPackage :exec, CountInstallationsOfPackageVersions :one, CreatePluginPackageFile :exec, GetPluginPackageFile :one, ListPluginPackageFilePaths :many, DeletePluginPackageFilesByPackage :exec, CreatePluginInstallation :one, UpdatePluginInstallationManifest :one, UpdatePluginInstallationConfig :one, SetPluginInstallationEnabled :one, GetPluginInstallation :one, GetWorkspacePluginInstallation :one, GetWorkspacePluginInstallationByKey :one, ListWorkspacePluginInstallations :many, DeletePluginInstallation :exec, CreatePluginHookSchedule :one, GetPluginHookSchedule :one, ListPluginHookSchedulesByInstallation :many, ListEnabledPluginHookSchedules :many, UpdatePluginHookScheduleDefinition :one, DisablePluginHookSchedules :exec, ReactivatePluginHookSchedule :one, UpdatePluginHookScheduleNextRun :execrows, DeletePluginHookSchedule :exec, DeletePluginHookSchedulesByInstallation :exec, UpsertPluginStorageValue :one, GetPluginStorageValue :one, ListPluginStorageKeys :many, DeletePluginStorageValue :execrows, GetPluginStorageUsage :one, DeletePluginStorageByInstallation :exec, UpsertPluginSecret :exec, ListPluginSecretKeys :many, GetPluginSecret :one, DeletePluginSecret :execrows, DeletePluginSecretsByInstallation :exec, SetPluginInstallationToken :exec, GetPluginInstallationByTokenHash :one, CreatePluginInvocation :one, ListPluginInvocations :many, CountRecentPluginInvocations :one, CountRecentPluginFailures :one, DeletePluginInvocationsByInstallation :exec, DeleteExpiredPluginInvocations :execrows, UpsertPluginSkill :one, ListPluginSkills :many, DeletePluginSkillsByInstallation :exec, DeletePluginSkillsNotIn :exec, SetPluginMCPApprovals :one

### server/go/pkg/db/queries/pr_automation.sql

Queries: GetIssuePRAutoCompleteDisabled :one, SetIssuePRAutoCompleteDisabled :exec, IsPullRequestExcludedFromIssue :one, ExcludePullRequestFromIssue :exec, DeletePullRequestExclusion :exec, ListIssueLinkedPullRequestStates :many, MoveIssueFromPullRequests :one

### server/go/pkg/db/queries/project.sql

Queries: ListProjects :many, ArchiveProject :one, RestoreProject :one, GetProjectInWorkspace :one, LockProjectForChatSessionCreate :one, LockProjectForDelete :one, CreateProject :one, UpdateProject :one, DeleteProject :exec, CountIssuesByProject :one, GetProjectIssueStats :many

### server/go/pkg/db/queries/project_member.sql

Queries: ListPrivateProjectIDs :many, ListHiddenProjectIDsForUser :many, ListPrivateProjectAudience :many, ListProjectMembers :many, ListProjectMemberUserIDs :many, AddProjectMembers :many, DeleteProjectMember :execrows, DeleteProjectMembersByProject :exec, DeleteProjectMembersByUser :exec, GetProjectAccessManager :one, UpdateProjectVisibility :one, GetIssueProjectID :one, GetCommentIssueProjectID :one, TouchProjectSearchIndexEntries :exec, ListIssueProjectIDs :many, ListAutopilotRunProjectIDs :many

### server/go/pkg/db/queries/project_owner_recovery.sql

Queries: ListPrivateProjects :many, ListPrivateProjectMembers :many

### server/go/pkg/db/queries/project_resource.sql

Queries: ListProjectResources :many, ListProjectResourcesInWorkspace :many, ListProjectResourcesForProjects :many, GetProjectResource :one, GetProjectResourceInWorkspace :one, GetProjectResourceInWorkspaceForUpdate :one, CreateProjectResource :one, UpdateProjectResource :one, DeleteProjectResource :exec, CountProjectResources :one, GetProjectResourceCounts :many

### server/go/pkg/db/queries/project_subscriber.sql

Queries: AddProjectSubscriber :exec, RemoveProjectSubscriber :exec, IsProjectSubscriber :one, ListProjectSubscribersForIssue :many, DeleteProjectSubscribersByProject :exec, DeleteProjectSubscribersByUser :exec

### server/go/pkg/db/queries/qoder_issue_lifecycle.sql

Queries: LockQoderTaskIssue :one, SetQoderIssueRevision :exec

### server/go/pkg/db/queries/quick_action.sql

Queries: ListQuickActions :many, GetQuickAction :one, CountActiveQuickActions :one, CreateQuickAction :one, UpdateQuickAction :one, DeleteQuickAction :exec, DeletePrivateQuickActionsByCreator :exec, TouchQuickActionUsage :exec

### server/go/pkg/db/queries/reaction.sql

Queries: AddReaction :one, RemoveReaction :one, ListReactionsByCommentIDs :many, DeleteCommentReactions :exec

### server/go/pkg/db/queries/runtime.sql

Queries: ListAgentRuntimes :many, ListAgentRuntimeIDsByWorkspace :many, ListVisibleAgentRuntimes :many, GetAgentRuntime :one, GetAgentRuntimes :many, GetAgentRuntimeHeartbeatLeases :many, LockAgentRuntime :one, LockAgentRuntimeForClaimDelivery :one, GetAgentRuntimeForWorkspace :one, UpsertAgentRuntime :one, UpsertAgentRuntimeWithProfile :one, UpdateAgentRuntimeVisibility :one, UpdateAgentRuntimeCustomName :one, UpdateAgentRuntimeCustomNameByDaemon :many, ListDaemonCustomNames :many, TouchAgentRuntimeLastSeen :execrows, TouchAgentRuntimesLastSeenBatch :many, MarkAgentRuntimeOnline :one, MarkAgentRuntimeOnlineIfOffline :execrows, SetAgentRuntimeOffline :exec, SetAgentRuntimeOfflineWithReason :exec, SelectStaleOnlineRuntimes :many, MarkRuntimesOfflineByIDs :many, FailTasksForOfflineRuntimes :many, ListAgentRuntimesByOwner :many, ForceOfflineRuntimesByIDs :many, CancelAgentTasksByRuntimeOrAgent :many, ListNonOwnerActiveTasksByRuntime :many, ListNonOwnerActiveTasksByRuntimeForUpdate :many, LockAgentRuntimeForAccessChange :one, LockRuntimeRevocationChatSessions :many, CancelNonOwnerTasksByRuntime :many, CountUndrainedTasksByRuntimeOrAgent :one, UnbindTasksFromRuntime :execrows, UnbindUserAgentsFromRuntime :many, UnbindNonOwnerAgentsFromRuntime :many, DeleteAgentRuntime :exec, DeleteSystemAgentsByRuntime :exec, CountActiveAgentsByRuntime :one, FindLegacyRuntimesByDaemonID :many, ReassignAgentsToRuntime :execrows, LockWorkspaceForRuntimeMerge :exec, LockRuntimesForMerge :many, ReassignTasksToRuntime :one, RecordRuntimeLegacyDaemonID :exec, ListStaleOfflineRuntimeGCCandidates :many, IsAgentRuntimeEligibleForGC :one, CountTasksByRuntime :one, ListRuntimeOwnersByDaemon :many, LockRuntimeShareMembers :many, LockRuntimeShareMemberRemoval :one, ListSharedAgentRuntimesForUpdate :many, UpdateAgentRuntimeMaxConcurrentTasks :one, GetAgentRuntimeMaxConcurrentTasks :one, LockRuntimeClaimCapacity :exec, CountActiveTasksByRuntime :one

### server/go/pkg/db/queries/runtime_profile.sql

Queries: CreateRuntimeProfile :one, GetRuntimeProfile :one, GetRuntimeProfileForWorkspace :one, LockRuntimeProfileForRegistration :one, LockRuntimeProfileForDelete :one, ListRuntimeProfiles :many, ListEnabledRuntimeProfilesForWorkspace :many, ListEnabledRuntimeProfilesForDaemon :many, ListEnabledRuntimeProfilesForOwner :many, RuntimeProfileHasDaemonInstance :one, ListRuntimeProfileMachines :many, UpdateRuntimeProfile :one, DeleteRuntimeProfile :exec, DeleteAgentRuntimesByProfile :many, ListActiveAgentsByProfile :many, ListAgentRuntimeIDsByProfile :many

### server/go/pkg/db/queries/runtime_rate_limit.sql

Queries: UpsertRuntimeRateLimit :exec, GetRuntimeRateLimit :one

### server/go/pkg/db/queries/runtime_usage.sql

Queries: ListRuntimeUsage :many, GetRuntimeTaskHourlyActivity :many, ListRuntimeUsageByAgent :many, GetRuntimeUsageByHour :many

### server/go/pkg/db/queries/search_index.sql

Queries: GetSearchIndexManifest :one, GetSearchIndexCurrentSnapshot :one, ListSearchIndexIssuesPage :many, ListSearchIndexIssuesByIDs :many, ListSearchIndexCommentsByIssues :many, ListSearchIndexCommentsByIDs :many, ListSearchIndexProjects :many, ListSearchIndexProjectsByIDs :many, SearchIndexSinceIsPruned :one, ListSearchIndexChanges :many, PruneSearchIndexChanges :one, DeleteWorkspaceSearchIndexChanges :exec

### server/go/pkg/db/queries/seat_capacity.sql

Queries: UpsertSeatCapacityIntent :one, EnqueueSeatCapacityRelease :one, GetSeatCapacityIntent :one, GetClaimedSeatCapacityIntent :one, CreateOrReactivateShareJoinCapacityIntent :one, GetMemberReleaseCapacityIntent :one, DeleteSeatCapacityConfirmIntentsForWorkspaceDeletion :exec, PrepareSeatCapacityOperationReleasesForWorkspaceDeletion :exec, PrepareSeatCapacityInvitationReleasesForWorkspaceDeletion :exec, PrepareSeatCapacityMemberReleasesForWorkspaceDeletion :exec, ClaimNextDueSeatCapacityIntent :one, MarkSeatCapacityIntentDelivered :exec, MarkSeatCapacityIntentFailed :exec, MarkClaimedSeatCapacityIntentDeadLettered :execrows, TransitionSeatCapacityIntent :execrows, TransitionClaimedSeatCapacityIntent :execrows, MarkClaimedSeatCapacityIntentFailed :execrows, DeferClaimedSeatCapacityIntent :execrows, DeleteSeatCapacityIntentForAction :exec, DeleteClaimedSeatCapacityIntent :execrows, ExpireInvitationForCapacityRecovery :exec

### server/go/pkg/db/queries/share_link.sql

Queries: CreateShareLink :one, ClaimShareLinkByID :one, GetActiveShareLinkByCode :one, GetShareLinkInfoByCode :one, ListShareLinksByWorkspace :many, DeactivateWorkspaceShareLinks :exec, RevokeShareLink :exec

### server/go/pkg/db/queries/site_counter.sql

Queries: GetSiteCounter :one, AddSiteCounter :one

### server/go/pkg/db/queries/skill.sql

Queries: ListSkillsByWorkspace :many, ListSkillSummariesByWorkspace :many, GetSkill :one, GetSkillInWorkspace :one, GetSkillByWorkspaceAndName :one, CreateSkill :one, UpdateSkill :one, TouchSkill :one, DeleteSkill :exec, ListSkillFiles :many, ListSkillFilesBySkillIDs :many, ListSkillFileMetadata :many, GetSkillFile :one, UpsertSkillFile :one, DeleteSkillFile :exec, DeleteSkillFilesBySkill :exec, ListAgentSkills :many, ListAgentSkillsByIDs :many, ListAgentSkillSummaries :many, ListAgentSkillNamesByAgentIDs :many, AddAgentSkill :exec, SetAgentSkillEnabled :execrows, RemoveAgentSkill :exec, RemoveAllAgentSkills :exec, ListAgentSkillsByWorkspace :many, LockSkillForVersioning :one, GetLatestSkillVersion :one, CreateSkillVersion :one, ListSkillVersions :many, GetSkillVersion :one

### server/go/pkg/db/queries/source_context.sql

Queries: CreateIssueSourceContext :one, GetIssueSourceContextByIssue :one, GetIssueSourceContextByID :one, GetPendingIssueSourceContextByOriginTask :one, AttachIssueSourceContext :one, TransferPendingIssueSourceContextTask :one, DeleteIssueSourceContextByIssue :one, ListIssueSourceContextsForWorkspace :many, DeleteIssueSourceContextsForWorkspace :many, ListExpiredPendingSourceContextsForCleanup :many, AbandonIssueSourceContext :execrows, ListAbandonedSourceContextsForCleanup :many, DeleteAbandonedIssueSourceContext :execrows, RecordSourceContextObjectIntent :one, RecordSourceContextDeletionObjectIntent :one, DeletePendingSourceContextObjectIntents :many, ClaimSourceContextObjectIntentForCleanup :one, SourceContextObjectIntentIsReferenced :one, ReleaseSourceContextObjectIntent :execrows, DeleteClaimedSourceContextObjectIntent :execrows, ListSourceContextObjectIntentURLsByWorkspace :many, DeleteSourceContextObjectIntentsByWorkspace :exec

### server/go/pkg/db/queries/squad.sql

Queries: CreateSquad :one, GetSquad :one, GetSquadInWorkspace :one, LockSquadForAutopilotAssignment :one, LockSquadForUpdate :one, ListSquads :many, ListSquadMemberPreviewRows :many, ListSquadMemberPreviewRowsBySquad :many, ListInvolvedSquadIDs :many, ListAllSquads :many, UpdateSquad :one, ArchiveSquad :one, AddSquadMember :one, RemoveSquadMember :execrows, ListSquadMembers :many, UpdateSquadMemberRole :one, IsSquadMember :one, CountSquadMembers :one, GetSquadByAssignee :one, ListSquadsByMember :many, TransferSquadAssignees :exec, TransferSquadAutopilotsToLeader :exec, ListSquadMemberStatusRows :many

### server/go/pkg/db/queries/subscriber.sql

Queries: AddIssueSubscriber :execrows, LockSubscriberWrites :exec, AddDelegatedSubscriber :execrows, LockActiveMember :one, DeleteSubscriptionsByMember :exec, SubscribeToIssueExplicitly :exec, RemoveIssueSubscriber :exec, UndoIssueUnsubscribe :one, UnsubscribeFromIssueSubtree :many, HasAncestorOptOut :one, ListIssueSubscribers :many, ListSubscribedIssueIDs :many, IsIssueSubscriber :one, GetDelegatedSubscriptionFacts :one

### server/go/pkg/db/queries/supplement.sql

Queries: StartAgentTaskWithSupplement :one, CreateTaskSupplement :one, GetTaskSupplementByRequest :one, LockTaskForSupplementBind :one, BindCommentTaskSupplement :one, GetRunningTaskForAgentOnIssue :one, ListUndeliveredTaskSupplementCommentIDs :many, DeleteUndeliveredTaskSupplementForRun :execrows, GetTaskSupplementForRun :one, CommentHasTaskSupplement :one, GetTaskSupplementCapability :one, ListTaskSupplementsByCommentIDs :many, ListTaskSupplementMetadata :many, SettleTerminalTaskSupplements :execrows, ClaimNextTaskSupplement :one, AckTaskSupplementDelivered :one, AckTaskSupplementFailed :one, RetryTaskSupplement :one, LockTaskSupplementsByComment :many, DeleteTaskSupplementByComment :exec

### server/go/pkg/db/queries/system_wakeup.sql

Queries: GetSystemWakeup :one, CreateSystemWakeup :one, CustomizeSystemWakeup :one, ApplySystemWakeupDefault :many, CountCustomizedSystemWakeups :one, MergeWorkspaceSettings :exec, ListParentsWithoutSystemWakeup :many, ListChildConditionWakeups :many, ClaimChildEvents :many, ListUnprocessedClosedChildren :many, FinishChildEvents :exec, ListStaleChildEventParents :many, DeleteProcessedChildEvents :execrows

### server/go/pkg/db/queries/task_cleanup.sql

Queries: TaskBlockedByProcessCleanup :one, FailCancelledTaskProcessCleanup :one, MarkPiTaskProcessCleanupPending :exec, ClearTaskProcessCleanupPending :exec, MarkMuseAppRecoveryCleanupUnconfirmed :many, TaskWaitingForProcessCleanup :one

### server/go/pkg/db/queries/task_context_receipt.sql

Queries: UpsertTaskContextReceipt :exec, GetTaskContextReceipt :one

### server/go/pkg/db/queries/task_message.sql

Queries: CreateTaskMessage :one, CreateTaskMessages :many, ListTaskMessages :many, ListTaskMessagesSince :many, ListTaskProgressSince :many, DeleteTaskMessages :exec, ListTaskReplyFragments :many

### server/go/pkg/db/queries/task_token.sql

Queries: CreateTaskToken :one, GetTaskTokenByHash :one, DeleteTaskTokensByTask :exec, DeleteExpiredTaskTokens :exec

### server/go/pkg/db/queries/task_usage.sql

Queries: UpsertTaskUsage :exec, GetTaskUsage :many, ListIssueTaskUsage :many, ListTaskUsageByIDs :many, ListAgentTaskUsage :many, GetIssueUsageSummary :one, ListDashboardUsageDaily :many, ListDashboardUsageByAgent :many, ListDashboardRunTimeDaily :many, ListDashboardAgentRunTime :many, ListDashboardFailuresDaily :many, ListDashboardFailuresByAgent :many

### server/go/pkg/db/queries/theme_store_download.sql

Queries: ListThemeStoreDownloads :many, AddThemeStoreDownload :exec

### server/go/pkg/db/queries/user.sql

Queries: GetUser :one, GetUserByEmail :one, GetUsersByIDs :many, CreateUser :one, UpdateUser :one, MarkUserOnboarded :one, PatchUserOnboarding :one, AdvanceWhatsNewSeenVersion :one, ClaimStarPromptShowing :one, MarkStarPromptStarred :one, JoinCloudWaitlist :one

### server/go/pkg/db/queries/vcs.sql

Queries: ListVCSConnectionsByWorkspace :many, GetVCSConnectionByID :one, UpsertVCSConnection :one, DeleteVCSConnection :exec, RotateVCSConnectionWebhookSecret :one, UpsertVCSPullRequest :one, ListVCSPullRequestsByIssue :many, UpsertVCSCommitStatus :exec, ListIssueIDsForVCSPRHead :many, LinkIssueToVCSPullRequest :execrows, LinkIssueToVCSPullRequestManually :execrows, ListIssueIDsForVCSPullRequest :many, ListAutoLinkedIssueIDsForVCSPullRequest :many, UnlinkIssueFromVCSPullRequest :execrows, GetVCSPullRequestByKey :one, GetVCSPullRequestInWorkspace :one, FindVCSPullRequestByURL :one

### server/go/pkg/db/queries/verification_code.sql

Queries: CreateVerificationCode :one, GetLatestVerificationCode :one, MarkVerificationCodeUsed :exec, IncrementVerificationCodeAttempts :exec, GetLatestCodeByEmail :one, DeleteExpiredVerificationCodes :exec

### server/go/pkg/db/queries/wakeup.sql

Queries: CreateIssueWakeup :one, ListIssueWakeups :many, ListWorkspaceWakeupSummaryRows :many, GetIssueWakeup :one, LockIssueWakeup :one, LockWakeupIssue :one, LockWakeupSourceTask :one, CancelUnstartedWakeupTasks :many, DisableIssueWakeups :exec, CancelUnstartedIssueWakeupTasks :many, ListInputWakeups :many, ListDueWakeups :many, ListPendingWakeupInputGroups :many, ListPendingWakeupReceipts :many, DeleteExpiredWakeupReceipts :execrows, RecordWakeupReceipt :one, ConsumeWakeupReceipts :exec, DiscardWakeupReceipts :exec, AdvanceIssueWakeup :exec, FindPendingWakeupTask :one, CreateWakeupTask :one, LocklessWakeup :one, ReplaceWakeupEvidence :one, NoteWakeupFailure :exec, TouchWakeupDispatch :exec, MarkWakeupTimedOut :exec, SetWakeupConditionState :exec, PauseIssueWakeup :exec, CountWakeupFires :exec, CountRecentWakeupTasks :one, ListWakeupChains :many, ListWakeupRuns :many, DeleteIssueWakeupReceipts :exec, DeleteIssueWakeup :exec, ListPausedWakeupIssues :many, FindWaitingIssueRun :one, ListWaitingWakeups :many, TryLockIssueWakeup :one, ReserveWakeupReceipts :exec, ReleaseWakeupReceipts :exec, SetClaimedTaskContext :one, CountActiveIssueRunsOfAgent :one

### server/go/pkg/db/queries/webhook_delivery.sql

Queries: CreateWebhookDelivery :one, GetWebhookReplayByIdempotencyKey :one, GetWebhookDelivery :one, GetWebhookDeliveryInWorkspace :one, GetWebhookDeliveryByTriggerAndDedupe :one, BumpWebhookDeliveryAttempt :one, AcknowledgeWebhookDelivery :one, ClaimQueuedWebhookDelivery :one, DeferClaimedWebhookDelivery :one, RetryClaimedWebhookDelivery :one, CompleteClaimedWebhookDelivery :one, UpdateWebhookDeliveryDispatched :one, UpdateWebhookDeliveryTerminal :one, ListWebhookDeliveriesByAutopilot :many

### server/go/pkg/db/queries/wecom_install_session.sql

Queries: LockWecomInstallBeginWorkspace :exec, GetWecomInstallSessionByRequestHash :one, GetPendingWecomInstallSessionByAgent :one, CountWecomInstallSessionsInWindow :one, GetActiveWecomInstallationForAgent :one, CreateWecomInstallSession :one, GetWecomInstallSession :one, ClaimDueWecomInstallSession :one, DeferClaimedWecomInstallSession :execrows, CompleteWecomInstallSession :execrows, FailWecomInstallSession :execrows, PurgeTerminalWecomInstallSessions :execrows

### server/go/pkg/db/queries/weixin.sql

Queries: CreateWeixinLoginSession :one, GetWeixinLoginSession :one, LockWeixinLoginSession :one, ClaimWeixinLoginSession :one, UpdateWeixinLoginSession :execrows, ReleaseWeixinLoginSession :exec, CancelWeixinLoginSession :execrows, CancelPreviousWeixinLogins :exec, PurgeWeixinState :exec, GetWeixinInstallationForAgent :one, ResetWeixinAccountState :exec, GetWeixinAccountState :one, SaveWeixinContext :execrows, SaveWeixinCursor :execrows, DeleteWeixinAccountState :exec, ExpireWeixinInstallation :execrows, IsWeixinTypingActive :one, SettleWeixinTypingInputs :exec

### server/go/pkg/db/queries/workflow_handoff.sql

Queries: LockWorkflowSquadHandoff :exec, GetWorkflowSquadHandoffTask :one, ListAssigneeRunsForHandoff :many

### server/go/pkg/db/queries/workspace.sql

Queries: ListWorkspaces :many, ListDaemonWorkspaces :many, GetDaemonWorkspace :one, GetWorkspace :one, GetWorkspaceBySlug :one, GetWorkspaceAttributionFailClosed :one, CreateWorkspace :one, UpdateWorkspace :one, IncrementIssueCounter :one, HealIssueCounter :one, LockWorkspaceForDelete :one, LockWorkspaceForChatSessionCreate :one, DeleteWorkspace :exec, SetWorkspacePinned :one

### server/go/pkg/db/queries/workspace_delete.sql

Queries: SetWorkspaceTeardownMode :exec, LockTaskUsageRollupForWorkspaceDelete :exec, LockWorkspaceTaskOwnerAgents :exec, LockWorkspaceTaskOwnerIssues :exec, LockWorkspaceTaskOwnerRuntimes :exec, ListWorkspaceAgentIDFirstPage :many, ListWorkspaceAgentIDPage :many, ListWorkspaceIssueIDFirstPage :many, ListWorkspaceIssueIDPage :many, ListWorkspaceRuntimeIDFirstPage :many, ListWorkspaceRuntimeIDPage :many, ListTaskIDsByAgentFirstPage :many, ListTaskIDsByAgentPage :many, ListTaskIDsByIssueFirstPage :many, ListTaskIDsByIssuePage :many, ListTaskIDsByRuntimeFirstPage :many, ListTaskIDsByRuntimePage :many, DetachTaskBatchReferences :exec, DeleteTaskBatch :exec, DeleteTaskTokensByAgent :exec, PrepareWorkspaceDeletionLinks :exec, DeleteWorkspaceLeafData :exec, DeleteWorkspaceChatMessages :exec, DeleteWorkspaceCommunicationRoots :exec, DeleteWorkspaceComments :exec, DeleteWorkspaceIssueRoots :exec, DeleteWorkspaceAutopilotRuns :exec, DeleteWorkspaceAutopilotQuotaReservations :exec, DeleteWorkspaceAutopilotQuotaPeriods :exec, DeleteWorkspaceEntitlementLimitOverages :exec, DeleteWorkspaceAutopilotChildren :exec, DeleteWorkspaceAutopilots :exec, DeleteWorkspacePullRequests :exec, DeleteWorkspaceConnections :exec, DeleteWorkspaceSquadsAndSkills :exec, DeleteWorkspacePluginData :exec, DeleteWorkspaceAgents :exec, DeleteWorkspaceRuntimesAndProjects :exec, DeleteWorkspaceAdministration :exec

### server/go/pkg/db/queries/workspace_mcp.sql

Queries: ListWorkspaceMcpServers :many, CountWorkspaceMcpServerAgents :many, LockWorkspaceMcpServerForShare :one, LockWorkspaceMcpServerForUpdate :one, GetWorkspaceMcpServer :one, CreateWorkspaceMcpServer :one, UpdateWorkspaceMcpServer :one, DeleteWorkspaceMcpServer :execrows, DeleteAgentMcpServersByServer :exec, ListAgentMcpServers :many, ListEnabledAgentMcpServers :many, AddAgentMcpServer :exec, SetAgentMcpServerEnabled :execrows, RemoveAgentMcpServer :execrows

### server/go/pkg/db/queries/workspace_wakeup.sql

Queries: ListWorkspaceWakeups :one
