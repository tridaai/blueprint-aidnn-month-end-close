-- 0001: the close store — source batches, close runs, board packs.
-- Payloads are the full records as JSONB (batches carry their
-- journals/extracts; runs carry their checklist state; packs
-- carry figures, variances, version stamps, and the sign-off);
-- the columns exist for identity, ordering, and filtering.
-- `seq` preserves insertion order across re-saves. Batches are
-- append-only by discipline: a superseding batch is a new row.

CREATE TABLE IF NOT EXISTS source_batches (
    batch_id TEXT PRIMARY KEY,
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    kind TEXT NOT NULL,
    entity_id TEXT,
    version INT NOT NULL DEFAULT 1,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS source_batches_slot_idx
    ON source_batches (entity_id, kind, version);

CREATE TABLE IF NOT EXISTS close_runs (
    run_id TEXT PRIMARY KEY,
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    period TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'COLLECTING',
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS close_runs_period_idx ON close_runs (period, seq);

CREATE TABLE IF NOT EXISTS board_packs (
    pack_id TEXT PRIMARY KEY,
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    run_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'BLOCKED',
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS board_packs_run_idx ON board_packs (run_id, seq);
