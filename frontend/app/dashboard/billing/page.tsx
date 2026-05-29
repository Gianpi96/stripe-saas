"use client";

import { useEffect, useState } from "react";
import { createPortalSession, getSubscriptionStatus } from "@/lib/api";
import Link from "next/link";

type SubStatus = {
  has_subscription: boolean;
  status: string | null;
  plan: string | null;
  trial_end: string | null;
  current_period_end: string | null;
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  active:    { label: "Attivo",         color: "bg-green-100 text-green-700" },
  trialing:  { label: "Trial in corso", color: "bg-blue-100 text-blue-700" },
  past_due:  { label: "Pagamento scaduto", color: "bg-amber-100 text-amber-700" },
  canceled:  { label: "Cancellato",     color: "bg-gray-100 text-gray-600" },
  unpaid:    { label: "Non pagato",     color: "bg-red-100 text-red-700" },
};

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("it-IT", {
    day: "numeric", month: "long", year: "numeric",
  });
}

export default function BillingPage() {
  const [sub, setSub] = useState<SubStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSubscriptionStatus()
      .then(setSub)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function openPortal() {
    setPortalLoading(true);
    setError(null);
    try {
      const { url } = await createPortalSession();
      window.location.href = url;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Errore nel caricamento del portale");
      setPortalLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Fatturazione</h1>
          <p className="text-gray-500 mt-1">Gestisci il tuo piano e i metodi di pagamento</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 mb-6">
            {error}
          </div>
        )}

        {loading ? (
          <div className="bg-white rounded-2xl shadow p-8 animate-pulse">
            <div className="h-5 bg-gray-200 rounded w-1/3 mb-4" />
            <div className="h-4 bg-gray-200 rounded w-2/3 mb-2" />
            <div className="h-4 bg-gray-200 rounded w-1/2" />
          </div>
        ) : !sub?.has_subscription ? (
          <div className="bg-white rounded-2xl shadow p-8 text-center">
            <div className="w-16 h-16 bg-violet-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Nessuna subscription attiva</h2>
            <p className="text-gray-500 mb-6">Scegli un piano per iniziare il trial gratuito di 14 giorni.</p>
            <Link
              href="/pricing"
              className="inline-block bg-violet-600 text-white py-3 px-8 rounded-xl font-semibold hover:bg-violet-700 transition-colors"
            >
              Scegli un piano
            </Link>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Current plan card */}
            <div className="bg-white rounded-2xl shadow p-8">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h2 className="text-lg font-bold text-gray-900">Piano corrente</h2>
                  <p className="text-gray-500 text-sm mt-0.5">I dettagli della tua subscription</p>
                </div>
                {sub.status && STATUS_LABELS[sub.status] && (
                  <span className={`text-sm font-semibold px-3 py-1 rounded-full ${STATUS_LABELS[sub.status].color}`}>
                    {STATUS_LABELS[sub.status].label}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-xl p-4">
                  <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Piano</p>
                  <p className="font-bold text-gray-900 capitalize text-lg">{sub.plan ?? "—"}</p>
                </div>
                <div className="bg-gray-50 rounded-xl p-4">
                  <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
                    {sub.status === "trialing" ? "Fine trial" : "Prossimo rinnovo"}
                  </p>
                  <p className="font-bold text-gray-900">
                    {sub.status === "trialing"
                      ? formatDate(sub.trial_end)
                      : formatDate(sub.current_period_end)}
                  </p>
                </div>
              </div>

              {sub.status === "past_due" && (
                <div className="mt-4 bg-amber-50 border border-amber-200 rounded-xl p-4">
                  <p className="text-amber-800 text-sm font-medium">
                    ⚠️ C'è un problema con il tuo pagamento. Aggiorna il metodo di pagamento per mantenere l'accesso.
                  </p>
                </div>
              )}
            </div>

            {/* Portal CTA */}
            <div className="bg-white rounded-2xl shadow p-8">
              <h2 className="text-lg font-bold text-gray-900 mb-2">Gestisci la tua subscription</h2>
              <p className="text-gray-500 text-sm mb-6">
                Tramite il portale Stripe puoi cambiare piano, aggiornare la carta di credito o cancellare la subscription.
              </p>
              <button
                onClick={openPortal}
                disabled={portalLoading}
                className="w-full bg-violet-600 text-white py-3.5 rounded-xl font-semibold hover:bg-violet-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {portalLoading ? (
                  <>
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Apertura portale...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Gestisci Subscription
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
