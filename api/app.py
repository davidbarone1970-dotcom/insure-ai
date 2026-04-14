from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone
import uuid
 
app = FastAPI(title="INSURE.AI Decision Engine")
 
 
class LeadInput(BaseModel):
    name: str
    company: str
    email: EmailStr
    company_size: int
    interaction_level: int
    existing_customer: bool
    source: str = "web_form"
    do_not_contact: bool = False  # Expliziter Fallback-Trigger
 
 
def compute_score(lead: LeadInput) -> int:
    return (
        (30 if lead.company_size > 20 else 10) +
        (40 if lead.interaction_level > 5 else 20) +
        (30 if lead.existing_customer else 10)
    )
 
 
def determine_route(score: int, lead: LeadInput) -> dict:
    """
    4 Routen:
      Fallback   → do_not_contact=True ODER ungültige Daten
      Sales      → score >= 71
      Nurturing  → score 41-70
      Automation → score <= 40
    """
 
    # Fallback: expliziter Edge-Case
    if lead.do_not_contact:
        return {
            "route": "Fallback",
            "final_action": "Flag for manual review - do not contact",
            "owner": "Operations",
            "priority": "Low",
            "fallback_reason": "do_not_contact flag set"
        }
 
    if lead.company_size < 1 or lead.interaction_level < 1:
        return {
            "route": "Fallback",
            "final_action": "Flag for manual review - invalid data",
            "owner": "Operations",
            "priority": "Low",
            "fallback_reason": "invalid field values"
        }
 
    # Score-basiertes Routing
    if score >= 71:
        return {
            "route": "Sales",
            "final_action": "Create CRM task",
            "owner": "Sales Team",
            "priority": "High",
            "fallback_reason": None
        }
    elif score >= 41:
        return {
            "route": "Nurturing",
            "final_action": "Add to nurturing campaign",
            "owner": "Marketing",
            "priority": "Medium",
            "fallback_reason": None
        }
    else:
        return {
            "route": "Automation",
            "final_action": "Send automated follow-up",
            "owner": "System",
            "priority": "Low",
            "fallback_reason": None
        }
 
 
@app.get("/")
def root():
    return {"status": "ok", "service": "INSURE.AI Decision Engine"}
 
 
@app.post("/score-lead")
def score_lead(lead: LeadInput):
    try:
        lead_id = str(uuid.uuid4())
        score = compute_score(lead)
        routing = determine_route(score, lead)
 
        segment = "Upper SMB" if lead.company_size >= 50 else "SMB"
        history_flag = "known" if lead.existing_customer else "new"
 
        return {
            "lead_id": lead_id,
            "name": lead.name,
            "company": lead.company,
            "email": lead.email,
            "company_size": lead.company_size,
            "interaction_level": lead.interaction_level,
            "existing_customer": lead.existing_customer,
            "do_not_contact": lead.do_not_contact,
            "source": lead.source,
            "segment": segment,
            "history_flag": history_flag,
            "score": score,
            "route": routing["route"],
            "priority": routing["priority"],
            "final_action": routing["final_action"],
            "owner": routing["owner"],
            "fallback_reason": routing["fallback_reason"],
            "status": "processed",
            "log": {
                "lead_id": lead_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": lead.source,
                "score": score,
                "route": routing["route"],
                "priority": routing["priority"],
                "fallback_reason": routing["fallback_reason"],
            }
        }
 
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )