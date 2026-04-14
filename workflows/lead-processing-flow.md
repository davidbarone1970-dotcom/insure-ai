# INSURE.AI – Lead Processing Workflow

## Overview

This workflow automates the intake, evaluation, and routing of new leads using AI-driven logic.

It is the first operational workflow of INSURE.AI and serves as the foundation for further automation.

---

## Workflow Objective

- capture incoming leads
- enrich data
- calculate lead score
- decide next-best action
- route lead automatically
- log outcome

---

## End-to-End Flow

```mermaid
flowchart LR
    A["New Lead (Webhook/Form)"] --> B["Validate Data"]
    B --> C["Load Customer Context"]
    C --> D["Call Lead Agent"]
    D --> E["Calculate Score"]
    E --> F["Orchestrator Decision"]
    F --> G["Route to Sales"]
    F --> H["Route to Nurturing"]
    F --> I["Route to Automation"]
    G --> J["Log Result"]
    H --> J
    I --> J

Step-by-Step Workflow
1. Trigger

Node: Webhook

receives new lead data
source:
web form
CRM
manual input
2. Validate Data

Node: Set / IF

Check:

name exists
company exists
email format valid

If invalid:
→ stop or log error

3. Load Customer Context

Node: Code / HTTP Request

check if customer already exists
enrich data:
company size
interaction level
history
4. Call Lead Agent

Node: HTTP Request or Code

Option A:
→ call local Python API

Option B:
→ calculate score directly in node

Example logic:
const score =
  ($json.company_size > 20 ? 30 : 10) +
  ($json.interaction_level > 5 ? 40 : 20) +
  ($json.existing_customer ? 30 : 10);

return [{ score }];

const score =
  ($json.company_size > 20 ? 30 : 10) +
  ($json.interaction_level > 5 ? 40 : 20) +
  ($json.existing_customer ? 30 : 10);

return [{ score }];
Webhook
  ↓
Set (Validation)
  ↓
IF (valid?)
  ↓
Code / HTTP (enrichment)
  ↓
Code / HTTP (scoring)
  ↓
Switch (routing)
  ├── Sales Path
  ├── Nurturing Path
  └── Automation Path
        ↓
Logging Node

Example Input (JSON)
{
  "name": "Max Muster",
  "company": "Muster AG",
  "company_size": 45,
  "interaction_level": 7,
  "existing_customer": true
}
Example Output
{
  "score": 85,
  "route": "Sales",
  "action": "Create CRM task"
}
Business Value
faster lead response
better prioritization
higher conversion rate
reduced manual effort
Future Enhancements
real CRM integration (Dynamics)
AI-based text analysis (LLM)
predictive lead scoring model
multi-channel enrichment
real-time dashboards
