# ADR-002: Pipeline Entity & Audit-Event Naming Conventions

| Status   | Accepted                                       |
|----------|------------------------------------------------|
| Date     | 2026-04-21                                     |
| Author   | David B. (with Claude Opus 4.7)                |
| Related  | ADR-001 (Enum types), Tech-Debt Items #1, #7, #9 |

---

## Context

Während der End-to-End-Verifikation der Retention-Pipeline (2026-04-21)
wurde ein Naming-Drift in `pipeline_events.entity_id` entdeckt: Audit-Events
wurden mit `customer_id` statt mit dem Business-Key geschrieben, was den
Audit-Trail nicht-joinbar zur fachlichen Tabelle machte.

Eine systematische Inventory aller vier Pipelines (Lead, Claims, Offer,
Retention) ergab Drifts auf **sechs verschiedenen Ebenen**:

### Drift-Inventory

| Aspekt                              | Lead              | Claims            | Offer              | Retention             |
|-------------------------------------|-------------------|-------------------|--------------------|------------------------|
| Tabellen-Name                       | `leads` ✓         | `claims` ✓        | `offers` ✓         | `retention_events` ✗   |
| Business-Key-Spalte                 | `lead_id` ✓       | `claim_id` ✓      | `offer_trigger_id` ✗ | `retention_event_id` ✗ |
| `pipeline_events.pipeline`          | `lead` ✓          | `claims` ✗        | `offer` ✓          | `retention` ✓          |
| `pipeline_events.entity_type`       | `lead` + `unknown` ✗ | `claim` ✓      | `offer` ✓          | `retention` ✓          |
| `pipeline_events.event_type` Drifts | `pipeline_event` ✗ | sauber ✓         | sauber ✓           | `outcome_tracked` ✗    |
| `pipeline_events.entity_id`         | meist BK ✓        | BK ✓              | BK ✓               | **Regression** ✗       |

Die Drifts wurden nicht durch Bösartigkeit eingebaut, sondern durch
inkrementelles Wachstum der vier Pipelines ohne expliziten gemeinsamen
Naming-Standard. Das ADR codifiziert diesen Standard nachträglich
und legt einen Migrations-Plan fest.

---

## Decisions

### D1 — Fachliche Tabellen heißen `<pipeline-singular>s` (Plural, kein Prefix)

**Standard:** `leads`, `claims`, `offers`, `retentions`

**Begründung:** Drei von vier Pipelines folgen bereits diesem Pattern.
Der `_events`-Suffix bei Retention ist ein Relikt aus einer früheren
Iteration (als Retention noch event-driven gedacht war), inzwischen
sind alle vier Pipelines fachlich gleichwertige "Cases".

**Migration:** `retention_events` → `retentions`

---

### D2 — Business-Key-Spalte heißt `<pipeline-singular>_id` (varchar)

**Standard:** `lead_id`, `claim_id`, `offer_id`, `retention_id`

**Begründung:** `offer_trigger_id` und `retention_event_id` sind semantisch
spezifischer, aber das macht die Pipelines untereinander schwerer vergleichbar.
Die fachliche Differenzierung ("ein Trigger kann mehrere Offers erzeugen")
bleibt durch separate Spalten/Tabellen möglich, sollte sie jemals real werden.

**Migration:**
- `offers.offer_trigger_id` → `offers.offer_id`
- `retention_events.retention_event_id` → `retentions.retention_id`

---

### D3 — `pipeline_events.pipeline` ist immer Singular

**Standard:** `lead`, `claim`, `offer`, `retention`

**Begründung:** Drei von vier sind Singular. Claims fällt aus der Reihe
(vermutlich weil `claims` auch der Tabellenname ist und das Backend
inkonsistent referenziert). Singular passt besser zum Konzept "diese
Pipeline" als Mengenbezeichnung.

**Migration:** UPDATE bestehender `pipeline_events`-Rows mit `pipeline = 'claims'` → `'claim'`

---

### D4 — `pipeline_events.entity_type` ist Pipeline-Singular, niemals `unknown`

**Standard:** `lead`, `claim`, `offer`, `retention`

**Begründung:** `unknown` als Wert ist ein Code-Smell — entweder weiß
das System welcher Entity-Type das ist (dann gehört der Wert hin) oder
der Audit-Event hätte gar nicht geschrieben werden sollen.

**Migration:** UPDATE `entity_type = 'unknown'` → `'lead'` (sofern aus Lead-Pipeline kommend, sonst Decision-by-Case)

---

### D5 — `pipeline_events.entity_id` ist IMMER der Business-Key

**Standard:** `lead_id`, `claim_id`, `offer_id`, `retention_id` — niemals
`customer_id`, `policy_id`, oder ein UUID-Primary-Key.

**Begründung:** Der Business-Key ist die einzige stabile, joinbare,
für Menschen lesbare Referenz zur fachlichen Tabelle. `customer_id`
verletzt 1:N (ein Kunde hat viele Cases), UUID-PKs sind nicht human-readable.

**Code-Fix nötig:**
- `agents/retention_agent.py` — schreibt aktuell `customer_id` als `entity_id`
- `agents/lead_agent.py` — vermutlich gleiches Problem (zu verifizieren)

---

### D6 — `pipeline_events.event_type` folgt einer geschlossenen Whitelist

**Standard-Werte:**

| `event_type`      | Wann                                          | Wer schreibt             |
|-------------------|-----------------------------------------------|--------------------------|
| `agent_processed` | LLM-Call abgeschlossen, Agent hat klassifiziert | Backend (FastAPI)       |
| `pipeline.routed` | Orchestrator hat Routing-Entscheidung getroffen | n8n (Track-Outcome-Node) |
| `human_review`    | Case in HITL-Queue eingestellt                | Backend                  |
| `outcome_recorded`| Tatsächliches Kunden-Outcome gemessen (zukünftig) | Backend (async)        |

**Begründung:** Klare Trennung zwischen "Agent hat entschieden" (technische
Klassifizierung) und "Pipeline hat geroutet" (Orchestrator-Geschäftslogik)
und "Outcome ist da" (Realität nach Tagen/Wochen). `outcome_tracked` und
`pipeline_event` sind beide semantisch falsch und müssen weg.

**Drifts zu fixen:**
- Lead n8n Track-Outcome: `pipeline_event` → `pipeline.routed`
- Retention n8n Track-Outcome: `outcome_tracked` → `pipeline.routed`

---

## Migration Plan

Die Migration läuft in **vier Phasen** mit Verifikationspunkten.
Jede Phase ist atomar — falls eine Phase abbricht, ist der vorherige Zustand
funktional intakt.

> **Scope-Revision (2026-04-21 nach Recency-Check):** Lead-Pipeline ist
> aktuell sauber — die `pipeline_event`/`unknown`-Drifts sind dormant
> (3 Test-Rows, älteste 2026-04-16, jüngste 2026-04-19, alle mit leeren
> Payloads). Phase 3 reduziert sich damit auf den Retention-Workflow,
> Phase 4 auf einen kleinen Cleanup-DELETE.

### Phase 1: ADR-Approval + Snapshots ✅
- ADR commiten (`docs/adr/ADR-002-pipeline-naming.md`)
- DB-Snapshot/Backup erstellen (Supabase Point-in-Time) vor Phase 2
- n8n-Workflow-Snapshots der aktuellen Versionen committen (analog Tech-Debt #3)

### Phase 2: Backend-Code + DB-Migration (koordiniert)
1. Branch `refactor/adr-002-naming` erstellen
2. SQLAlchemy-Models anpassen:
   - `RetentionEvent` → `Retention`, `__tablename__` → `retentions`
   - `retention_event_id` → `retention_id`
   - `offer_trigger_id` → `offer_id`
3. Repositories + Agents + API-Endpoints anpassen:
   - `retention_agent.py`: `entity_id = customer_id` → `entity_id = retention_id`
   - Claims-Audit-Calls: `pipeline = 'claims'` → `'claim'`
4. Dashboards (`insure-ai-hitl.html`, `insure-ai-dashboard.html`):
   - Spalten-Refs anpassen falls vorhanden
5. Alembic-Migration generieren:
   - `ALTER TABLE retention_events RENAME TO retentions`
   - `ALTER TABLE retentions RENAME COLUMN retention_event_id TO retention_id`
   - `ALTER TABLE offers RENAME COLUMN offer_trigger_id TO offer_id`
   - `UPDATE pipeline_events SET pipeline = 'claim' WHERE pipeline = 'claims'`
6. Lokal testen: `pytest`, dann manueller Smoke-Test pro Pipeline
7. Migration auf Supabase ausführen
8. Render-Deploy von Branch
9. Verifikation: alle vier `/api/v1/<pipeline>/...`-Direct-Calls grün

### Phase 3: n8n-Workflow (nur Retention)
- Retention Track-Outcome-Node-Body komplett ersetzen:
  - `entity_id`: `$json.customer_id` → `$json.retention_id`
  - `entity_type`: `"retention"` → `"retention"` (bleibt)
  - `event_type`: `"outcome_tracked"` → `"pipeline.routed"`
  - `payload`: `retention_id` mit reinnehmen
- Offer-Workflow: alle `offer_trigger_id`-Refs → `offer_id` (nur falls n8n diese Felder referenziert)
- Workflow-Snapshots erneut committen
- E2E-Retention-Test analog zur heutigen Session

### Phase 4: Historische Audit-Daten — Cleanup
```sql
-- Lead-Drift-Test-Rows
DELETE FROM pipeline_events
WHERE entity_type = 'unknown' OR event_type = 'pipeline_event';

-- Retention-Regression-Rows (entity_id ist customer_id statt Business-Key)
DELETE FROM pipeline_events
WHERE pipeline = 'retention'
  AND entity_id LIKE 'CUST-%';
```

---

## Verification Queries

Nach Phase 2 müssen alle vier Queries Treffer liefern:

```sql
-- 1. Tabellen-Namen
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
-- Erwartet: claims, leads, offers, retentions, pipeline_events

-- 2. Business-Key-Spalten
SELECT table_name, column_name FROM information_schema.columns
WHERE table_schema = 'public' AND column_name IN
  ('lead_id', 'claim_id', 'offer_id', 'retention_id');
-- Erwartet: 4 Rows, eine pro Tabelle

-- 3. Pipeline-Wert-Konsistenz
SELECT DISTINCT pipeline FROM pipeline_events;
-- Erwartet: nur 'lead', 'claim', 'offer', 'retention'

-- 4. Event-Type-Whitelist
SELECT DISTINCT event_type FROM pipeline_events;
-- Erwartet: nur 'agent_processed', 'pipeline.routed', 'human_review'
-- (kein 'pipeline_event', kein 'outcome_tracked')
```

Nach Phase 3 zusätzlich pro Pipeline ein E2E-Trigger:

```sql
-- Audit-Event muss zur fachlichen Row joinbar sein
SELECT pe.event_type, pe.entity_id, r.retention_id, r.churn_score
FROM pipeline_events pe
JOIN retentions r ON r.retention_id = pe.entity_id
WHERE pe.created_at > now() - interval '5 minutes';
-- Erwartet: ≥ 2 Rows (agent_processed + pipeline.routed) pro Trigger
```

---

## Consequences

### Positive
- Audit-Trail ist 1:1 joinbar zur fachlichen Tabelle (entity_id ↔ business_key)
- KPI-Dashboards funktionieren ohne Pipeline-spezifische Sonderlocken
- Onboarding neuer Pipelines (z.B. zweite Industry) hat klares Pattern
- ADR ist als CAS-Thesis-Material verwendbar (zeigt reflektierte Engineering-Praxis)

### Negative
- Migration berührt Backend (3 Pipelines: Retention/Offer/Claims), DB (Renames + UPDATE)
  und einen n8n-Workflow (Retention)
- Revidierter Aufwand: 1–2 Stunden konzentrierte Arbeit
- Kurzes Deployment-Window in Phase 2 (Backend down 1–3 Min)
- ~6 historische Audit-Rows werden in Phase 4 gelöscht (Test-Daten, kein Verlust)

### Neutral
- Keine API-Breaking-Changes für externe Konsumenten — n8n ist der einzige
  Konsument und wird in Phase 3 mit-migriert.

---

## Resolved Decisions (Open Questions)

1. **Backwards-Compat-Layer im Backend** — *Resolved: Hard-Cut.*
   n8n ist der einzige Konsument der API. Backwards-Compat-Aliase
   würden Code-Komplexität ohne Nutzen einführen.

2. **Historische Audit-Daten** — *Resolved: Option A (löschen).*
   Betroffen sind nur Test-Rows (3 Lead-Drift-Rows + Retention-Regression-Rows
   der letzten 24h, alle aus E2E-Verifikations-Sessions). Cleanup-SQL ist Teil von Phase 4.

3. **Lead-`unknown`-Drift Quelle** — *Resolved: dormant.*
   Recency-Check (2026-04-21) zeigte: 3 Test-Rows von 2026-04-16 bis
   2026-04-19, alle mit leeren Payloads. Aktueller Lead-Workflow schreibt
   keine Drift-Events mehr. Kein Code-Fix nötig, nur Cleanup in Phase 4.

---

## References

- Tech-Debt Item #1 (`routed_at` Konsistenz)
- Tech-Debt Item #7 (Retention Business-Key)
- Tech-Debt Item #9 (Enum-ADR / ADR-001)
- Discovery-Session 2026-04-21 (Retention E2E-Verifikation)
