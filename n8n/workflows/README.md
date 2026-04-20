# n8n Workflows

Snapshot-Export der INSURE.AI n8n Cloud-Workflows.

**Instance:** jeegrobot1970.app.n8n.cloud
**Backend:** https://insure-ai-wql4.onrender.com

## Files

| File | Pipeline | Webhook Path |
|---|---|---|
| lead.json | Lead Intelligence | /webhook/lead |
| claims.json | Claims Assessment | /webhook/claim |
| retention.json | Customer Retention | /webhook/retention |
| offer.json | Offer Management | /webhook/offer |

## Re-Export

In n8n Cloud: Workflow öffnen → Menü (⋯) oben rechts → Download.
Die JSONs enthalten Credentials-References (nicht die Credentials selbst),
sind also safe zum Committen.

## Re-Import

In n8n Cloud: + New Workflow → Import from File → JSON auswählen.
Credentials müssen nach dem Import neu verknüpft werden.
