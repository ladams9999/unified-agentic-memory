CREATE TABLE IF NOT EXISTS uam.schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS uam.events (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    client TEXT NOT NULL,
    agent_name TEXT,
    model_name TEXT,
    event_name TEXT NOT NULL,
    tool_name TEXT,
    tool_input JSONB,
    user_prompt TEXT,
    cwd TEXT,
    raw_payload JSONB NOT NULL,
    payload_schema_version TEXT NOT NULL DEFAULT '1',
    occurred_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content_tsv tsvector
);

CREATE TABLE IF NOT EXISTS uam.memories (
    id UUID PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    frontmatter JSONB NOT NULL DEFAULT '{}'::jsonb,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL DEFAULT 'learning'
        CHECK (memory_type IN ('fact', 'learning', 'idea')),
    embedding vector(768),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content_tsv tsvector
);

CREATE OR REPLACE FUNCTION uam.set_event_content_tsv() RETURNS trigger AS $$
BEGIN
    NEW.content_tsv := to_tsvector(
        'simple',
        coalesce(NEW.event_name, '') || ' ' ||
        coalesce(NEW.tool_name, '') || ' ' ||
        coalesce(NEW.user_prompt, '') || ' ' ||
        coalesce(NEW.raw_payload::text, '')
    );
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION uam.set_memory_content_tsv() RETURNS trigger AS $$
BEGIN
    NEW.content_tsv := to_tsvector(
        'simple',
        coalesce(NEW.path, '') || ' ' || coalesce(NEW.content, '')
    );
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS uam_events_content_tsv_trigger ON uam.events;
CREATE TRIGGER uam_events_content_tsv_trigger
BEFORE INSERT OR UPDATE ON uam.events
FOR EACH ROW
EXECUTE FUNCTION uam.set_event_content_tsv();

DROP TRIGGER IF EXISTS uam_memories_content_tsv_trigger ON uam.memories;
CREATE TRIGGER uam_memories_content_tsv_trigger
BEFORE INSERT OR UPDATE ON uam.memories
FOR EACH ROW
EXECUTE FUNCTION uam.set_memory_content_tsv();

CREATE TABLE IF NOT EXISTS uam.embeddings (
    id UUID PRIMARY KEY,
    event_id UUID REFERENCES uam.events(id) ON DELETE CASCADE,
    embedding vector(768) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS uam.dream_runs (
    id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    events_processed INT NOT NULL DEFAULT 0,
    memories_updated INT NOT NULL DEFAULT 0,
    watermark TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS uam.search_cache (
    query_hash TEXT PRIMARY KEY,
    results JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ttl_seconds INT NOT NULL
);

CREATE INDEX IF NOT EXISTS uam_events_session_id_idx ON uam.events (session_id);
CREATE INDEX IF NOT EXISTS uam_events_occurred_at_idx ON uam.events (occurred_at);
CREATE INDEX IF NOT EXISTS uam_events_event_name_idx ON uam.events (event_name);
CREATE INDEX IF NOT EXISTS uam_events_client_idx ON uam.events (client);
CREATE INDEX IF NOT EXISTS uam_events_content_tsv_idx ON uam.events USING GIN (content_tsv);
CREATE INDEX IF NOT EXISTS uam_memories_content_tsv_idx ON uam.memories USING GIN (content_tsv);
CREATE INDEX IF NOT EXISTS uam_embeddings_event_id_idx ON uam.embeddings (event_id);
CREATE INDEX IF NOT EXISTS uam_embeddings_embedding_hnsw_idx ON uam.embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS uam_memories_embedding_hnsw_idx ON uam.memories USING hnsw (embedding vector_cosine_ops);
