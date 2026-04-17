"""
INSURE.AI â€” FastAPI Application Entry Point
All agents + PostgreSQL DB layer + Audit/KPI/Review API
"""

from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from db.database import startup as db_startup, shutdown as db_shutdown
from agents import claims_agent, retention_agent, offer_agent, lead_agent
from api import audit_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_startup()    # verify DB connection on boot
    yield
    await db_shutdown()   # dispose pool on shutdown

app = FastAPI(
    title="INSURE.AI Agent Backend",
    description="AI-powered insurance automation. Agents: Claims Â· Retention Â· Offer. Storage: PostgreSQL.",
    version="0.9.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# â”€â”€ REGISTER ALL ROUTES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

claims_agent.register_routes(app)
retention_agent.register_routes(app)
offer_agent.register_routes(app)
lead_agent.register_routes(app)
audit_routes.register_routes(app)

# â”€â”€ GLOBAL HEALTH â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "INSURE.AI Agent Backend",
        "version": "0.9.0",
        "agents": ["claims", "retention", "offer"],
        "storage": "postgresql",
        "status": "operational"
    }

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "agents": 3, "db": "postgresql"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
