"""
INSURE.AI — Offer Agent
FastAPI endpoint: POST /agent/offer
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
import anthropic
import json
import logging
from datetime import datetime

from db.database import db_session
from db.repositories import OfferRepository, EventRepository

logger = logging.getLogger(__name__)

# ── MODELS ────────────────────────────────────────────────────────────────

class OfferInput(BaseModel):
    offer_trigger_id: str
    customer_id: str
    trigger_type: str                # "renewal", "lifecycle_event", "segment_campaign",
                                     # "cross_sell_signal", "upsell_signal", "retention_linked"
    customer_name: Optional[str] = None
    segment: Optional[str] = None
    age_group: Optional[str] = None
    customer_since_years: Optional[int] = None
    annual_premium: Optional[float] = None
    customer_ltv: Optional[float] = None
    existing_products: List[str] = []
    recent_life_events: List[str] = []
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    annual_revenue: Optional[float] = None
    offers_sent_last_90_days: List[str] = []
    available_products: List[str] = [
        "hausrat", "haftpflicht", "leben", "unfall", "rechtsschutz",
        "cyber_privat", "cyber_business", "kfz_haftpflicht", "vollkasko",
        "reise", "krankentaggeld", "gebaeude", "betrieb"
    ]


class OfferResult(BaseModel):
    offer_trigger_id: str
    customer_id: str
    recommended_product: str
    product_display_name: str
    offer_rationale: str
    estimated_annual_premium: Optional[str]
    cross_sell_score: float
    confidence: float
    recommended_route: str           # "automated_offer", "sales_handoff", "nurturing_sequence"
    personalization_angle: str
    channel_recommendation: str
    urgency: str
    flags: List[dict]
    reasoning: str
    suggested_next_steps: List[str]
    processed_at: str

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────

OFFER_SYSTEM_PROMPT = """You are the Offer Agent for INSURE.AI, an intelligent insurance automation platform.

Your job is to analyze customer context and produce a personalized product recommendation as structured JSON.

PRODUCT KNOWLEDGE:
- hausrat: Home contents insurance. Target: renters/owners. Cross-sell: haftpflicht, rechtsschutz
- haftpflicht: Personal liability. Target: everyone. Often bundled with hausrat
- leben: Life insurance. Target: families, mortgages, 30-55 age. High value
- unfall: Accident insurance. Target: active people, families with children
- rechtsschutz: Legal protection. Target: employees, families, homeowners. Cross-sell with hausrat
- cyber_privat: Personal cyber insurance. Target: digital-native individuals
- cyber_business: Business cyber insurance. Target: SME in tech/services. HIGH priority gap
- kfz_haftpflicht: Car liability (mandatory). Target: vehicle owners
- vollkasko: Comprehensive car insurance. Target: new/expensive vehicles
- reise: Travel insurance. Target: frequent travelers, families
- krankentaggeld: Daily sickness allowance. Target: self-employed, SME without group coverage
- gebaeude: Building insurance. Target: property owners
- betrieb: Business operations insurance. Target: SME all sectors

CROSS-SELL SCORE FACTORS (increase score):
- Clear coverage gap (product not in existing_products): +0.30
- Life event match (e.g. new_child → unfall, leben): +0.20
- Segment/industry match (e.g. IT company → cyber_business): +0.25
- High engagement signal: +0.10
- Renewal upcoming (bundle opportunity): +0.15
- Long-term customer (loyalty angle available): +0.10

SCORE DECREASE:
- Product already offered in last 90 days: -0.40 (choose different product)
- Segment mismatch: -0.20

ROUTING RULES:
- "automated_offer": cross_sell_score >= 0.65, offer value < CHF 1500/year, no complex underwriting
- "sales_handoff": cross_sell_score >= 0.70 AND (annual_premium > CHF 1500 OR complex product)
- "nurturing_sequence": cross_sell_score 0.40–0.64, not yet ready to buy

URGENCY:
- "high": life event + clear gap, OR renewal due < 60 days
- "medium": clear gap, no urgency signal
- "low": nice-to-have, long nurturing window

Always respond with valid JSON only. No markdown, no preamble.
Pick the SINGLE best product recommendation. Do not list multiple.

JSON Schema:
{
  "recommended_product": "product_key",
  "product_display_name": "Human readable name",
  "offer_rationale": "One sentence why this product now",
  "estimated_annual_premium": "CHF X – Y",
  "cross_sell_score": 0.00,
  "confidence": 0.00,
  "recommended_route": "automated_offer|sales_handoff|nurturing_sequence",
  "personalization_angle": "Key message for the customer",
  "channel_recommendation": "email|call|portal_notification|broker",
  "urgency": "low|medium|high",
  "flags": [
    {"severity": "danger|warn|info", "label": "...", "detail": "..."}
  ],
  "reasoning": "...",
  "suggested_next_steps": ["...", "..."]
}"""

# ── AGENT LOGIC ───────────────────────────────────────────────────────────

client = anthropic.Anthropic()

def build_offer_prompt(data: OfferInput) -> str:
    parts = [
        f"TRIGGER ID: {data.offer_trigger_id}",
        f"Customer: {data.customer_id} | Trigger: {data.trigger_type}",
    ]
    if data.customer_name:
        parts.append(f"Name: {data.customer_name}")
    parts.append(f"Segment: {data.segment or 'unknown'} | Age group: {data.age_group or 'unknown'}")
    if data.customer_since_years is not None:
        parts.append(f"Customer since: {data.customer_since_years} years")
    if data.annual_premium is not None:
        parts.append(f"Current annual premium: CHF {data.annual_premium:,.0f}")
    if data.customer_ltv is not None:
        parts.append(f"LTV estimate: CHF {data.customer_ltv:,.0f}")
    parts.append(f"Existing products: {', '.join(data.existing_products) if data.existing_products else 'none on record'}")
    if data.recent_life_events:
        parts.append(f"Recent life events: {', '.join(data.recent_life_events)}")
    if data.industry:
        parts.append(f"Industry: {data.industry}" +
                     (f" | Employees: {data.employee_count}" if data.employee_count else "") +
                     (f" | Revenue: CHF {data.annual_revenue:,.0f}" if data.annual_revenue else ""))
    if data.offers_sent_last_90_days:
        parts.append(f"Already offered (last 90 days): {', '.join(data.offers_sent_last_90_days)}")
    parts.append(f"Available products to consider: {', '.join(data.available_products)}")
    return "\n".join(parts)


async def run_offer_agent(data: OfferInput) -> OfferResult:
    prompt = build_offer_prompt(data)

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=OFFER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            raise ValueError(f"Agent returned non-JSON: {raw[:200]}")

    return OfferResult(
        offer_trigger_id=data.offer_trigger_id,
        customer_id=data.customer_id,
        recommended_product=parsed["recommended_product"],
        product_display_name=parsed["product_display_name"],
        offer_rationale=parsed["offer_rationale"],
        estimated_annual_premium=parsed.get("estimated_annual_premium"),
        cross_sell_score=parsed["cross_sell_score"],
        confidence=parsed["confidence"],
        recommended_route=parsed["recommended_route"],
        personalization_angle=parsed["personalization_angle"],
        channel_recommendation=parsed["channel_recommendation"],
        urgency=parsed["urgency"],
        flags=parsed.get("flags", []),
        reasoning=parsed["reasoning"],
        suggested_next_steps=parsed.get("suggested_next_steps", []),
        processed_at=datetime.utcnow().isoformat() + "Z"
    )

# ── FASTAPI ROUTES ────────────────────────────────────────────────────────

def register_routes(app: FastAPI):

    @app.post("/agent/offer", response_model=OfferResult, tags=["Agents"])
    async def generate_offer(
        data: OfferInput,
        session: AsyncSession = Depends(db_session),
    ):
        """
        Offer Agent.
        Generates personalized product recommendation and routing decision.
        Persists result to DB.
        """
        try:
            result = await run_offer_agent(data)

            # ── Persist to DB ──────────────────────────────────────────
            offer_repo = OfferRepository(session)
            event_repo = EventRepository(session)

            await offer_repo.create({
                "offer_trigger_id":          data.offer_trigger_id,
                "customer_id":               data.customer_id,
                "trigger_type":              data.trigger_type,
                "source_pipeline":           "direct",
                "recommended_product":       result.recommended_product,
                "product_display_name":      result.product_display_name,
                "offer_rationale":           result.offer_rationale,
                "estimated_annual_premium":  result.estimated_annual_premium,
                "cross_sell_score":          result.cross_sell_score,
                "confidence":                result.confidence,
                "personalization_angle":     result.personalization_angle,
                "channel_recommendation":    result.channel_recommendation,
                "urgency":                   result.urgency,
                "agent_reasoning":           result.reasoning,
                "flags":                     result.flags,
                "recommended_route":         result.recommended_route,
                "final_route":               result.recommended_route,
                "agent_processed_at":        datetime.utcnow(),
                "customer_snapshot": {
                    "customer_name":          data.customer_name,
                    "segment":                data.segment,
                    "age_group":              data.age_group,
                    "customer_since_years":   data.customer_since_years,
                    "annual_premium":         data.annual_premium,
                    "customer_ltv":           data.customer_ltv,
                    "existing_products":      data.existing_products,
                    "recent_life_events":     data.recent_life_events,
                },
            })

            await event_repo.log(
                pipeline=    "offer",
                entity_id=   data.offer_trigger_id,
                entity_type= "offer",
                event_type=  "agent_processed",
                payload={
                    "product":          result.recommended_product,
                    "route":            result.recommended_route,
                    "cross_sell_score": result.cross_sell_score,
                    "confidence":       result.confidence,
                    "urgency":          result.urgency,
                },
            )

            logger.info(
                f"[Offer] {data.offer_trigger_id} → {result.recommended_product} "
                f"(score={result.cross_sell_score:.2f}) → {result.recommended_route}"
            )
            return result

        except Exception as e:
            logger.error(f"[Offer] Error processing {data.offer_trigger_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/agent/offer/health", tags=["Health"])
    async def offer_health():
        return {"agent": "offer", "status": "ok"}
