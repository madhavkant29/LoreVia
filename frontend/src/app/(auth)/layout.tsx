import Link from "next/link"

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-[100dvh] bg-[radial-gradient(circle_at_top_left,#efe3c8,transparent_22%),radial-gradient(circle_at_88%_10%,#dde9fb,transparent_26%),linear-gradient(180deg,#f7f3ec_0%,#f7f7f5_52%,#eef2f8_100%)] px-4 py-8">
      <div className="mx-auto flex min-h-[calc(100dvh-4rem)] max-w-5xl flex-col justify-between gap-10">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/" className="flex items-center gap-3 text-stone-900">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-stone-950 text-sm font-semibold text-white">LV</div>
            <div>
              <p className="font-serif text-2xl tracking-tight">LoreVia</p>
              <p className="text-xs text-stone-500">A serious reading workspace</p>
            </div>
          </Link>
          <Link
            href="/"
            className="rounded-full border border-stone-300 bg-white/80 px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-white"
          >
            Back to home
          </Link>
        </header>

        <div className="grid gap-8 lg:grid-cols-[0.95fr_0.7fr] lg:items-center">
          <section className="hidden lg:block">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-amber-700">Read with continuity</p>
            <h1 className="mt-4 max-w-xl font-serif text-5xl leading-[1.05] text-stone-950">
              Stay inside the story,
              <br />
              not inside the friction.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-8 text-stone-600">
              LoreVia keeps context, characters, and narrative threads close at hand so dense books feel navigable without flattening them into generic chat.
            </p>
            <div className="mt-8 grid max-w-xl gap-4 sm:grid-cols-2">
              {[
                ["Spoiler-safe by design", "Summaries and context stay tied to what you have already read."],
                ["Character continuity", "Aliases, motives, and relationships are gathered into one evolving view."],
                ["Built for real books", "Long fiction, classics, and series stay readable without losing the thread."],
                ["Grounded reading tools", "Search, graph, timeline, and recall stay anchored to the text."],
              ].map(([title, body]) => (
                <div key={title} className="rounded-[1.6rem] border border-white/70 bg-white/70 p-4 shadow-[0_18px_55px_-45px_rgba(15,23,42,0.28)]">
                  <p className="text-sm font-semibold text-stone-900">{title}</p>
                  <p className="mt-2 text-sm leading-6 text-stone-600">{body}</p>
                </div>
              ))}
            </div>
          </section>

          <div className="mx-auto w-full max-w-md">{children}</div>
        </div>

        <footer className="flex flex-wrap items-center justify-center gap-4 text-xs text-stone-500">
          <Link href="/terms" className="hover:text-stone-900">Terms &amp; Conditions</Link>
          <Link href="/compliance" className="hover:text-stone-900">Compliance</Link>
          <Link href="/eula" className="hover:text-stone-900">EULA</Link>
          <Link href="/contact" className="hover:text-stone-900">Contact</Link>
        </footer>
      </div>
    </div>
  )
}
