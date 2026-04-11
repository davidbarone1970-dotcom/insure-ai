import json
from pathlib import Path

from agents.claims_agent import ClaimsAgent
from agents.lead_agent import LeadAgent
from agents.orchestrator import Orchestrator
from agents.retention_agent import RetentionAgent
from models.churn_model import churn_probability
from models.scoring_model import score_customer_value


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"


def load_json(filename: str):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    customers = load_json("customers.json")
    claims = load_json("claims.json")

    lead_agent = LeadAgent()
    claims_agent = ClaimsAgent()
    retention_agent = RetentionAgent()
    orchestrator = Orchestrator()

    print("=== INSURE.AI Simulation Start ===")

    for customer in customers:
        lead_result = lead_agent.evaluate(customer)
        retention_result = retention_agent.evaluate(customer)
        orchestration = orchestrator.decide(lead_result, retention_result)
        customer_value = score_customer_value(customer)
        churn_risk = churn_probability(customer)

        print(f"Customer: {customer['name']}")
        print(f"  Lead score: {lead_result['score']} -> {lead_result['route']}")
        print(f"  Retention risk: {retention_result['risk']} -> {retention_result['action']}")
        print(f"  Value score: {customer_value}")
        print(f"  Churn probability: {churn_risk}")
        print(f"  Next best action: {orchestration['next_best_action']}")
        print()

    for claim in claims:
        claim_result = claims_agent.evaluate(claim)
        print(f"Claim: {claim['claim_id']}")
        print(f"  Priority: {claim_result['priority']}")
        print(f"  Auto process: {claim_result['auto_process']}")
        print()

    print("=== INSURE.AI Simulation End ===")


if __name__ == "__main__":
    main()
