from typing import Dict


class Orchestrator:
    """Combines agent outputs into one next-best-action decision."""

    def decide(self, lead_result: Dict, retention_result: Dict) -> Dict:
        next_best_action = "monitor"

        if lead_result.get("route") == "sales_priority":
            next_best_action = "assign_to_sales"
        elif retention_result.get("risk") == "high":
            next_best_action = "launch_retention_play"
        elif lead_result.get("route") == "nurture":
            next_best_action = "start_nurture_sequence"

        return {
            "agent": "Orchestrator",
            "customer_id": lead_result.get("customer_id"),
            "next_best_action": next_best_action,
            "inputs": {
                "lead_route": lead_result.get("route"),
                "retention_risk": retention_result.get("risk"),
            },
        }
