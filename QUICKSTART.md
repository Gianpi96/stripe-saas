# StripeSaaS — Quickstart

## 1. Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Copia e compila le variabili d'ambiente
copy .env.example .env
# Edita .env con le tue chiavi Stripe, Resend, ecc.

# Avvia FastAPI
uvicorn main:app --reload --port 8000
```

## 2. Frontend setup

```bash
cd frontend
npm install

# Copia e compila le variabili d'ambiente
copy .env.local.example .env.local
# Edita .env.local con pk_test_... e i price ID

npm run dev   # http://localhost:3000
```

## 3. Celery (worker + beat per cron)

Richiede Redis in esecuzione (es. `docker run -p 6379:6379 redis`).

```bash
cd backend

# Worker (processa i task)
celery -A tasks.celery_app worker --loglevel=info

# Beat (lancia i cron job)
celery -A tasks.celery_app beat --loglevel=info
```

## 4. Stripe webhook locale

```bash
stripe listen --forward-to localhost:8000/api/webhooks/stripe
# Copia il webhook secret (whsec_...) in .env -> STRIPE_WEBHOOK_SECRET
```

## 5. Creare i prodotti Stripe (una volta sola)

```bash
# Basic $9/mese
stripe products create --name "Basic"
stripe prices create --product <product_id> --unit-amount 900 --currency usd --recurring[interval]=month

# Pro $29/mese  
stripe products create --name "Pro"
stripe prices create --product <product_id> --unit-amount 2900 --currency usd --recurring[interval]=month

# Copia i price ID in backend/.env e frontend/.env.local
```

## 6. Testare con carta Stripe test

| Scenario           | Numero carta         |
|--------------------|----------------------|
| Pagamento OK       | 4242 4242 4242 4242  |
| Autenticazione 3DS | 4000 0025 0000 3155  |
| Carta rifiutata    | 4000 0000 0000 0002  |

Scadenza: qualsiasi data futura · CVV: qualsiasi 3 cifre

## 7. Simulare fine trial con Test Clock

```bash
# Crea un Test Clock
stripe test_helpers test_clocks create --frozen-time $(date -u +%Y-%m-%dT%H:%M:%SZ)

# Avanza il clock di 14 giorni
stripe test_helpers test_clocks advance --test-clock <clock_id> \
  --frozen-time <data+14giorni>

# Il webhook customer.subscription.updated viene inviato automaticamente
# -> il DB aggiorna lo stato -> l'accesso Pro viene revocato
```

## 8. Configurare il Customer Portal (una volta sola)

Nel Stripe Dashboard → Billing → Customer Portal:
- ✅ Abilita cancellazione subscription
- ✅ Abilita cambio piano  
- ✅ Abilita aggiornamento metodo di pagamento
- Return URL: `http://localhost:3000/billing/return`

## Architettura

```
HTTP Request
    │
    ▼
FastAPI Router
    │
    ├── /api/payments/create-checkout-session  → Stripe Checkout
    ├── /api/payments/portal-session           → Customer Portal
    ├── /api/payments/subscription-status      → DB query
    └── /api/webhooks/stripe
            │ (risponde < 5s)
            ▼
        Celery Worker
            │
            ├── process_webhook_event  → aggiorna DB + log
            ├── send_*_email           → Resend con retry
            └── alert_payment_failed   → Slack + email admin

Cron (Celery Beat)
    ├── sync_all_subscriptions    → 03:00 UTC daily
    └── send_trial_expiry_reminders → 09:00 UTC daily
```

## Flusso webhook (idempotency)

```
stripe → POST /api/webhooks/stripe
    1. Verifica firma (STRIPE_WEBHOOK_SECRET)
    2. Controlla webhook_events.event_id (già processato? → 200 skip)
    3. Inserisce record con status="queued"
    4. Dispatch a Celery → risponde 200 subito
    5. Celery: elabora evento → aggiorna subscription + log
    6. Aggiorna record a status="processed"
```
