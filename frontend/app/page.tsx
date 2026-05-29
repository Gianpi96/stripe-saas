import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-violet-600 to-indigo-700 flex items-center justify-center px-4">
      <div className="text-center text-white max-w-2xl">
        <h1 className="text-6xl font-extrabold mb-4 tracking-tight">StripeSaaS</h1>
        <p className="text-xl text-violet-200 mb-12">
          Checkout · Subscription · Portal · Webhook · Email — tutto integrato.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/pricing"
            className="bg-white text-violet-700 font-bold py-4 px-8 rounded-xl text-lg hover:bg-violet-50 transition-colors shadow-lg"
          >
            Vedi i prezzi →
          </Link>
          <Link
            href="/dashboard/billing"
            className="border-2 border-white text-white font-bold py-4 px-8 rounded-xl text-lg hover:bg-white/10 transition-colors"
          >
            La mia subscription
          </Link>
        </div>
      </div>
    </main>
  );
}
