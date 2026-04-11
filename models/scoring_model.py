from typing import Dict


def score_customer_value(customer: Dict) -> int:
    score = 0
    score += min(customer.get("policy_count", 0) * 10, 40)
    score += min(customer.get("tenure_years", 0) * 5, 25)
    score += min(customer.get("company_size", 0), 35)
    return score
