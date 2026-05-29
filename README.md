# StripeSaaS

Full-stack SaaS con billing Stripe completo. Costruito con Next.js 14 + FastAPI + SQLite + Celery + Resend.

## Stack

| Layer | Tecnologia |
|-------|-----------|
| Frontend | Next.js 14 App Router + Tailwind CSS |
| Backend | FastAPI + SQLAlchemy + SQLite |
| Pagamenti | Stripe (Checkout, Subscriptions, Customer Portal, Webhooks) |
| Code asincrono | Celery + Redis |
| Email | Resend |

## Funzionalità

- **Checkout** — Stripe Checkout Session con scadenza 30 min, metadata user_id
- **Subscription** — Piano Basic ($9/mese) e Pro ($29/mese) con 14 giorni di trial gratuito
- **Customer Portal** — Cambio piano, aggiornamento carta, cancellazione (zero codice custom)
- **Webhook** — Gestione eventi Stripe con verifica firma e idempotency
- **Email** — Welcome, conferma pagamento, avviso scadenza trial (Resend + retry esponenziale)
- **Cron** — Sincronizzazione giornaliera degli stati subscription da Stripe
- **Middleware** — Protezione endpoint Pro con controllo subscription status

## Avvio rapido

### Prerequisiti

- Python 3.10+
- Node.js 18+
- Docker (per Redis)
- Stripe CLI

### 1. Clona e configura

```bash
git clone <repo-url>
cd stripe-saas
```

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
# Compila .env con le tue chiavi
```

### 3. Frontend

```bash
cd frontend
npm install
copy .env.local.example .env.local   # Windows
# cp .env.local.example .env.local   # macOS/Linux
# Compila .env.local con le tue chiavi
```

### 4. Redis

```bash
docker run -d --name stripe-saas-redis -p 6379:6379 redis:alpine
```

### 5. Avvia tutto (4 terminali)

```bash
# Terminale 1 — Backend
cd backend && uvicorn main:app --reload --port 8000

# Terminale 2 — Frontend
cd frontend && npm run dev

# Terminale 3 — Celery worker (Windows: --pool=solo)
cd backend && .venv\Scripts\celery -A tasks.celery_app worker --loglevel=info --pool=solo

# Terminale 4 — Stripe webhook listener
stripe listen --forward-to localhost:8000/api/webhooks/stripe
# Copia il whsec_... in backend/.env -> STRIPE_WEBHOOK_SECRET
```

Apri **http://localhost:3000**

## Variabili d'ambiente

### backend/.env

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_BASIC_PRICE_ID=price_...
STRIPE_PRO_PRICE_ID=price_...

APP_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
DATABASE_URL=sqlite:///./stripe_saas.db
REDIS_URL=redis://localhost:6379/0

RESEND_API_KEY=re_...
EMAIL_FROM=noreply@tuodominio.com
EMAIL_FROM_NAME=StripeSaaS

SLACK_WEBHOOK_URL=         # opzionale — alert pagamento fallito
ALERT_EMAIL=admin@...      # opzionale
```

### frontend/.env.local

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
NEXT_PUBLIC_STRIPE_BASIC_PRICE_ID=price_...
NEXT_PUBLIC_STRIPE_PRO_PRICE_ID=price_...
```

## Creare i prodotti Stripe

```bash
# Basic $9/mese
stripe products create --name "Basic"
stripe prices create -d "product=<id>" -d "unit_amount=900" -d "currency=usd" -d "recurring[interval]=month"

# Pro $29/mese
stripe products create --name "Pro"
stripe prices create -d "product=<id>" -d "unit_amount=2900" -d "currency=usd" -d "recurring[interval]=month"
```

## Carte di test Stripe

| Scenario | Numero carta |
|----------|-------------|
| Pagamento OK | `4242 4242 4242 4242` |
| Richiede 3D Secure | `4000 0025 0000 3155` |
| Carta rifiutata | `4000 0000 0000 0002` |
| Fondi insufficienti | `4000 0000 0000 9995` |

Scadenza: qualsiasi data futura · CVV: qualsiasi 3 cifre

## Architettura

```
Browser (Next.js)
    │
    ├── GET  /pricing              → Pagina piani Basic / Pro
    ├── GET  /success?session_id=  → Conferma pagamento
    ├── GET  /cancel               → Pagamento annullato
    ├── GET  /dashboard/billing    → Stato subscription + portal button
    └── GET  /billing/return       → Return URL dal Customer Portal
    
    │ fetch
    ▼
FastAPI (localhost:8000)
    │
    ├── POST /api/payments/create-checkout-session
    ├── POST /api/payments/portal-session
    ├── GET  /api/payments/subscription-status
    ├── GET  /api/pro-feature      ← protetto da require_pro_subscription
    └── POST /api/webhooks/stripe
            │
            │ (risponde < 5s, processing asincrono)
            ▼
        Celery Worker (Redis broker)
            │
            ├── process_webhook_event
            │     ├── checkout.session.completed → crea Subscription in DB
            │     ├── customer.subscription.updated → aggiorna stato
            │     ├── customer.subscription.deleted → stato = canceled
            │     ├── invoice.payment_failed → stato = past_due + alert
            │     └── invoice.payment_succeeded → email conferma
            │
            └── email_tasks (Resend, retry 2^n)
                  ├── send_welcome_email
                  ├── send_payment_confirmed_email
                  ├── send_trial_expiring_email
                  └── alert_payment_failed

Celery Beat (cron)
    ├── 03:00 UTC — sync_all_subscriptions (reconcilia DB con Stripe)
    └── 09:00 UTC — send_trial_expiry_reminders (email 3gg prima fine trial)
```

## Sicurezza

- **Webhook**: verifica firma HMAC con `stripe.Webhook.construct_event`
- **Idempotency**: tabella `webhook_events` con `event_id` unico — eventi duplicati ignorati
- **Subscription gate**: middleware `require_pro_subscription` / `require_active_subscription`
- **No card data**: nessun dato di carta transitato o loggato dal backend
- **Checkout expiry**: sessione scade dopo 30 minuti (`expires_at`)

## Database

```
users                    subscriptions              webhook_events
─────────────────        ──────────────────────     ──────────────────
id (PK)                  id (PK)                    id (PK)
email                    user_id (FK)               event_id (UNIQUE)
stripe_customer_id       stripe_subscription_id     event_type
created_at               stripe_customer_id         status
                         plan                       payload (JSON)
                         status                     processed_at
                         trial_end
                         current_period_end         subscription_status_logs
                                                    ────────────────────────
                                                    subscription_id (FK)
                                                    old_status
                                                    new_status
                                                    reason
                                                    changed_at
```

## Test di sicurezza

```bash
# Firma webhook invalida → 400
curl -X POST http://localhost:8000/api/webhooks/stripe \
  -H "stripe-signature: fake" -d "payload"

# Endpoint Pro senza subscription → 403
curl http://localhost:8000/api/pro-feature \
  -H "x-user-id: utente-senza-sub"

# Price ID invalido → 400
curl -X POST http://localhost:8000/api/payments/create-checkout-session \
  -H "Content-Type: application/json" \
  -d '{"price_id":"price_FAKE","user_id":"u1","user_email":"x@x.com"}'
```

## Licenza

MIT
