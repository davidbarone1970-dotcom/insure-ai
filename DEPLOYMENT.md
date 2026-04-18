# INSURE.AI — Railway Deployment Guide

## Voraussetzung: Dateien ins Repo pushen

```bash
# Im lokalen insure-ai Verzeichnis:
cp railway.toml Procfile runtime.txt nixpacks.toml ./
git add railway.toml Procfile runtime.txt nixpacks.toml
git commit -m "chore: add Railway deployment config"
git push origin master
```

---

## Railway Setup (einmalig, ~10 Minuten)

### 1. Account & Projekt anlegen
- https://railway.app → "Start a New Project"
- "Deploy from GitHub repo" → `davidbarone1970-dotcom/insure-ai` auswählen
- Branch: `master`

### 2. Environment Variables setzen
Railway Dashboard → Projekt → **Variables** → folgende eintragen:

| Variable | Wert |
|---|---|
| `DATABASE_URL` | `postgresql://...` (Supabase Connection String, Port 5432) |
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `SSL_CERT_FILE` | *(leer lassen — Railway hat System-CA)* |
| `DB_ECHO` | `false` |
| `ENVIRONMENT` | `production` |

> **Wichtig:** Supabase Connection String für Session Mode (Port 5432), nicht Transaction Mode (Port 6543).
> Format: `postgresql://postgres.[project-ref]:[password]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres`

### 3. Domain generieren
Railway Dashboard → **Settings** → **Networking** → "Generate Domain"
→ Du bekommst eine URL wie: `https://insure-ai-production.up.railway.app`

### 4. Deployment verifizieren
```bash
# Health Check
curl https://insure-ai-production.up.railway.app/health

# Lead Agent testen (Beispiel)
curl -X POST https://insure-ai-production.up.railway.app/api/v1/leads/process \
  -H "Content-Type: application/json" \
  -d '{"name": "Test GmbH", "segment": "KMU", "source": "web"}'
```

---

## n8n anpassen

Nach dem Deployment: In n8n alle HTTP Request Nodes von `ngrok`-URL auf Railway-URL umstellen.

**Suche & Ersetze in n8n:**
- Alt: `https://xxxx-xx-xx-xxx.ngrok-free.app`
- Neu: `https://insure-ai-production.up.railway.app`

---

## Kosten

| Plan | Preis | Ausreichend für |
|---|---|---|
| Starter | $5/Monat | Showcase / MVP ✓ |
| Pro | $20/Monat | Production mit mehr RAM |

Railway Starter = 512 MB RAM, 1 vCPU — reicht für den FastAPI Agent Stack.

---

## Nächste Schritte nach Deployment

1. ✅ Railway URL in n8n eintragen
2. Claims Pipeline verdrahten
3. Retention Pipeline verdrahten  
4. Offer Pipeline verdrahten
5. HITL Dashboard → `/api/v1/review/queue`
6. KPI Dashboard → `/api/v1/kpi/today`
