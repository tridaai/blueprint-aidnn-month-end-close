-- 0004: the pre-close readiness records — expectation
-- manifests and readiness waivers. A manifest is a named
-- controller's statement of what one period's close expects
-- to receive (per source slot, with the delivery version
-- expected where one is stated); a waiver is a named
-- controller's licence to build that period's close
-- short-handed, covering named failing items exactly. Both
-- are append-only governance records in the same idiom as
-- 0001–0003: one JSONB payload per record, columns only for
-- identity, kind, and filtering. They are their own
-- aggregate (not rows on a run or a pack) because they
-- belong to the period's close, not to any one build of it:
-- a manifest is written before the period's run exists, and
-- a waiver is consulted by every build the period attempts
-- until the gap it covers is closed.

CREATE TABLE IF NOT EXISTS readiness_records (
    record_id TEXT PRIMARY KEY,
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    kind TEXT NOT NULL,
    period TEXT NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS readiness_records_kind_idx
    ON readiness_records (kind, period, seq);
