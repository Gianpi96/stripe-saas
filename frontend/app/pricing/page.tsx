"use client";

import { useState } from "react";
import { createCheckoutSession } from "@/lib/api";

const PLANS = [
  {
    id: "basic",
    name: "Basic",
    price: 9,
    priceId: process.env.NEXT_PUBLIC_STRIPE_BASIC_PRICE_ID ?? "",
    description: "Per individui e piccoli team",
    features: [
      "Fino a 3 progetti",
      "5 GB di storage",
      "Supporto email",
      "API access base",
    ],
    cta: "Inizia il trial Basic",
    highlight: false,
  },
  {
    id: "pro",
    name: "Pro",
    price: 29,
    priceId: process.env.NEXT_PUBLIC_STRIPE_PRO_PRICE_ID ?? "",
    description: "Per team in crescita",
    features: [
      "Progetti illimitati",
      "50 GB di storage",
      "Supporto prioritario 24/7",
      "API access completo",
      "Analytics avanzate",
      "Integrazioni Pro",
    ],
    cta: "Passa a Pro",
    highlight: true,
  },
];

export default function PricingPage() {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleCheckout(priceId: string, planId: string) {
    if (!priceId) {
      setError("Price ID non configurato. Imposta NEXT_PUBLIC_STRIPE_*_PRICE_ID nel .env.local");
      return;
    }
    setLoading(planId);
    setError(null);
    try {
      const { url } = await createCheckoutSession(priceId);
      window.location.href = url;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Errore sconosciuto");
      setLoading(null);
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-violet-50 to-indigo-50 py-20 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <span className="inline-block bg-violet-100 text-violet-700 text-sm font-semibold px-4 py-1.5 rounded-full mb-4">
            14 giorni di trial gratuito
          </span>
          <h1 className="text-5xl font-bold text-gray-900 mb-4 tracking-tight">
            Scegli il piano giusto
          </h1>
          <p className="text-xl text-gray-600">
            Nessuna carta richiesta durante il trial. Disdici quando vuoi.
          </p>
        </div>

        {/* Error banner */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 mb-8 text-center">
            {error}
          </div>
        )}

        {/* Plans grid */}
        <div className="grid md:grid-cols-2 gap-8">
          {PLANS.map((plan) => (
            <div
              key={plan.id}
              className={`relative rounded-2xl p-8 flex flex-col ${
                plan.highlight
                  ? "bg-violet-600 text-white shadow-2xl shadow-violet-200 scale-105"
                  : "bg-white text-gray-900 shadow-lg"
              }`}
            >
              {plan.highlight && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="bg-amber-400 text-amber-900 text-xs font-bold px-4 py-1.5 rounded-full uppercase tracking-wide">
                    Più popolare
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h2 className="text-2xl font-bold mb-1">{plan.name}</h2>
                <p className={`text-sm ${plan.highlight ? "text-violet-200" : "text-gray-500"}`}>
                  {plan.description}
                </p>
              </div>

              <div className="mb-8">
                <span className="text-5xl font-extrabold">${plan.price}</span>
                <span className={`ml-2 ${plan.highlight ? "text-violet-200" : "text-gray-500"}`}>
                  /mese
                </span>
              </div>

              <ul className="space-y-3 mb-10 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5">
                    <svg
                      className={`w-5 h-5 flex-shrink-0 mt-0.5 ${
                        plan.highlight ? "text-violet-200" : "text-violet-600"
                      }`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className={plan.highlight ? "text-violet-100" : "text-gray-700"}>{f}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handleCheckout(plan.priceId, plan.id)}
                disabled={loading !== null}
                className={`w-full py-4 rounded-xl font-bold text-lg transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed ${
                  plan.highlight
                    ? "bg-white text-violet-600 hover:bg-violet-50 active:scale-95"
                    : "bg-violet-600 text-white hover:bg-violet-700 active:scale-95"
                }`}
              >
                {loading === plan.id ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Caricamento...
                  </span>
                ) : (
                  plan.cta
                )}
              </button>
            </div>
          ))}
        </div>

        {/* Trust badges */}
        <div className="mt-16 flex flex-wrap justify-center gap-8 text-gray-400 text-sm">
          <span>🔒 Pagamenti sicuri con Stripe</span>
          <span>✅ Disdici in qualsiasi momento</span>
          <span>🎁 14 giorni gratis, nessuna carta richiesta</span>
        </div>
      </div>
    </main>
  );
}
