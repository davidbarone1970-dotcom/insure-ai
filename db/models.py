"""
INSURE.AI — SQLAlchemy ORM Models
Maps to schema.sql tables.

ADR-002 Phase 2 changes:
- Class RetentionEvent renamed to Retention
- Table 'retention_events' renamed to 'retentions'
- Column 'retention_event_id' renamed to 'retention_id'
- Column 'offer_trigger_id' renamed to 'offer_id' (in Offer model)
- PIPELINE_ENUM: canonical value is 'claim' (singular).
  Legacy 'claims' value remains in the Postgres enum (cannot be dropped) but
  is no longer written from Python.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Numeric, Boolean, DateTime,
    SmallInteger, Enum as PgEnum, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base

# ── SHARED ENUM STRINGS ──────────────────────────────────────────────────────

REVIEW_DECISION_ENUM = PgEnum(
    'approved', 'rejected', 'escalated', 'info_requested', 'pending',
    name='review_decision', create_type=False
)

ROUTE_ENUM = PgEnum(
    'sales', 'nurturing', 'automation',
    'auto_process', 'manual_review', 'escalation', 'siu_referral',
    'call_task', 'generate_offer', 'automated_campaign', 'no_action',
    'automated_offer', 'sales_handoff', 'nurturing_sequence',
    name='route_type', create_type=False
)

PRIORITY_ENUM = PgEnum('low', 'medium', 'high', 'critical', name='priority_type', create_type=False)

# ADR-002 D3: pipeline values are SINGULAR.
# Postgres enum still contains the legacy 'claims' value (cannot be dropped),
# but Python writes only the canonical singular forms below.
PIPELINE_ENUM = PgEnum('lead', 'claim', 'retention', 'offer', name='pipeline_type', create_type=False)


# ── PIPELINE EVENTS (audit log) ──────────────────────────────────────────────

class PipelineEvent(Base):
    __tablename__ = "pipeline_events"

    id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline:    Mapped[str]       = mapped_column(PIPELINE_ENUM, nullable=False)
    entity_id:   Mapped[str]       = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str]       = mapped_column(String(32), nullable=False)
    event_type:  Mapped[str]       = mapped_column(String(64), nullable=False)
    payload:     Mapped[dict]      = mapped_column(JSONB, nullable=False, default=dict)
    created_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── CLAIMS ───────────────────────────────────────────────────────────────────

class Claim(Base):
    __tablename__ = "claims"

    id:                    Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id:              Mapped[str]              = mapped_column(String(64), unique=True, nullable=False)
    customer_id:           Mapped[str]              = mapped_column(String(64), nullable=False)
    policy_id:             Mapped[str]              = mapped_column(String(64), nullable=False)
    claim_type:            Mapped[str]              = mapped_column(String(64), nullable=False)
    claim_amount:          Mapped[float]            = mapped_column(Numeric(12, 2), nullable=False)
    currency:              Mapped[str]              = mapped_column(String(3), nullable=False, default='CHF')
    description:           Mapped[Optional[str]]    = mapped_column(Text)
    submission_channel:    Mapped[Optional[str]]    = mapped_column(String(32))

    # Agent output
    classification:        Mapped[Optional[str]]    = mapped_column(String(32))
    priority:              Mapped[Optional[str]]    = mapped_column(PRIORITY_ENUM)
    confidence:            Mapped[Optional[float]]  = mapped_column(Numeric(4, 3))
    fraud_score:           Mapped[Optional[float]]  = mapped_column(Numeric(4, 3))
    estimated_payout:      Mapped[Optional[float]]  = mapped_column(Numeric(12, 2))
    agent_reasoning:       Mapped[Optional[str]]    = mapped_column(Text)
    flags:                 Mapped[dict]             = mapped_column(JSONB, nullable=False, default=list)

    # Orchestrator
    recommended_route:     Mapped[Optional[str]]    = mapped_column(String(32))
    final_route:           Mapped[Optional[str]]    = mapped_column(ROUTE_ENUM)
    orchestrator_override: Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    override_reason:       Mapped[Optional[str]]    = mapped_column(Text)

    # Review
    review_decision:       Mapped[str]              = mapped_column(REVIEW_DECISION_ENUM, nullable=False, default='pending')
    reviewer_id:           Mapped[Optional[str]]    = mapped_column(String(64))
    reviewer_note:         Mapped[Optional[str]]    = mapped_column(Text)
    reviewed_at:           Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Timestamps
    received_at:           Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())
    agent_processed_at:    Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    routed_at:             Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_at:           Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Snapshot
    customer_snapshot:     Mapped[dict]             = mapped_column(JSONB, nullable=False, default=dict)


# ── RETENTION ────────────────────────────────────────────────────────────────
# ADR-002 D1: table renamed retention_events -> retentions
# ADR-002 D2: column renamed retention_event_id -> retention_id

class Retention(Base):
    __tablename__ = "retentions"

    id:                    Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id:           Mapped[str]              = mapped_column(String(64), nullable=False)
    retention_id:          Mapped[Optional[str]]    = mapped_column(String(64), unique=True, nullable=True)
    trigger_type:          Mapped[str]              = mapped_column(String(64), nullable=False)
    trigger_detail:        Mapped[Optional[str]]    = mapped_column(Text)

    # Agent output
    churn_score:           Mapped[Optional[float]]  = mapped_column(Numeric(4, 3))
    churn_risk_level:      Mapped[Optional[str]]    = mapped_column(String(16))
    confidence:            Mapped[Optional[float]]  = mapped_column(Numeric(4, 3))
    offer_type:            Mapped[Optional[str]]    = mapped_column(String(64))
    offer_value_suggestion:Mapped[Optional[str]]    = mapped_column(Text)
    campaign_segment:      Mapped[Optional[str]]    = mapped_column(String(128))
    priority_score:        Mapped[Optional[int]]    = mapped_column(SmallInteger)
    agent_reasoning:       Mapped[Optional[str]]    = mapped_column(Text)
    flags:                 Mapped[dict]             = mapped_column(JSONB, nullable=False, default=list)

    # Orchestrator
    recommended_route:     Mapped[Optional[str]]    = mapped_column(String(32))
    final_route:           Mapped[Optional[str]]    = mapped_column(ROUTE_ENUM)
    orchestrator_override: Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    override_reason:       Mapped[Optional[str]]    = mapped_column(Text)

    # Outcome
    action_taken:          Mapped[Optional[str]]    = mapped_column(String(64))
    outcome:               Mapped[Optional[str]]    = mapped_column(String(32))
    outcome_recorded_at:   Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Review
    review_decision:       Mapped[str]              = mapped_column(REVIEW_DECISION_ENUM, nullable=False, default='pending')
    reviewer_id:           Mapped[Optional[str]]    = mapped_column(String(64))
    reviewer_note:         Mapped[Optional[str]]    = mapped_column(Text)
    reviewed_at:           Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Timestamps
    triggered_at:          Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())
    agent_processed_at:    Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    routed_at:             Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    customer_snapshot:     Mapped[dict]             = mapped_column(JSONB, nullable=False, default=dict)


# ── OFFERS ───────────────────────────────────────────────────────────────────
# ADR-002 D2: column renamed offer_trigger_id -> offer_id

class Offer(Base):
    __tablename__ = "offers"

    id:                       Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id:                 Mapped[str]              = mapped_column(String(64), unique=True, nullable=False)
    customer_id:              Mapped[str]              = mapped_column(String(64), nullable=False)
    trigger_type:             Mapped[str]              = mapped_column(String(64), nullable=False)
    source_pipeline:          Mapped[str]              = mapped_column(String(32), nullable=False, default='direct')

    # Agent output
    recommended_product:      Mapped[Optional[str]]    = mapped_column(String(64))
    product_display_name:     Mapped[Optional[str]]    = mapped_column(String(128))
    offer_rationale:          Mapped[Optional[str]]    = mapped_column(Text)
    estimated_annual_premium: Mapped[Optional[str]]    = mapped_column(String(64))
    cross_sell_score:         Mapped[Optional[float]]  = mapped_column(Numeric(4, 3))
    confidence:               Mapped[Optional[float]]  = mapped_column(Numeric(4, 3))
    personalization_angle:    Mapped[Optional[str]]    = mapped_column(Text)
    channel_recommendation:   Mapped[Optional[str]]    = mapped_column(String(32))
    urgency:                  Mapped[Optional[str]]    = mapped_column(String(16))
    agent_reasoning:          Mapped[Optional[str]]    = mapped_column(Text)
    flags:                    Mapped[dict]             = mapped_column(JSONB, nullable=False, default=list)

    # Orchestrator
    recommended_route:        Mapped[Optional[str]]    = mapped_column(String(32))
    final_route:              Mapped[Optional[str]]    = mapped_column(ROUTE_ENUM)
    orchestrator_override:    Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    override_reason:          Mapped[Optional[str]]    = mapped_column(Text)

    # Review
    review_decision:          Mapped[str]              = mapped_column(REVIEW_DECISION_ENUM, nullable=False, default='pending')
    reviewer_id:              Mapped[Optional[str]]    = mapped_column(String(64))
    reviewer_note:            Mapped[Optional[str]]    = mapped_column(Text)
    reviewed_at:              Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Outcome
    offer_sent_at:            Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    offer_accepted_at:        Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    offer_rejected_at:        Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    offer_expired_at:         Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Timestamps
    triggered_at:             Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())
    agent_processed_at:       Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    routed_at:                Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    customer_snapshot:        Mapped[dict]             = mapped_column(JSONB, nullable=False, default=dict)


# ── LEADS ────────────────────────────────────────────────────────────────────

class Lead(Base):
    __tablename__ = "leads"

    id:                    Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id:               Mapped[str]              = mapped_column(String(64), unique=True, nullable=False)
    customer_id:           Mapped[str]              = mapped_column(String(64), nullable=False)
    lead_source:           Mapped[Optional[str]]    = mapped_column(String(64))
    segment:               Mapped[Optional[str]]    = mapped_column(String(64))
    product_interest:      Mapped[Optional[str]]    = mapped_column(String(128))
    submission_channel:    Mapped[Optional[str]]    = mapped_column(String(32))

    # Agent output
    lead_score:            Mapped[Optional[int]]    = mapped_column(SmallInteger)
    priority:              Mapped[Optional[str]]    = mapped_column(PRIORITY_ENUM)
    confidence:            Mapped[Optional[float]]  = mapped_column(Numeric(4, 3))
    qualification:         Mapped[Optional[str]]    = mapped_column(String(32))
    estimated_annual_value:Mapped[Optional[float]]  = mapped_column(Numeric(12, 2))
    competitor_offer:      Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    competitor_name:       Mapped[Optional[str]]    = mapped_column(String(64))
    agent_reasoning:       Mapped[Optional[str]]    = mapped_column(Text)
    flags:                 Mapped[dict]             = mapped_column(JSONB, nullable=False, default=list)

    # Orchestrator
    recommended_route:     Mapped[Optional[str]]    = mapped_column(String(32))
    final_route:           Mapped[Optional[str]]    = mapped_column(ROUTE_ENUM)
    orchestrator_override: Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    override_reason:       Mapped[Optional[str]]    = mapped_column(Text)

    # Review
    review_decision:       Mapped[str]              = mapped_column(REVIEW_DECISION_ENUM, nullable=False, default='pending')
    reviewer_id:           Mapped[Optional[str]]    = mapped_column(String(64))
    reviewer_note:         Mapped[Optional[str]]    = mapped_column(Text)
    reviewed_at:           Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Outcome
    converted:             Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    converted_at:          Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    conversion_value:      Mapped[Optional[float]]  = mapped_column(Numeric(12, 2))

    # Timestamps
    received_at:           Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())
    agent_processed_at:    Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    routed_at:             Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    customer_snapshot:     Mapped[dict]             = mapped_column(JSONB, nullable=False, default=dict)
