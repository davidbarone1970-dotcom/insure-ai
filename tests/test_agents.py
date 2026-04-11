from agents.lead_agent import LeadAgent
from agents.retention_agent import RetentionAgent


def test_lead_agent_high_score():
    result = LeadAgent().evaluate(
        {
            "customer_id": "C-1",
            "company_size": 50,
            "interaction_level": 7,
            "existing_customer": True,
        }
    )
    assert result["route"] == "sales_priority"



def test_retention_agent_high_risk():
    result = RetentionAgent().evaluate(
        {
            "customer_id": "C-2",
            "satisfaction_score": 4,
            "interaction_level": 2,
            "tenure_years": 3,
        }
    )
    assert result["risk"] == "high"
