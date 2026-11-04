# stripe-saas

[![Build](https://img.shields.io/github/actions/workflow/status/Gianpi96/stripe-saas/ci.yml?branch=main&label=build&style=flat-square)](https://github.com/Gianpi96/stripe-saas/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Deploy with Vercel](https://img.shields.io/badge/deploy-Vercel-black?style=flat-square&logo=vercel)](https://vercel.com/new/clone?repository-url=https://github.com/Gianpi96/stripe-saas)

**A complete SaaS billing system — subscriptions, webhooks, customer portal, and async processing, all wired correctly.**

*English summary: Stripe subscriptions (Basic and Pro plans with a 14-day trial), signature-verified and idempotent webhooks processed asynchronously with Celery and Redis, customer portal, transactional emails via Resend, a daily sync job, and subscription-based route protection. FastAPI backend, Next.js 14 frontend. The documentation below is in Italian.*

---

## What you get

- **Stripe subscriptions pronte all'uso** — piani Basic ($9/mese) e Pro ($29/mese) con 14 giorni di trial gratuito. Checkout con scadenza di 30 minuti per evitare sessioni zombie.
- **Webhook con idempotency** — ogni evento Stripe viene verificato con firma HMAC e salvato con ID univoco prima di qualsiasi elaborazione. Lo stesso evento può arrivare 10 volte: viene processato una volta sola.
- **Celery per il processing asincrono** — i webhook non bloccano la risposta a Stripe. Gli eventi vengono messi in coda Redis e processati da worker separati, quindi la risposta a Stripe è immediata. Se la coda non è raggiungibile il webhook risponde `503` e segna l'evento come `failed`: Stripe riprova e il nuovo tentativo viene elaborato (non scartato come duplicato), così nessun evento va perso.
- **Customer portal integrato** — il cliente gestisce piano, carta, e cancellazione in autonomia tramite il portale ufficiale Stripe. Le operazioni di billing non richiedono intervento manuale.
- **Email transazionali** — benvenuto, conferma pagamento, reminder scadenza trial, notifica pagamento fallito. Tutte via Resend con template HTML.
- **Cron job giornaliero** — sincronizza lo stato degli abbonamenti da Stripe ogni notte e invia reminder ai trial in scadenza nelle prossime 24 ore.
- **Protezione route basata su subscription** — il middleware FastAPI blocca l'accesso alle funzionalità Pro se l'abbonamento non è attivo. Nessun check manuale nei singoli endpoint.
- **Zero dati carta nel backend** — Stripe gestisce tutto il sensitive data. Il backend non tocca mai numeri di carta o CVV.

---

## Quick start

Requisiti (versioni usate dalla CI): Python 3.12, Node.js 20, Redis (per Celery) e la [Stripe CLI](https://stripe.com/docs/stripe-cli). Il database di default è SQLite, quindi non serve installare altro.

```bash
# 1. Clona e configura
git clone https://github.com/Gianpi96/stripe-saas
cd stripe-saas
cp backend/.env.example backend/.env             # inserisci le chiavi Stripe e Resend
cp frontend/.env.local.example frontend/.env.local

# 2. Avvia Redis (broker di Celery)
docker run -d --name stripe-saas-redis -p 6379:6379 redis:7

# 3. Backend (dalla cartella backend/)
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 4. In altri terminali, sempre da backend/:
celery -A tasks.celery_app worker --loglevel=info   # elabora i webhook e le email
celery -A tasks.celery_app beat --loglevel=info     # job giornalieri (sync abbonamenti, reminder trial)

# 5. Frontend
cd ../frontend && npm install && npm run dev   # da backend/ → frontend/
```

Per ricevere i webhook Stripe in locale:

```bash
stripe listen --forward-to localhost:8000/api/webhooks/stripe
```

Altri dettagli passo passo in [QUICKSTART.md](QUICKSTART.md).


---

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Example | Dove trovarla |
|---|---|---|---|
| `DATABASE_URL` | ✅ | `sqlite:///./app.db` | SQLite locale o PostgreSQL |
| `REDIS_URL` | ✅ | `redis://localhost:6379` | Docker locale o Upstash |
| `SECRET_KEY` | ✅ | `openssl rand -hex 32` | Generata localmente |
| `STRIPE_SECRET_KEY` | ✅ | `sk_test_xxxxxxxxxxxx` | Stripe Dashboard → API keys |
| `STRIPE_WEBHOOK_SECRET` | ✅ | `whsec_xxxxxxxxxxxx` | Stripe Dashboard → Webhooks |
| `STRIPE_BASIC_PRICE_ID` | ✅ | `price_xxxxxxxxxxxx` | Stripe Dashboard → Products |
| `STRIPE_PRO_PRICE_ID` | ✅ | `price_xxxxxxxxxxxx` | Stripe Dashboard → Products |
| `RESEND_API_KEY` | ✅ | `re_xxxxxxxxxxxx` | resend.com/api-keys |
| `FRONTEND_URL` | ✅ | `http://localhost:3000` | URL del frontend |

### Frontend (`frontend/.env.local`)

| Variable | Required | Example |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | ✅ | `http://localhost:8000` |
| `NEXTAUTH_SECRET` | ✅ | `openssl rand -base64 32` |
| `NEXTAUTH_URL` | ✅ | `http://localhost:3000` |

---

## Architettura

```
stripe-saas/
├── backend/                    # FastAPI application
│   ├── main.py
│   ├── config.py, database.py, models.py
│   ├── routers/
│   │   ├── payments.py         # Checkout, customer portal, stato abbonamento
│   │   └── webhooks.py         # Webhook Stripe (firma, idempotenza, coda)
│   ├── tasks/
│   │   ├── celery_app.py       # Configurazione Celery e schedule giornaliero
│   │   ├── sync_tasks.py       # Elaborazione eventi, sync abbonamenti, reminder trial
│   │   └── email_tasks.py      # Email transazionali (Resend)
│   ├── middleware/
│   │   └── subscription.py     # Protezione route Pro
│   ├── templates/              # Template HTML delle email
│   └── tests/                  # Test su pagamenti, webhook, sicurezza
│
├── frontend/                   # Next.js 14 App Router
│   └── app/
│       ├── pricing/            # Pagina piani con checkout
│       ├── dashboard/billing/  # Stato abbonamento e portale
│       └── success, cancel, billing/return
│
└── .github/workflows/          # CI
```

**Flusso webhook Stripe:**

```
Stripe → POST /api/webhooks/stripe
  → Verifica firma HMAC (scarta richieste non firmate)
  → Controlla event_id nel database → se già presente (e non fallito), rispondi 200 e stop
  → Salva l'evento, poi mettilo in coda Celery (coda non disponibile → 503, Stripe riprova)
  → Rispondi 200 a Stripe immediatamente
  → Worker Celery processa l'evento:
      → Aggiorna stato subscription nel database
      → Invia email appropriata
      → Segna evento come processed
```

---

## Piani e prezzi configurati

| Piano | Prezzo | Trial | Funzionalità |
|---|---|---|---|
| Basic | $9/mese | 14 giorni | Funzionalità base |
| Pro | $29/mese | 14 giorni | Tutto + funzionalità Pro |

I prezzi si configurano in Stripe Dashboard e si aggiungono alle env vars. Per cambiarli non tocchi il codice.

---

## Why this stack

**Celery + Redis per i webhook invece di processing sincrono** — Stripe richiede una risposta entro 30 secondi. Se il processing (database + email) supera quel limite, Stripe riprova il webhook e rischi di processarlo due volte. Celery riceve il webhook, lo mette in coda in millisecondi, e risponde subito. Il worker processa senza pressione di timeout.

**SQLite in sviluppo, PostgreSQL in produzione** — SQLAlchemy astrae il database. In locale SQLite non richiede setup. In produzione si cambia solo la `DATABASE_URL`. Zero modifiche al codice.

**Resend invece di SMTP** — configurare un server SMTP per le email transazionali richiede gestione di reputazione, SPF/DKIM, e rate limiting. Resend gestisce tutto questo. Il free tier copre 3.000 email/mese — sufficiente per la fase early-stage.

**Idempotency via tabella database** — salvare l'`event_id` nel database prima del processing garantisce che anche in caso di crash e riavvio del worker, l'evento non venga riprocessato. Soluzioni in-memory (Redis key con TTL) perdono lo stato al riavvio.

---

## License

MIT
