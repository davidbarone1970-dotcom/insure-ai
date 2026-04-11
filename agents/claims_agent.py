from typing import Dict


class ClaimsAgent:
    """Basic claims triage starter agent."""

    def evaluate(self, claim: Dict) -> Dict:
        priority = "normal"
        if claim.get("claim_amount", 0) > 10000:
            priority = "high"
        if not claim.get("documents_complete", False):
            priority = "pending_documents"
        if claim.get("fraud_signal", False):
            priority = "fraud_review"

        return {
            "agent": "ClaimsAgent",
            "claim_id": claim.get("claim_id"),
            "priority": priority,
            "auto_process": priority == "normal",
        }
