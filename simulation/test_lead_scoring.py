def calculate_score(company_size, interaction_level, existing_customer):
    score = (
        (30 if company_size > 20 else 10) +
        (40 if interaction_level > 5 else 20) +
        (30 if existing_customer else 10)
    )

    if score > 70:
        route = "Sales"
        action = "Create CRM task"
    elif score > 40:
        route = "Nurturing"
        action = "Add to nurturing campaign"
    else:
        route = "Automation"
        action = "Send automated follow-up"

    return {
        "score": score,
        "route": route,
        "action": action
    }


# 🔷 Testfälle
test_cases = [
    {
        "name": "Max Muster",
        "company": "Muster AG",
        "company_size": 50,
        "interaction": 8,
        "existing": True
    },
    {
        "name": "Anna Beispiel",
        "company": "Beispiel GmbH",
        "company_size": 15,
        "interaction": 6,
        "existing": False
    },
    {
        "name": "Tom Klein",
        "company": "Klein AG",
        "company_size": 5,
        "interaction": 1,
        "existing": False
    }
]


# 🔷 Testlauf
for case in test_cases:
    result = calculate_score(
        case["company_size"],
        case["interaction"],
        case["existing"]
    )

    print("\n-----------------------------")
    print(f"Lead: {case['name']}")
    print(f"Company: {case['company']}")
    print(f"Score: {result['score']}")
    print(f"Route: {result['route']}")
    print(f"Action: {result['action']}")