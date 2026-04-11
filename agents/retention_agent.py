from typing import Dict


class RetentionAgent:
    """Simple churn-risk assessment based on relationship indicators."""

    def evaluate(self, customer: Dict) -> Dict:
        risk = "low"
        satisfaction = customer.get("satisfaction_score", 0)
        interaction = customer.get("interaction_level", 0)
        tenure = customer.get("tenure_years", 0)

        if satisfaction <= 6 or interaction <= 3:
            risk = "medium"
        if satisfaction <= 4 or (interaction <= 2 and tenure >= 2):
            risk = "high"

        return {
            "agent": "RetentionAgent",
            "customer_id": customer.get("customer_id"),
            "risk": risk,
            "action": {
                "low": "standard_follow_up",
                "medium": "advisor_callback",
                "high": "retention_offer",
            }[risk],
        }
