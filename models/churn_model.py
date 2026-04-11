from typing import Dict


def churn_probability(customer: Dict) -> float:
    base = 0.10
    if customer.get("satisfaction_score", 10) <= 6:
        base += 0.20
    if customer.get("interaction_level", 10) <= 3:
        base += 0.15
    if customer.get("tenure_years", 0) < 1:
        base += 0.10
    return round(min(base, 0.95), 2)
