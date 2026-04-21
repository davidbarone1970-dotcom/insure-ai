-- ============================================================================
-- ADR-002 Phase 2: Pipeline Naming Migration
-- ============================================================================
-- Run as TWO separate blocks in Supabase SQL Editor.
-- Block 1 cannot run inside a transaction (Postgres limitation on ALTER TYPE).
-- Block 2 is fully transactional — atomically applies all renames + updates.
--
-- After both blocks succeed, run the 4 verification queries at the end.
-- ============================================================================


-- ============================================================================
-- BLOCK 1 — Enum-Erweiterung (NO TRANSACTION)
-- ============================================================================
-- Run this FIRST, on its own. Postgres requires ALTER TYPE ADD VALUE to be
-- outside any transaction block.

ALTER TYPE pipeline_type ADD VALUE IF NOT EXISTS 'claim';

-- Quick verification before Block 2:
-- SELECT enum_range(NULL::pipeline_type);
-- Expected: must contain 'claim' alongside the existing 'claims', 'lead', 'retention', 'offer'.


-- ============================================================================
-- BLOCK 2 — Renames + Pipeline-Wert-Migration (TRANSACTIONAL)
-- ============================================================================
-- Run this AFTER Block 1 succeeded. Single atomic transaction.

BEGIN;

-- ── 1. Tabellen-Rename ─────────────────────────────────────────────────────
ALTER TABLE retention_events RENAME TO retentions;

-- ── 2. Spalten-Renames ─────────────────────────────────────────────────────
ALTER TABLE retentions RENAME COLUMN retention_event_id TO retention_id;
ALTER TABLE offers RENAME COLUMN offer_trigger_id TO offer_id;

-- ── 3. Pipeline-Wert-Migration für Claims (ADR D3: Singular) ──────────────
UPDATE pipeline_events SET pipeline = 'claim' WHERE pipeline = 'claims';

COMMIT;


-- ============================================================================
-- VERIFIKATION (run each query separately)
-- ============================================================================
-- All four must return the expected results before declaring Phase 2 successful.


-- ── Query V1: Tabellen-Namen ──────────────────────────────────────────────
-- Erwartet: claims, leads, offers, pipeline_events, retentions
-- KEIN retention_events mehr.

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;


-- ── Query V2: Spalte retention_id ─────────────────────────────────────────
-- Erwartet: 1 Zeile mit retention_id
-- KEIN retention_event_id.

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'retentions'
  AND column_name LIKE '%retention%';


-- ── Query V3: Spalte offer_id ─────────────────────────────────────────────
-- Erwartet: offer_id (varchar, unique)
-- KEIN offer_trigger_id.

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'offers'
  AND column_name LIKE 'offer%';


-- ── Query V4: Pipeline-Werte konsistent Singular ──────────────────────────
-- Erwartet: claim, lead, offer, retention
-- KEIN claims (Plural) mehr.

SELECT DISTINCT pipeline, COUNT(*) AS cnt
FROM pipeline_events
GROUP BY pipeline
ORDER BY pipeline;


-- ============================================================================
-- ROLLBACK (only if a verification fails)
-- ============================================================================
-- Run as a single atomic transaction. Reverses Block 2.
-- Block 1 (ALTER TYPE ADD VALUE) is NOT reversible in Postgres — the 'claim'
-- value remains in the enum but unused. Harmless.

-- BEGIN;
-- ALTER TABLE retentions RENAME TO retention_events;
-- ALTER TABLE retention_events RENAME COLUMN retention_id TO retention_event_id;
-- ALTER TABLE offers RENAME COLUMN offer_id TO offer_trigger_id;
-- UPDATE pipeline_events SET pipeline = 'claims' WHERE pipeline = 'claim';
-- COMMIT;
