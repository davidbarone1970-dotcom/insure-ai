from typing import Dict


class LeadAgent:
    """Rule-based lead scoring starter agent."""

    def evaluate(self, customer: Dict) -> Dict:
        score = 0
        if customer.get("company_size", 0) >= 20:
            score += 30
        if customer.get("interaction_level", 0) >= 5:
            score += 40
        if customer.get("existing_customer", False):
            score += 30

        if score >= 70:
            route = "sales_priority"
        elif score >= 40:
            route = "nurture"
        else:
            route = "automation_only"

        return {
            "agent": "LeadAgent",
            "customer_id": customer.get("customer_id"),
            "score": score,
            "route": route,
        }
