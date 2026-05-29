"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";

function SuccessContent() {
  const params = useSearchParams();
  const sessionId = params.get("session_id");

  return (
    <main className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-10 text-center">
        <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg className="w-10 h-10 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>

        <h1 className="text-3xl font-bold text-gray-900 mb-3">Pagamento riuscito!</h1>
        <p className="text-gray-600 mb-8 leading-relaxed">
          Il tuo abbonamento è attivo. Riceverai una email di conferma a breve.
          Il tuo trial di 14 giorni è già iniziato.
        </p>

        {sessionId && (
          <div className="bg-gray-50 rounded-xl p-4 mb-8 text-left">
            <p className="text-xs text-gray-400 font-mono uppercase tracking-wide mb-1">Session ID</p>
            <p className="text-sm text-gray-700 font-mono break-all">{sessionId}</p>
          </div>
        )}

        <div className="flex flex-col gap-3">
          <Link
            href="/dashboard/billing"
            className="bg-violet-600 text-white py-3 px-6 rounded-xl font-semibold hover:bg-violet-700 transition-colors"
          >
            Gestisci la tua subscription
          </Link>
          <Link
            href="/"
            className="text-gray-500 hover:text-gray-700 py-3 font-medium transition-colors"
          >
            Torna alla home
          </Link>
        </div>
      </div>
    </main>
  );
}

export default function SuccessPage() {
  return (
    <Suspense>
      <SuccessContent />
    </Suspense>
  );
}
