# INSURE.AI - The SMB Transformation Engine

An end-to-end AI-driven digital transformation starter kit for a simulated SMB insurance company.

## What this starter kit includes
- Modular Python project structure for VS Code
- Agent-based workflow simulation
- Sample insurance data
- FastAPI entrypoint for future API expansion
- Technical and business manuals
- Ready-to-run simulation script

## Core use cases
1. Lead intake and prioritization
2. Claims triage and routing
3. Churn-risk detection and retention actions
4. Orchestrated next-best-action workflow

## Recommended stack
- Python 3.11+
- VS Code
- FastAPI
- pytest
- Optional: n8n, OpenAI, Anthropic, LangChain/LangGraph

## Quick start
```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python simulation/run_simulation.py
```

## Project structure
```text
insure-ai-transformation-engine/
├── agents/
├── api/
├── architecture/
├── data/
├── docs/
├── models/
├── simulation/
├── tests/
├── workflows/
├── .vscode/
├── README.md
├── requirements.txt
└── .env.example
```

## Next recommended steps
- Replace rule-based scoring with LLM or ML models
- Connect workflows to n8n or Power Automate
- Add a small dashboard with Streamlit
- Containerize with Docker
