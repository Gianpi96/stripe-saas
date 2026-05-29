import Link from "next/link";

export default function CancelPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-50 to-slate-100 flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-10 text-center">
        <div className="w-20 h-20 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg className="w-10 h-10 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>

        <h1 className="text-3xl font-bold text-gray-900 mb-3">Pagamento annullato</h1>
        <p className="text-gray-600 mb-8 leading-relaxed">
          Nessun addebito è stato effettuato. Puoi tornare alla pagina prezzi e scegliere un piano in qualsiasi momento.
        </p>

        <div className="flex flex-col gap-3">
          <Link
            href="/pricing"
            className="bg-violet-600 text-white py-3 px-6 rounded-xl font-semibold hover:bg-violet-700 transition-colors"
          >
            Torna ai prezzi
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
