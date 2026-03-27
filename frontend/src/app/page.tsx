import Link from "next/link"

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-8 px-4 bg-gradient-to-b from-indigo-50 to-white">
      <div className="text-center max-w-lg">
        <h1 className="text-5xl font-bold tracking-tight text-gray-900 mb-4">LoreVia</h1>
        <p className="text-xl text-gray-500 mb-2">Your books, deeply understood.</p>
        <p className="text-sm text-gray-400">Characters. Relationships. Plot threads. Memory. On demand.</p>
      </div>
      <div className="flex gap-4">
        <Link href="/register" className="px-6 py-3 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 transition-colors shadow-sm">
          Get started free
        </Link>
        <Link href="/login" className="px-6 py-3 border border-gray-300 rounded-xl font-medium hover:bg-gray-50 transition-colors">
          Sign in
        </Link>
      </div>
    </main>
  )
}
