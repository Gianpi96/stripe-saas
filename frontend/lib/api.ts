const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// In production replace this with a real auth token resolver
function getUserId(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("user_id") ?? "demo-user-001";
}

function getUserEmail(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("user_email") ?? "demo@example.com";
}

export async function createCheckoutSession(priceId: string): Promise<{ url: string }> {
  const res = await fetch(`${API_URL}/api/payments/create-checkout-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      price_id: priceId,
      user_id: getUserId(),
      user_email: getUserEmail(),
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Errore durante la creazione della sessione di pagamento");
  }
  return res.json();
}

export async function createPortalSession(): Promise<{ url: string }> {
  const res = await fetch(`${API_URL}/api/payments/portal-session`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-user-id": getUserId(),
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Errore durante la creazione del portale");
  }
  return res.json();
}

export async function getSubscriptionStatus(): Promise<{
  has_subscription: boolean;
  status: string | null;
  plan: string | null;
  trial_end: string | null;
  current_period_end: string | null;
}> {
  const res = await fetch(`${API_URL}/api/payments/subscription-status`, {
    headers: { "x-user-id": getUserId() },
  });

  if (!res.ok) throw new Error("Errore nel recupero dello stato subscription");
  return res.json();
}
