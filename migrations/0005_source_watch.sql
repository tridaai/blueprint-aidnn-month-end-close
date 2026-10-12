-- 0005: the post-sign-off source watch records — a named
-- controller's acknowledgements of source movements behind
-- signed packs. An acknowledgement covers exactly one
-- movement (one period, one source slot, one chain tip) and
-- one stated disposition — a restatement planned, or no
-- action, with the reason. The records are their own
-- aggregate in the same idiom as 0001–0004: one JSONB
-- payload per record, columns only for identity, kind, and
-- filtering. They belong to no pack: the pack they answer
-- for is signed history and is never written to, and the
-- watch that reads them is a projection over the signed
-- packs' stamps and the supersession chains, computed on
-- read — the acknowledgement is the only state it keeps.

CREATE TABLE IF NOT EXISTS source_watch_records (
    record_id TEXT PRIMARY KEY,
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    kind TEXT NOT NULL,
    period TEXT NOT NULL,
    slot TEXT NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS source_watch_records_kind_idx
    ON source_watch_records (kind, period, seq);
