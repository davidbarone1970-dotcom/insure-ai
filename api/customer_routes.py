"""
INSURE.AI — Customer & Product Stub Endpoints

Mock-data endpoints consumed by n8n pipelines (Retention & Offer) to enrich
event payloads before the agent call. Deterministic by design:
- Known customer IDs (MOCK_CUSTOMERS) return hand-curated personas.
- Unknown IDs fall back to a seed-deterministic generator based on customer_id
  hash, so the same ID always produces the same response across sessions.

When a real CRM integration becomes available, replace MOCK_CUSTOMERS lookups
with DB / HTTP calls; the seed fallback can remain as an "unknown customer"
handler.
"""

from __future__ import annotations

import hashlib
import random
from typing import Optional

from fastapi import FastAPI, Query


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _seeded_rng(customer_id: str) -> random.Random:
    """Stable RNG: same customer_id → same sequence across runs."""
    seed = int(hashlib.md5(customer_id.encode("utf-8")).hexdigest(), 16)
    return random.Random(seed)


def _parse_csv(value: Optional[str]) -> list[str]:
    """Parse a comma-separated query param into a list. Empty → []."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


# ── CATALOGUES ────────────────────────────────────────────────────────────────

ALL_PRODUCTS = [
    "haftpflicht_privat",
    "hausrat",
    "rechtsschutz_privat",
    "life_insurance",
    "auto_vollkasko",
    "cyber_business",
    "haftpflicht_business",
    "betriebsversicherung_kmu",
    "krankentaggeld",
    "unfallversicherung",
]

PRODUCTS_BY_SEGMENT = {
    "private":          ["haftpflicht_privat", "hausrat", "rechtsschutz_privat", "life_insurance", "auto_vollkasko"],
    "premium_private":  ["hausrat", "rechtsschutz_privat", "life_insurance", "auto_vollkasko", "unfallversicherung"],
    "sme":              ["cyber_business", "haftpflicht_business", "betriebsversicherung_kmu"],
    "enterprise":       ["cyber_business", "haftpflicht_business", "betriebsversicherung_kmu"],
    "self_employed":    ["krankentaggeld", "haftpflicht_business", "rechtsschutz_privat"],
}

SEGMENTS = ["private", "premium_private", "sme", "self_employed"]
AGE_GROUPS = ["25-34", "35-44", "45-54", "55-64", "65+"]
INDUSTRIES = ["IT", "Retail", "Manufacturing", "Consulting", "Healthcare", "Logistics"]


# ── MOCK DB: HAND-CURATED PERSONAS ────────────────────────────────────────────
# These IDs show up in the existing test data (DB seeds, HITL mock UI, session
# history). Add new personas here when you need a specific story for a demo.

MOCK_CUSTOMERS = {
    # Premium Private, Long-Term, Churn-Risk Persona (appears in HITL mock UI)
    "CUST-8001": {
        "customer_name":         "Dr. H. Zimmermann",
        "segment":               "premium_private",
        "age_group":             "55-64",
        "customer_since_years":  13,
        "annual_premium":        9400.0,
        "customer_ltv":          122200.0,
        "policy_count":          2,
        "policy_types":          ["life_insurance", "hausrat"],
        "existing_products":     ["life_insurance", "hausrat"],
        "last_claim_months_ago": None,
        "total_claims_ever":     0,
        "nps_score":             7,
        "renewal_due_days":      45,
        "recent_life_events":    [],
        "industry":              None,
        "employee_count":        None,
        "annual_revenue":        None,
        # Behavior signals (30-day rolling)
        "portal_logins":             12,
        "contract_views":            4,
        "competitor_portal_visits":  3,
        "support_contacts":          1,
        "email_open_rate":           0.72,
        # Recent offers
        "offers_sent_last_90_days":  [],
    },
    # SME, IT, Cyber Unterdeckung (appears in HITL mock UI)
    "CUST-9001": {
        "customer_name":         "Meister Digital GmbH",
        "segment":               "sme",
        "age_group":             None,
        "customer_since_years":  6,
        "annual_premium":        3200.0,
        "customer_ltv":          19200.0,
        "policy_count":          1,
        "policy_types":          ["betriebsversicherung_kmu"],
        "existing_products":     ["betriebsversicherung_kmu"],
        "last_claim_months_ago": None,
        "total_claims_ever":     0,
        "nps_score":             8,
        "renewal_due_days":      120,
        "recent_life_events":    [],
        "industry":              "IT",
        "employee_count":        18,
        "annual_revenue":        2400000.0,
        "portal_logins":             3,
        "contract_views":            0,
        "competitor_portal_visits":  0,
        "support_contacts":          0,
        "email_open_rate":           0.45,
        "offers_sent_last_90_days":  [],
    },
    # Enterprise Lead (appears in HITL mock UI)
    "CUST-ZT-240": {
        "customer_name":         "Zürich Transport GmbH",
        "segment":               "enterprise",
        "age_group":             None,
        "customer_since_years":  0,
        "annual_premium":        0.0,
        "customer_ltv":          180000.0,
        "policy_count":          0,
        "policy_types":          [],
        "existing_products":     [],
        "last_claim_months_ago": None,
        "total_claims_ever":     0,
        "nps_score":             None,
        "renewal_due_days":      None,
        "recent_life_events":    [],
        "industry":              "Logistics",
        "employee_count":        450,
        "annual_revenue":        85000000.0,
        "portal_logins":             0,
        "contract_views":            0,
        "competitor_portal_visits":  0,
        "support_contacts":          0,
        "email_open_rate":           0.0,
        "offers_sent_last_90_days":  [],
    },
    # Retail Private, stable long-term (demo counter-example: low churn risk)
    "CUST-SUTER": {
        "customer_name":         "E. & P. Suter",
        "segment":               "premium_private",
        "age_group":             "65+",
        "customer_since_years":  18,
        "annual_premium":        5600.0,
        "customer_ltv":          100800.0,
        "policy_count":          2,
        "policy_types":          ["life_insurance", "unfallversicherung"],
        "existing_products":     ["life_insurance", "unfallversicherung"],
        "last_claim_months_ago": 48,
        "total_claims_ever":     1,
        "nps_score":             9,
        "renewal_due_days":      60,
        "recent_life_events":    [],
        "industry":              None,
        "employee_count":        None,
        "annual_revenue":        None,
        "portal_logins":             2,
        "contract_views":            1,
        "competitor_portal_visits":  0,
        "support_contacts":          0,
        "email_open_rate":           0.85,
        "offers_sent_last_90_days":  [],
    },
    # Test IDs actually present in the DB seeds
    "TEST-K-N8N-002": {
        "customer_name":         "N8N Test Persona",
        "segment":               "private",
        "age_group":             "35-44",
        "customer_since_years":  5,
        "annual_premium":        1800.0,
        "customer_ltv":          9000.0,
        "policy_count":          2,
        "policy_types":          ["haftpflicht_privat", "hausrat"],
        "existing_products":     ["haftpflicht_privat", "hausrat"],
        "last_claim_months_ago": None,
        "total_claims_ever":     0,
        "nps_score":             6,
        "renewal_due_days":      90,
        "recent_life_events":    [],
        "industry":              None,
        "employee_count":        None,
        "annual_revenue":        None,
        "portal_logins":             5,
        "contract_views":            1,
        "competitor_portal_visits":  1,
        "support_contacts":          0,
        "email_open_rate":           0.55,
        "offers_sent_last_90_days":  [],
    },
    "TEST-K-QUEUE-001": {
        "customer_name":         "Queue Test KMU",
        "segment":               "sme",
        "age_group":             None,
        "customer_since_years":  3,
        "annual_premium":        2100.0,
        "customer_ltv":          6300.0,
        "policy_count":          1,
        "policy_types":          ["betriebsversicherung_kmu"],
        "existing_products":     ["betriebsversicherung_kmu"],
        "last_claim_months_ago": None,
        "total_claims_ever":     0,
        "nps_score":             7,
        "renewal_due_days":      180,
        "recent_life_events":    [],
        "industry":              "IT",
        "employee_count":        12,
        "annual_revenue":        1500000.0,
        "portal_logins":             2,
        "contract_views":            0,
        "competitor_portal_visits":  0,
        "support_contacts":          0,
        "email_open_rate":           0.50,
        "offers_sent_last_90_days":  [],
    },
}


# ── SEED FALLBACK GENERATOR ───────────────────────────────────────────────────

def _generate_from_seed(customer_id: str) -> dict:
    """Build a plausible but deterministic customer record for unknown IDs."""
    rng = _seeded_rng(customer_id)
    segment = rng.choice(SEGMENTS)
    is_business = segment in ("sme", "enterprise")

    customer_since = rng.randint(0, 20)
    annual_premium = round(rng.uniform(800, 12000), 2)
    ltv = round(annual_premium * max(customer_since, 1) * rng.uniform(0.8, 1.2), 2)

    pool = PRODUCTS_BY_SEGMENT.get(segment, ALL_PRODUCTS)
    policy_count = rng.randint(0, min(3, len(pool)))
    existing = rng.sample(pool, k=policy_count) if policy_count else []

    return {
        "customer_name":         f"Seed Persona {customer_id[:12]}",
        "segment":               segment,
        "age_group":             rng.choice(AGE_GROUPS) if not is_business else None,
        "customer_since_years":  customer_since,
        "annual_premium":        annual_premium,
        "customer_ltv":          ltv,
        "policy_count":          policy_count,
        "policy_types":          list(existing),
        "existing_products":     list(existing),
        "last_claim_months_ago": rng.choice([None, None, 6, 18, 36]),  # mostly None
        "total_claims_ever":     rng.randint(0, 3),
        "nps_score":             rng.randint(3, 10),
        "renewal_due_days":      rng.choice([30, 60, 90, 120, 180, 365]),
        "recent_life_events":    [],
        "industry":              rng.choice(INDUSTRIES) if is_business else None,
        "employee_count":        rng.randint(5, 250) if is_business else None,
        "annual_revenue":        round(rng.uniform(500_000, 20_000_000), 2) if is_business else None,
        "portal_logins":             rng.randint(0, 15),
        "contract_views":            rng.randint(0, 5),
        "competitor_portal_visits":  rng.randint(0, 3),
        "support_contacts":          rng.randint(0, 2),
        "email_open_rate":           round(rng.uniform(0.2, 0.9), 2),
        "offers_sent_last_90_days":  [],
    }


def _get_customer(customer_id: str) -> dict:
    """Resolve a customer to a full record: mock DB first, then seed fallback."""
    if customer_id in MOCK_CUSTOMERS:
        return MOCK_CUSTOMERS[customer_id]
    return _generate_from_seed(customer_id)


# ── ROUTE REGISTRATION ────────────────────────────────────────────────────────

def register_routes(app: FastAPI) -> None:

    @app.get("/api/v1/customers/{customer_id}/profile", tags=["Customer Stubs"])
    async def customer_profile(customer_id: str):
        """Lightweight profile for the Offer pipeline (segment, LTV, existing products, life events)."""
        c = _get_customer(customer_id)
        return {
            "customer_id":          customer_id,
            "customer_name":        c["customer_name"],
            "segment":              c["segment"],
            "age_group":            c["age_group"],
            "customer_since_years": c["customer_since_years"],
            "annual_premium":       c["annual_premium"],
            "customer_ltv":         c["customer_ltv"],
            "existing_products":    c["existing_products"],
            "recent_life_events":   c["recent_life_events"],
            "industry":             c["industry"],
            "employee_count":       c["employee_count"],
            "annual_revenue":       c["annual_revenue"],
        }

    @app.get("/api/v1/customers/{customer_id}/full-profile", tags=["Customer Stubs"])
    async def customer_full_profile(customer_id: str):
        """Full record for the Retention pipeline — adds policy + claim history + renewal window."""
        c = _get_customer(customer_id)
        return {
            "customer_id":           customer_id,
            "customer_name":         c["customer_name"],
            "segment":               c["segment"],
            "customer_since_years":  c["customer_since_years"],
            "annual_premium":        c["annual_premium"],
            "customer_ltv":          c["customer_ltv"],
            "policy_count":          c["policy_count"],
            "policy_types":          c["policy_types"],
            "last_claim_months_ago": c["last_claim_months_ago"],
            "total_claims_ever":     c["total_claims_ever"],
            "nps_score":             c["nps_score"],
            "renewal_due_days":      c["renewal_due_days"],
        }

    @app.get("/api/v1/customers/{customer_id}/behavior", tags=["Customer Stubs"])
    async def customer_behavior(
        customer_id: str,
        days: int = Query(30, ge=1, le=365),
    ):
        """Behavioural signals over a window (default 30d). Scales linearly with window size."""
        c = _get_customer(customer_id)
        # Scale count-based signals relative to the 30-day baseline in the mock data.
        factor = days / 30.0
        return {
            "customer_id":              customer_id,
            "window_days":              days,
            "portal_logins":            int(round(c["portal_logins"] * factor)),
            "contract_views":           int(round(c["contract_views"] * factor)),
            "competitor_portal_visits": int(round(c["competitor_portal_visits"] * factor)),
            "support_contacts":         int(round(c["support_contacts"] * factor)),
            "email_open_rate":          c["email_open_rate"],  # rate, not count → no scaling
        }

    @app.get("/api/v1/customers/{customer_id}/offers", tags=["Customer Stubs"])
    async def customer_offers(
        customer_id: str,
        days: int = Query(90, ge=1, le=365),
    ):
        """Recent offers sent to this customer — used by the Offer pipeline to avoid spam."""
        c = _get_customer(customer_id)
        return {
            "customer_id":               customer_id,
            "window_days":               days,
            "offers_sent":               c["offers_sent_last_90_days"],
            "count":                     len(c["offers_sent_last_90_days"]),
        }

    @app.get("/api/v1/products/available", tags=["Customer Stubs"])
    async def products_available(
        segment: Optional[str] = Query(None),
        exclude: Optional[str] = Query(None, description="Comma-separated product IDs to exclude"),
    ):
        """Catalogue lookup: products available for a segment, minus already-held products."""
        base = PRODUCTS_BY_SEGMENT.get(segment or "", ALL_PRODUCTS)
        excluded = set(_parse_csv(exclude))
        available = [p for p in base if p not in excluded]
        return {
            "segment":          segment,
            "excluded":         sorted(excluded),
            "available":        available,
            "count":            len(available),
        }