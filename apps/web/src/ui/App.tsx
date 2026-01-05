export default function App() {
  return (
    <div className="min-h-screen p-6">
      <div className="max-w-3xl mx-auto space-y-4">
        <h1 className="text-3xl font-bold">Locksum</h1>
        <p className="text-slate-600">
          Docker is running. Next we build: auth - customers - items - invoices.
        </p>

        <div className="rounded-2xl border p-4">
          <div className="font-semibold">API status</div>
          <div className="text-sm text-slate-600">
            Try: <code className="px-1 py-0.5 rounded bg-slate-100">http://localhost/api/auth/ping</code>
          </div>
        </div>
      </div>
    </div>
  );
}
