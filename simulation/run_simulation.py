# INSURE.AI - Lead Processing Simulation
# Mirrors the logic of api/app.py


def calculate_score(company_size: int, interaction_level: int, existing_customer: bool) -> int:
    return (
        (30 if company_size > 20 else 10) +
        (40 if interaction_level > 5 else 20) +
        (30 if existing_customer else 10)
    )


def determine_route(score: int, do_not_contact: bool = False, company_size: int = 1, interaction_level: int = 1) -> dict:
    # Fallback: explicit edge cases
    if do_not_contact:
        return {
            "route": "Fallback",
            "action": "Flag for manual review - do not contact",
            "owner": "Operations",
            "priority": "Low",
            "fallback_reason": "do_not_contact flag set"
        }
    if company_size < 1 or interaction_level < 1:
        return {
            "route": "Fallback",
            "action": "Flag for manual review - invalid data",
            "owner": "Operations",
            "priority": "Low",
            "fallback_reason": "invalid field values"
        }

    # Score-based routing
    if score >= 71:
        return {"route": "Sales",      "action": "Create CRM task",           "owner": "Sales Team", "priority": "High",   "fallback_reason": None}
    elif score >= 41:
        return {"route": "Nurturing",  "action": "Add to nurturing campaign",  "owner": "Marketing",  "priority": "Medium", "fallback_reason": None}
    else:
        return {"route": "Automation", "action": "Send automated follow-up",   "owner": "System",     "priority": "Low",    "fallback_reason": None}


# Test cases covering all 4 routes
test_cases = [
    {
        "name": "Max Muster",
        "company": "Muster AG",
        "company_size": 50,
        "interaction_level": 8,
        "existing_customer": True,
        "do_not_contact": False
    },
    {
        "name": "Anna Beispiel",
        "company": "Beispiel GmbH",
        "company_size": 5,
        "interaction_level": 6,
        "existing_customer": False,
        "do_not_contact": False
    },
    {
        "name": "Tom Klein",
        "company": "Klein AG",
        "company_size": 5,
        "interaction_level": 3,
        "existing_customer": False,
        "do_not_contact": False
    },
    {
        "name": "Do Not Call",
        "company": "Blocked AG",
        "company_size": 50,
        "interaction_level": 8,
        "existing_customer": True,
        "do_not_contact": True
    }
]

# Run simulation
print("=" * 40)
print("  INSURE.AI - Lead Processing Simulation")
print("=" * 40)

for case in test_cases:
    score = calculate_score(
        case["company_size"],
        case["interaction_level"],
        case["existing_customer"]
    )
    result = determine_route(
        score=score,
        do_not_contact=case["do_not_contact"],
        company_size=case["company_size"],
        interaction_level=case["interaction_level"]
    )

    print(f"\n--- Lead: {case['name']} ---")
    print(f"Company:         {case['company']}")
    print(f"Score:           {score}")
    print(f"Route:           {result['route']}")
    print(f"Action:          {result['action']}")
    print(f"Owner:           {result['owner']}")
    print(f"Priority:        {result['priority']}")
    if result["fallback_reason"]:
        print(f"Fallback Reason: {result['fallback_reason']}")

print("\n" + "=" * 40)
print("  Simulation complete.")
print("=" * 40)