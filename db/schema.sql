-- ============================================================
-- INSURE.AI — PostgreSQL Schema (Supabase-compatible)
-- Version: 1.1.0 — Consolidated
--   • Leads pipeline integrated inline (no more extension blocks)
--   • Deduplicated hitl_queue VIEW and kpi_today MATERIALIZED VIEW
--   • Idempotent: safe to re-run on an existing DB
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ── ENUMS ─────────────────────────────────────────────────────────────────────

DO $$ BEGIN
  CREATE TYPE pipeline_type AS ENUM ('lead', 'claims', 'retention', 'offer');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE route_type AS ENUM (
    'sales', 'nurturing', 'automation',
    'auto_process', 'manual_review', 'escalation', 'siu_referral',
    'call_task', 'generate_offer', 'automated_campaign', 'no_action',
    'automated_offer', 'sales_handoff', 'nurturing_sequence'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE priority_type AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE review_decision AS ENUM (
    'approved', 'rejected', 'escalated', 'info_requested', 'pending'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── PIPELINE EVENTS (audit log) ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pipeline_events (
  id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
  pipeline    pipeline_type NOT NULL,
  entity_id   VARCHAR(64) NOT NULL,
  entity_type VARCHAR(32) NOT NULL,
  event_type  VARCHAR(64) NOT NULL,
  payload     JSONB       NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_pipeline    ON pipeline_events (pipeline);
CREATE INDEX IF NOT EXISTS idx_events_entity_id   ON pipeline_events (entity_id);
CREATE INDEX IF NOT EXISTS idx_events_created_at  ON pipeline_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_payload_gin ON pipeline_events USING GIN (payload);

-- ── CLAIMS ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS claims (
  id                    UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
  claim_id              VARCHAR(64)    UNIQUE NOT NULL,
  customer_id           VARCHAR(64)    NOT NULL,
  policy_id             VARCHAR(64)    NOT NULL,
  claim_type            VARCHAR(64)    NOT NULL,
  claim_amount          NUMERIC(12,2)  NOT NULL,
  currency              CHAR(3)        NOT NULL DEFAULT 'CHF',
  description           TEXT,
  submission_channel    VARCHAR(32),
  classification        VARCHAR(32),
  priority              priority_type,
  confidence            NUMERIC(4,3),
  fraud_score           NUMERIC(4,3),
  estimated_payout      NUMERIC(12,2),
  agent_reasoning       TEXT,
  flags                 JSONB          NOT NULL DEFAULT '[]',
  recommended_route     VARCHAR(32),
  final_route           route_type,
  orchestrator_override BOOLEAN        NOT NULL DEFAULT FALSE,
  override_reason       TEXT,
  review_decision       review_decision NOT NULL DEFAULT 'pending',
  reviewer_id           VARCHAR(64),
  reviewer_note         TEXT,
  reviewed_at           TIMESTAMPTZ,
  received_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
  agent_processed_at    TIMESTAMPTZ,
  routed_at             TIMESTAMPTZ,
  resolved_at           TIMESTAMPTZ,
  customer_snapshot     JSONB          NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_claims_customer_id ON claims (customer_id);
CREATE INDEX IF NOT EXISTS idx_claims_final_route ON claims (final_route);
CREATE INDEX IF NOT EXISTS idx_claims_priority    ON claims (priority);
CREATE INDEX IF NOT EXISTS idx_claims_received_at ON claims (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_claims_fraud_score ON claims (fraud_score DESC)
  WHERE fraud_score > 0.5;

-- ── RETENTION EVENTS ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS retention_events (
  id                     UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
  retention_event_id     VARCHAR(64)    UNIQUE,
  customer_id            VARCHAR(64)    NOT NULL,
  trigger_type           VARCHAR(64)    NOT NULL,
  trigger_detail         TEXT,
  churn_score            NUMERIC(4,3),
  churn_risk_level       VARCHAR(16),
  confidence             NUMERIC(4,3),
  offer_type             VARCHAR(64),
  offer_value_suggestion TEXT,
  campaign_segment       VARCHAR(128),
  priority_score         SMALLINT,
  agent_reasoning        TEXT,
  flags                  JSONB          NOT NULL DEFAULT '[]',
  recommended_route      VARCHAR(32),
  final_route            route_type,
  orchestrator_override  BOOLEAN        NOT NULL DEFAULT FALSE,
  override_reason        TEXT,
  action_taken           VARCHAR(64),
  outcome                VARCHAR(32),
  outcome_recorded_at    TIMESTAMPTZ,
  review_decision        review_decision NOT NULL DEFAULT 'pending',
  reviewer_id            VARCHAR(64),
  reviewer_note          TEXT,
  reviewed_at            TIMESTAMPTZ,
  triggered_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
  agent_processed_at     TIMESTAMPTZ,
  routed_at              TIMESTAMPTZ,
  customer_snapshot      JSONB          NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_retention_customer_id  ON retention_events (customer_id);
CREATE INDEX IF NOT EXISTS idx_retention_churn_score  ON retention_events (churn_score DESC);
CREATE INDEX IF NOT EXISTS idx_retention_final_route  ON retention_events (final_route);
CREATE INDEX IF NOT EXISTS idx_retention_triggered_at ON retention_events (triggered_at DESC);

-- ── OFFERS ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS offers (
  id                       UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
  offer_trigger_id         VARCHAR(64)    UNIQUE NOT NULL,
  customer_id              VARCHAR(64)    NOT NULL,
  trigger_type             VARCHAR(64)    NOT NULL,
  source_pipeline          VARCHAR(32)    NOT NULL DEFAULT 'direct',
  recommended_product      VARCHAR(64),
  product_display_name     VARCHAR(128),
  offer_rationale          TEXT,
  estimated_annual_premium VARCHAR(64),
  cross_sell_score         NUMERIC(4,3),
  confidence               NUMERIC(4,3),
  personalization_angle    TEXT,
  channel_recommendation   VARCHAR(32),
  urgency                  VARCHAR(16),
  agent_reasoning          TEXT,
  flags                    JSONB          NOT NULL DEFAULT '[]',
  recommended_route        VARCHAR(32),
  final_route              route_type,
  orchestrator_override    BOOLEAN        NOT NULL DEFAULT FALSE,
  override_reason          TEXT,
  review_decision          review_decision NOT NULL DEFAULT 'pending',
  reviewer_id              VARCHAR(64),
  reviewer_note            TEXT,
  reviewed_at              TIMESTAMPTZ,
  offer_sent_at            TIMESTAMPTZ,
  offer_accepted_at        TIMESTAMPTZ,
  offer_rejected_at        TIMESTAMPTZ,
  offer_expired_at         TIMESTAMPTZ,
  triggered_at             TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
  agent_processed_at       TIMESTAMPTZ,
  routed_at                TIMESTAMPTZ,
  customer_snapshot        JSONB          NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_offers_customer_id      ON offers (customer_id);
CREATE INDEX IF NOT EXISTS idx_offers_final_route      ON offers (final_route);
CREATE INDEX IF NOT EXISTS idx_offers_recommended_prod ON offers (recommended_product);
CREATE INDEX IF NOT EXISTS idx_offers_triggered_at     ON offers (triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_offers_cross_sell_score ON offers (cross_sell_score DESC);

-- ── LEADS ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS leads (
  id                     UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id                VARCHAR(64)    UNIQUE NOT NULL,
  customer_id            VARCHAR(64)    NOT NULL,
  lead_source            VARCHAR(64),
  segment                VARCHAR(64),
  product_interest       VARCHAR(128),
  submission_channel     VARCHAR(32),
  lead_score             SMALLINT,
  priority               priority_type,
  confidence             NUMERIC(4,3),
  qualification          VARCHAR(32),
  estimated_annual_value NUMERIC(12,2),
  competitor_offer       BOOLEAN        NOT NULL DEFAULT FALSE,
  competitor_name        VARCHAR(64),
  agent_reasoning        TEXT,
  flags                  JSONB          NOT NULL DEFAULT '[]',
  recommended_route      VARCHAR(32),
  final_route            route_type,
  orchestrator_override  BOOLEAN        NOT NULL DEFAULT FALSE,
  override_reason        TEXT,
  review_decision        review_decision NOT NULL DEFAULT 'pending',
  reviewer_id            VARCHAR(64),
  reviewer_note          TEXT,
  reviewed_at            TIMESTAMPTZ,
  converted              BOOLEAN        NOT NULL DEFAULT FALSE,
  converted_at           TIMESTAMPTZ,
  conversion_value       NUMERIC(12,2),
  received_at            TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
  agent_processed_at     TIMESTAMPTZ,
  routed_at              TIMESTAMPTZ,
  customer_snapshot      JSONB          NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_leads_customer_id ON leads (customer_id);
CREATE INDEX IF NOT EXISTS idx_leads_final_route ON leads (final_route);
CREATE INDEX IF NOT EXISTS idx_leads_lead_score  ON leads (lead_score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_received_at ON leads (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_segment     ON leads (segment);
CREATE INDEX IF NOT EXISTS idx_leads_high_value  ON leads (estimated_annual_value DESC)
  WHERE estimated_annual_value IS NOT NULL;

-- ── HITL QUEUE VIEW (all four pipelines, single definition) ───────────────────

DROP VIEW IF EXISTS hitl_queue;

CREATE VIEW hitl_queue AS
SELECT *
FROM (
  SELECT
    'claim'               AS entity_type,
    id,
    claim_id              AS entity_id,
    customer_id,
    priority::TEXT        AS urgency,
    classification        AS subtype,
    confidence,
    fraud_score           AS risk_score,
    final_route::TEXT     AS route,
    agent_reasoning       AS reasoning,
    flags,
    received_at           AS queued_at,
    reviewed_at,
    review_decision::TEXT AS decision
  FROM claims
  WHERE review_decision = 'pending'
    AND final_route IN ('manual_review', 'escalation', 'siu_referral')

  UNION ALL

  SELECT
    'retention'           AS entity_type,
    id,
    customer_id           AS entity_id,
    customer_id,
    churn_risk_level      AS urgency,
    trigger_type          AS subtype,
    confidence,
    churn_score           AS risk_score,
    final_route::TEXT     AS route,
    agent_reasoning       AS reasoning,
    flags,
    triggered_at          AS queued_at,
    reviewed_at,
    review_decision::TEXT AS decision
  FROM retention_events
  WHERE review_decision = 'pending'
    AND final_route IN ('call_task')

  UNION ALL

  SELECT
    'offer'               AS entity_type,
    id,
    offer_trigger_id      AS entity_id,
    customer_id,
    urgency,
    recommended_product   AS subtype,
    confidence,
    cross_sell_score      AS risk_score,
    final_route::TEXT     AS route,
    agent_reasoning       AS reasoning,
    flags,
    triggered_at          AS queued_at,
    reviewed_at,
    review_decision::TEXT AS decision
  FROM offers
  WHERE review_decision = 'pending'
    AND final_route IN ('sales_handoff')

  UNION ALL

  SELECT
    'lead'                AS entity_type,
    id,
    lead_id               AS entity_id,
    customer_id,
    priority::TEXT        AS urgency,
    product_interest      AS subtype,
    confidence,
    lead_score::NUMERIC   AS risk_score,
    final_route::TEXT     AS route,
    agent_reasoning       AS reasoning,
    flags,
    received_at           AS queued_at,
    reviewed_at,
    review_decision::TEXT AS decision
  FROM leads
  WHERE review_decision = 'pending'
    AND final_route IN ('sales', 'nurturing')
    AND qualification = 'borderline'
) q
ORDER BY
  CASE urgency
    WHEN 'critical' THEN 0
    WHEN 'high'     THEN 1
    WHEN 'medium'   THEN 2
    ELSE 3
  END,
  queued_at ASC;

-- ── KPI MATERIALIZED VIEW (all four pipelines, single definition) ─────────────

DROP MATERIALIZED VIEW IF EXISTS kpi_today;

CREATE MATERIALIZED VIEW kpi_today AS
  WITH date_filter AS (SELECT NOW()::DATE AS today)

  SELECT
    'leads' AS pipeline,
    COUNT(*) AS total,
    SUM(CASE WHEN final_route = 'automation' THEN 1 ELSE 0 END) AS automated,
    SUM(CASE WHEN final_route = 'sales'      THEN 1 ELSE 0 END) AS manual,
    SUM(CASE WHEN converted = TRUE           THEN 1 ELSE 0 END) AS escalated,
    AVG(confidence) AS avg_confidence,
    AVG(lead_score) AS avg_fraud_score
  FROM leads, date_filter
  WHERE received_at::DATE = today

  UNION ALL

  SELECT
    'claims' AS pipeline,
    COUNT(*),
    SUM(CASE WHEN final_route = 'auto_process'  THEN 1 ELSE 0 END),
    SUM(CASE WHEN final_route = 'manual_review' THEN 1 ELSE 0 END),
    SUM(CASE WHEN final_route = 'siu_referral'  THEN 1 ELSE 0 END),
    AVG(confidence),
    AVG(fraud_score)
  FROM claims, date_filter
  WHERE received_at::DATE = today

  UNION ALL

  SELECT
    'retention' AS pipeline,
    COUNT(*),
    SUM(CASE WHEN final_route = 'automated_campaign' THEN 1 ELSE 0 END),
    SUM(CASE WHEN final_route = 'call_task'          THEN 1 ELSE 0 END),
    SUM(CASE WHEN final_route = 'no_action'          THEN 1 ELSE 0 END),
    AVG(confidence),
    AVG(churn_score)
  FROM retention_events, date_filter
  WHERE triggered_at::DATE = today

  UNION ALL

  SELECT
    'offer' AS pipeline,
    COUNT(*),
    SUM(CASE WHEN final_route = 'automated_offer'    THEN 1 ELSE 0 END),
    SUM(CASE WHEN final_route = 'sales_handoff'      THEN 1 ELSE 0 END),
    SUM(CASE WHEN final_route = 'nurturing_sequence' THEN 1 ELSE 0 END),
    AVG(confidence),
    AVG(cross_sell_score)
  FROM offers, date_filter
  WHERE triggered_at::DATE = today;

CREATE UNIQUE INDEX IF NOT EXISTS idx_kpi_today_pipeline ON kpi_today (pipeline);