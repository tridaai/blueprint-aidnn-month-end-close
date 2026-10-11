-- 0002: the audit evidence bundle index. One row per generated
-- bundle: the bundle bytes themselves live in the object store
-- (evidence/{period}/{pack_id}/evidence-v1.json + .txt); this
-- table is the record that names the keys, carries the digest
-- the stored bytes are checked against, and remembers when
-- generation happened. The payload is the full record as JSONB,
-- in the same idiom as 0001's tables.

CREATE TABLE IF NOT EXISTS evidence_bundles (
    bundle_id TEXT PRIMARY KEY,
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    pack_id TEXT NOT NULL,
    period TEXT NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS evidence_bundles_pack_idx
    ON evidence_bundles (pack_id, seq);
