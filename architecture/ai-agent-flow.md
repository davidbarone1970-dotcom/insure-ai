# INSURE.AI – AI Agent Flow

## Overview

This document defines the AI-driven decision logic of **INSURE.AI – The SMB Transformation Engine**.

The system uses a coordinated set of specialized AI agents to simulate how an SMB insurance company can automate and optimize its core processes.

The design follows an **agentic architecture**, where:
- each agent has a clear responsibility
- decisions are orchestrated centrally
- workflows are executed automatically
- human control remains possible

---

## Core Agents

The system is built around four primary agents:

- **Lead Intelligence Agent** → evaluates and prioritizes leads  
- **Claims Assessment Agent** → classifies claims and determines handling  
- **Retention Agent** → detects churn risk and triggers actions  
- **Orchestrator Agent** → coordinates decisions and workflows  

---

## Executive Flow

```mermaid
flowchart LR
    A["Business Event"] --> B["Data Retrieval"]
    B --> C["Specialized Agent"]
    C --> D["Orchestrator Agent"]
    D --> E["Business Action"]
    E --> F["Monitoring & Audit"]

Detailed Agent Flow

```mermaid
mermaid-diagram_1.png

Core Workflows
1. Lead Intelligence Flow
Purpose

Evaluate incoming leads and determine next-best action.

Input
Company size
Industry
Interaction level
Existing relationship
Channel source
Process
Lead enters system (web, broker, form)
Customer data is loaded
Lead Agent calculates score
Orchestrator decides:
Sales routing
Nurturing
Automation
Result is stored and logged
Output
Lead score
Priority
Routing decision

Flow
```mermaid
mermaid-diagram_2.png

2. Claims Assessment Flow
Purpose

Classify claims and determine handling process.

Input
Claim type
Damage estimate
Policy coverage
Customer segment
Claim description
Process
Claim is submitted
Policy and customer data are loaded
Claims Agent classifies case
Orchestrator decides:
Auto processing
Escalation
Manual review
Audit trail is created
Output
Claim category
Priority
Handling decision

Flow
```mermaid
mermaid-diagram_3

3. Retention Flow
Purpose

Identify churn risk and trigger retention actions.

Input
Renewal timing
Interaction frequency
Claims history
Customer value
Complaint signals
Process
Retention trigger detected
Customer profile loaded
Retention Agent calculates risk
Orchestrator selects action:
Campaign
Personal outreach
Offer generation
Action is tracked
Output
Churn risk score
Recommended action
Retention trigger

Flow
```mermaid
mermaid-diagram_4.png

4. Offer Generation Flow
Purpose

Generate personalized offers based on context and agent insights.

Input
Lead score
Customer profile
Product portfolio
Policy gaps
Process
Offer trigger identified
Customer and product data loaded
Offer Agent generates recommendation
Orchestrator validates decision
Offer is generated and routed
Output
Offer proposal
Product bundle
Sales recommendation

Flow
```mermaid
mermaid-diagram_5.png

Orchestrator Agent
Role

The Orchestrator Agent is the central decision unit of INSURE.AI.

It:

coordinates all agents
consolidates outputs
applies business rules
determines next-best action
ensures auditability
Decision Logic

The Orchestrator evaluates:

confidence score
customer value
urgency
risk level
business rules

Orchestrator Flow
```mermaid
mermaid-diagram_6.png

Human-in-the-Loop Principle

INSURE.AI ensures controlled automation.

Human review is triggered for:

low-confidence decisions
high-value customers
complex claims
compliance-sensitive cases

This guarantees:

quality
trust
transparency
explainability
Implementation Mapping
Python
scoring logic
routing logic
simulation execution
n8n
workflow orchestration
triggers and automation
API calls
AI Providers
OpenAI
Anthropic
Azure OpenAI

Used for:

classification
summarization
recommendations
reasoning
Summary

The AI Agent Flow transforms insurance operations from:

manual
fragmented
reactive

into:

automated
coordinated
AI-assisted
scalable