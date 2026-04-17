"""
INSURE.AI — Lead Intelligence Agent
FastAPI endpoint: POST /agent/lead
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import anthropic
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── MODELS ────────────────────────────────────────────────────────────────────

class LeadInput(BaseModel):
    lead_id: str
    customer_id: Optional[str] = None
    source: str                          # "web", "broker", "phone", "email", "referral"
    segment: str                         # "private", "sme", "enterprise", "fleet"
    product_interest: str                # "liability", "property", "life", "fleet", "cyber"
    # contact info
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    region: Optional[str] = None
    # enriched context (loaded by n8n before calling agent)
    company_size: Optional[int] = None
    estimated_annual_premium: Optional[float] = None
    interaction_level: Optional[int] = None   # 1–10 engagement score
    existing_customer: bool = False
    competitor_offer: bool = False
    competitor_offer_deadline: Optional[str] = None
    broker_id: Optional[str] = None
    notes: Optional[str] = None

class LeadResult(BaseModel):
    lead_id: str
    score: int                           # 0–100
    priority: str                        # "low", "medium", "high", "critical"
    confidence: float                    # 0.0 – 1.0
    recommended_route: str               # "sales_priority", "nurture", "automation_only", "fallback"
    estimated_ltv: Optional[float]
    flags: List[dict]
    reasoning: str
    suggested_next_steps: List[str]
    processed_at: str

# ── SYSTEM PROMPT ──────────────────────────────────────────────────────────────

LEAD_SYSTEM_PROMPT = """You are the Lead Intelligence Agent for INSURE.AI, an intelligent insurance automation platform operating in Switzerland.

Your job is to analyze incoming leads and produce a structured JSON assessment with a score and routing decision.

SCORING RULES (0–100):
- Company size >= 50 employees: +25
- Company size 20–49: +15
- Company size < 20: +5
- Estimated annual premium >= CHF 50k: +25
- Estimated annual premium CHF 10k–50k: +15
- Estimated annual premium < CHF 10k: +5
- Interaction level >= 8: +20
- Interaction level 5–7: +12
- Interaction level < 5: +5
- Existing customer: +15
- Competitor offer present: +10 (urgency signal)
- Broker channel: +5

ROUTING RULES:
- "sales_priority": Score >= 70 OR competitor deadline within 7 days OR enterprise segment
- "nurture": Score 40–69, no urgency signals
- "automation_only": Score < 40, private segment, low engagement
- "fallback": Insufficient data to score reliably (confidence < 0.60)

PRIORITY RULES:
- "critical": Score >= 85 OR estimated premium >= CHF 100k
- "high": Score 70–84 OR competitor offer present
- "medium": Score 40–69
- "low": Score < 40

FLAGS to raise:
- Competitor offer with deadline → danger
- Enterprise lead without broker → warn
- Missing key data (company size, premium estimate) → warn
- High score but low interaction → info
- Existing customer cross-sell opportunity → info

Always respond with valid JSON only. No markdown, no preamble.

JSON Schema:
{
  "score": 0,
  "priority": "low|medium|high|critical",
  "confidence": 0.00,
  "recommended_route": "sales_priority|nurture|automation_only|fallback",
  "estimated_ltv": null or number,
  "flags": [
    {"severity": "danger|warn|info", "label": "...", "detail": "..."}
  ],
  "reasoning": "...",
  "suggested_next_steps": ["...", "..."]
}"""

# ── AGENT LOGIC ────────────────────────────────────────────────────────────────

client = anthropic.Anthropic()

def build_lead_prompt(lead: LeadInput) -> str:
    parts = [
        f"LEAD ID: {lead.lead_id}",
        f"Source: {lead.source} | Segment: {lead.segment}",
        f"Product Interest: {lead.product_interest}",
        f"Region: {lead.region or 'unknown'}",
    ]
    if lead.company_name:
        parts.append(f"Company: {lead.company_name}")
    if lead.contact_name:
        parts.append(f"Contact: {lead.contact_name}")
    if lead.company_size is not None:
        parts.append(f"Company size: {lead.company_size} employees")
    if lead.estimated_annual_premium is not None:
        parts.append(f"Estimated annual premium: CHF {lead.estimated_annual_premium:,.0f}")
    if lead.interaction_level is not None:
        parts.append(f"Interaction level: {lead.interaction_level}/10")
    parts.append(f"Existing customer: {lead.existing_customer}")
    if lead.competitor_offer:
        parts.append(f"Competitor offer: YES (deadline: {lead.competitor_offer_deadline or 'unknown'})")
    if lead.broker_id:
        parts.append(f"Broker ID: {lead.broker_id}")
    if lead.notes:
        parts.append(f"Notes: {lead.notes}")
    return "\n".join(parts)


async def run_lead_agent(lead: LeadInput) -> LeadResult:
    prompt = build_lead_prompt(lead)

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=LEAD_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Agent returned non-JSON: {raw[:200]}")

    return LeadResult(
        lead_id=lead.lead_id,
        score=data["score"],
        priority=data["priority"],
        confidence=data["confidence"],
        recommended_route=data["recommended_route"],
        estimated_ltv=data.get("estimated_ltv"),
        flags=data.get("flags", []),
        reasoning=data["reasoning"],
        suggested_next_steps=data.get("suggested_next_steps", []),
        processed_at=datetime.utcnow().isoformat() + "Z"
    )


# ── FASTAPI ROUTES ─────────────────────────────────────────────────────────────

def register_routes(app: FastAPI):

    @app.post("/agent/lead", response_model=LeadResult, tags=["Agents"])
    async def assess_lead(lead: LeadInput):
        """
        Lead Intelligence Agent.
        Receives enriched lead data, returns score + routing decision.
        """
        try:
            result = await run_lead_agent(lead)
            logger.info(
                f"[Lead] {lead.lead_id} → {result.recommended_route} "
                f"(score={result.score}, confidence={result.confidence:.2f})"
            )
            return result
        except Exception as e:
            logger.error(f"[Lead] Error processing {lead.lead_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/agent/lead/health", tags=["Health"])
    async def lead_health():
        return {"agent": "lead", "status": "ok"}
