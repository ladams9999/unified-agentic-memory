ALTER TABLE uam.memories
    ADD COLUMN IF NOT EXISTS memory_type TEXT NOT NULL DEFAULT 'learning'
        CHECK (memory_type IN ('fact', 'learning', 'idea'));
