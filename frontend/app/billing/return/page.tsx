"use client";

import { useEffect, useState } from "react";
import { getSubscriptionStatus } from "@/lib/api";
import Link from "next/link";

export default function BillingReturnPage() {
  const [status, setStatus] = useState<string | null>(null);
  const [plan, setPlan] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSubscriptionStatus()
      .then((data) => {
        setStatus(data.status);
        setPlan(data.plan);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-gradient-to-br from-violet-50 to-indigo-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-10 text-center">
        <div className="w-20 h-20 bg-violet-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg className="w-10 h-10 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-2">Modifiche salvate</h1>
        <p className="text-gray-500 mb-6">
          Le tue preferenze di fatturazione sono state aggiornate con successo.
        </p>

        {!loading && status && (
          <div className="bg-gray-50 rounded-xl p-4 mb-8 text-left">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-500">Piano attuale</span>
              <span className="font-semibold capitalize text-gray-900">{plan ?? "—"}</span>
            </div>
            <div className="flex justify-between items-center mt-2">
              <span className="text-sm text-gray-500">Stato</span>
              <span className={`text-sm font-semibold capitalize px-2.5 py-0.5 rounded-full ${
                status === "active"   ? "bg-green-100 text-green-700" :
                status === "trialing" ? "bg-blue-100 text-blue-700"  :
                status === "canceled" ? "bg-gray-100 text-gray-600"  :
                                        "bg-amber-100 text-amber-700"
              }`}>
                {status}
              </span>
            </div>
          </div>
        )}

        <div className="flex flex-col gap-3">
          <Link
            href="/dashboard/billing"
            className="bg-violet-600 text-white py-3 px-6 rounded-xl font-semibold hover:bg-violet-700 transition-colors"
          >
            Torna alla fatturazione
          </Link>
          <Link
            href="/"
            className="text-gray-500 hover:text-gray-700 py-3 font-medium transition-colors"
          >
            Vai alla home
          </Link>
        </div>
      </div>
    </main>
  );
}
