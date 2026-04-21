# PHASE 2 RUNBOOK — Backend + DB Migration

ADR-002 Implementation, Branch `refactor/adr-002-naming`.
Geschätzter Aufwand: **1–2 Stunden**, sequenziell, keine Schritte überspringen.

---

## Pre-Flight Checks

Bevor du loslegst — diese sechs Checks sollten alle ✅ sein:

- [ ] `git branch` zeigt `* refactor/adr-002-naming` (du bist auf dem Branch)
- [ ] `git status` ist sauber (keine uncommitted Änderungen außer dem ADR von Phase 1)
- [ ] Supabase SQL Editor offen, eingeloggt
- [ ] Render Dashboard offen (für Deploy-Trigger + Log-Monitoring)
- [ ] n8n Cloud — keine Pipelines werden während des Windows manuell getriggert
- [ ] Mental: 1-2h fokussierte Zeit eingeplant

---

## Master-Reihenfolge

```
Schritt 1: Code-Änderungen lokal vorbereiten   (~30 Min)
Schritt 2: DB-Migration in Supabase            (~5 Min)
Schritt 3: Lokal Import-Test                    (~2 Min)
Schritt 4: Commit + Merge to main              (~3 Min)
Schritt 5: Render Auto-Deploy abwarten         (~15 Min)
Schritt 6: Production Smoke-Test               (~10 Min)
```

**Outage-Window** für das Backend: zwischen Schritt 2 (DB-Schema neu) und Schritt 5
abgeschlossen (Backend mit neuem Code deployed). In dieser Zeit (~20 Min)
gibt das Backend 500-Errors für jeden Retention/Offer-Trigger. Da kein User
außer dir triggert, ist das unkritisch — aber **keine Test-Trigger feuern** in
diesem Window!

---

## Schritt 1 — Code-Änderungen vorbereiten

Files in **dieser Reihenfolge** ersetzen (jede ist Source-of-Truth für die nächste):

| # | Datei | Was ändert sich |
|---|---|---|
| 1.1 | `db/models.py` | Class-Rename `RetentionEvent`→`Retention`, Spalten-Renames, Mojibake-Cleanup |
| 1.2 | `db/repositories.py` | Alle Refs auf neue Class/Spalten, Mojibake-Cleanup |
| 1.3 | `agents/retention_agent.py` | **Bug-Fix `entity_id`**, Pydantic-Rename, Fallback-Generator |
| 1.4 | `agents/offer_agent.py` | Pydantic-Rename, Spalten-Refs, Mojibake-Cleanup |
| 1.5 | `api/audit_routes.py` | API-Path-Renames, ENTITY_TO_PIPELINE-Mapper-Cleanup |

**Nach jeder Datei** den Quick-Import-Test:

```powershell
python -c "import ast; ast.parse(open('db/models.py').read()); print('syntax OK')"
```

Erwartet: `syntax OK`. Wenn Syntax-Error → Datei nochmal kopieren.

**WICHTIG:** Tests gegen die DB werden bis Schritt 2 fehlschlagen, weil das
DB-Schema noch alt ist. Das ist normal. Nur Syntax + Import prüfen.

---

## Schritt 2 — DB-Migration in Supabase

1. Supabase SQL Editor → neuer Tab: "Phase 2 Migration"
2. Inhalt von `phase-2-migration.sql` reinkopieren
3. **WICHTIG:** Das Script hat **zwei Blocks** — nicht alles auf einmal ausführen!
   - **Block 1:** `ALTER TYPE ... ADD VALUE` (kann nicht in Transaction laufen)
   - **Block 2:** Alle Renames + UPDATEs (atomar in einer Transaction)
4. Block 1 markieren → Run
5. Verifikation: `SELECT enum_range(NULL::pipeline_type);` → muss `'claim'` enthalten
6. Block 2 markieren → Run
7. **Verifikations-Queries 1-4 durchgehen** (im SQL-File dokumentiert)
8. Wenn auch nur EINE Verifikation fehlschlägt → siehe **Rollback** unten

---

## Schritt 3 — Lokal Import-Test

```powershell
python -c "from db.models import Retention, Offer, Lead, Claim, PipelineEvent; print('models OK')"
python -c "from db.repositories import RetentionRepository, OfferRepository; print('repos OK')"
python -c "from agents.retention_agent import RetentionInput; print('retention agent OK')"
python -c "from agents.offer_agent import OfferInput; print('offer agent OK')"
python -c "from api.audit_routes import register_routes; print('routes OK')"
```

Alle 5 müssen `OK` printen. Wenn ein Import bricht → Datei reviewen, kein Push.

---

## Schritt 4 — Commit + Merge to main

```powershell
cd C:\Users\Public\Projects\insure.ai
git status
git add -A
git diff --stat --cached
```

**Sanity check:** Diff-Stat sollte zeigen:
- `db/models.py`               | XX +/- 
- `db/repositories.py`         | XX +/-
- `agents/retention_agent.py`  | XX +/-
- `agents/offer_agent.py`      | XX +/-
- `api/audit_routes.py`        | XX +/-

5 Files, keine zusätzlichen.

Dann commit:

```powershell
git commit -m "refactor(adr-002): pipeline entity & audit naming consistency" -m "Implements ADR-002 Phase 2 (Backend + DB). - Rename retention_events to retentions, retention_event_id to retention_id. - Rename offer_trigger_id to offer_id (table column + API paths). - PIPELINE_ENUM: add 'claim' value, migrate pipeline_events rows. - Fix retention_agent entity_id bug (was customer_id, now retention_id). - Add Backend fallback generator for retention_id when n8n omits it. - Encoding cleanup (Mojibake to proper UTF-8 in 5 files). - Remove deprecated ENTITY_TO_PIPELINE absorber for claim/claims."

git push origin refactor/adr-002-naming
```

Dann Merge to main (löst Render Auto-Deploy aus):

```powershell
git checkout main
git merge refactor/adr-002-naming --no-ff
git push origin main
```

---

## Schritt 5 — Render Deploy + Wait

Render Auto-Deploy von main startet automatisch. ~15 Min Latenz.

Polling-Loop für Verifikation:

```powershell
$attempts = 0
while ($attempts -lt 40) {
    Start-Sleep -Seconds 30
    try {
        $r = Invoke-RestMethod -Uri "https://insure-ai-wql4.onrender.com/health" -TimeoutSec 10
        Write-Host "[$([DateTime]::Now.ToString('HH:mm:ss'))] $($r | ConvertTo-Json -Compress)"
        if ($r.status -eq "ok") {
            Write-Host "✓ Backend is UP" -ForegroundColor Green
            break
        }
    } catch {
        Write-Host "[$([DateTime]::Now.ToString('HH:mm:ss'))] Still deploying..."
    }
    $attempts++
}
```

Erwartet: irgendwann kommt `{"status":"ok","agents":3,"db":"postgresql"}` zurück
mit dem neuen Commit-SHA von oben.

---

## Schritt 6 — Production Smoke-Test

Direkter Agent-Call gegen Render — kein n8n im Spiel:

```powershell
$body = @{
    customer_id    = "CUST-9001"
    trigger_type   = "login_anomaly"
    trigger_detail = "Phase 2 verification trigger"
} | ConvertTo-Json

$result = Invoke-RestMethod -Uri "https://insure-ai-wql4.onrender.com/agent/retention" `
    -Method POST -Body $body -ContentType "application/json" -TimeoutSec 60

$result | ConvertTo-Json
```

Erwartet: HTTP 200 mit churn_score, recommended_route, etc.

**DB-Verifikation** (in Supabase):

```sql
-- 1. Neue Retention-Row mit auto-generierter retention_id
SELECT retention_id, customer_id, churn_score, final_route, triggered_at
FROM retentions
WHERE triggered_at > now() - interval '5 minutes'
ORDER BY triggered_at DESC LIMIT 3;

-- 2. Audit-Event ist zur Retention-Row joinbar (DAS ist der eigentliche Win)
SELECT pe.event_type, pe.entity_id, pe.created_at,
       r.retention_id, r.churn_score
FROM pipeline_events pe
JOIN retentions r ON r.retention_id = pe.entity_id
WHERE pe.created_at > now() - interval '5 minutes'
ORDER BY pe.created_at DESC LIMIT 5;
```

**Phase 2 GRÜN wenn:**
- ✅ Direct-Call returnt 200 mit gültigem Response
- ✅ Q1 zeigt neue Row mit `retention_id` befüllt (nicht NULL)
- ✅ Q2 zeigt JOIN-Match zwischen `pipeline_events.entity_id` und `retentions.retention_id`

---

## Rollback Plan

Wenn nach Schritt 2 ein Verifikations-Query fehlschlägt:

```sql
-- Reverse Renames (atomar)
BEGIN;

ALTER TABLE retentions RENAME TO retention_events;
ALTER TABLE retention_events RENAME COLUMN retention_id TO retention_event_id;
ALTER TABLE offers RENAME COLUMN offer_id TO offer_trigger_id;

UPDATE pipeline_events SET pipeline = 'claims' WHERE pipeline = 'claim';

COMMIT;
```

Note: `ALTER TYPE ... ADD VALUE` ist **nicht reversibel** in Postgres
(kein `DROP VALUE`). Der `'claim'`-Wert bleibt im Enum, wird aber von keinen
Rows mehr referenziert. Harmlos.

Code-Rollback:

```powershell
git checkout main
git revert HEAD --no-edit
git push origin main
```

(Niemals `git push --force` auf main!)

---

## Was nach Phase 2 noch offen ist

- **Phase 3:** n8n Retention-Workflow Track-Outcome-Body anpassen (Spalten-Refs +
  `event_type`-Korrektur). Plus Offer-Workflow falls dort `offer_trigger_id`
  noch direkt referenziert wird (Field-Refs prüfen).
- **Phase 4:** Cleanup historischer Drift-Rows (kleines DELETE-Script).

Beides in Folge-Sessions, keine Eile.
