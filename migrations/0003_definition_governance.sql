-- 0003: the definition-governance records — dry-runs and
-- activations. A dry-run is the computed impact of a candidate
-- definition-pack version over a signed period; an activation
-- is the named act that makes a version govern future periods.
-- Both are append-only governance records in the same idiom as
-- 0001/0002: one JSONB payload per record, columns only for
-- identity, kind, and filtering. They are their own aggregate
-- (not rows on a pack or a run) because they belong to the
-- deployment's definition registry: an activation is written
-- before the periods it governs have runs at all.

CREATE TABLE IF NOT EXISTS definition_governance (
    record_id TEXT PRIMARY KEY,
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    kind TEXT NOT NULL,
    pack_id TEXT NOT NULL,
    version TEXT NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS definition_governance_kind_idx
    ON definition_governance (kind, pack_id, seq);
