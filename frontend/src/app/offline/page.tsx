import Image from "next/image"

export default function OfflinePage() {
  return <main className="grid min-h-screen place-items-center bg-stone-50 px-6"><section className="max-w-lg rounded-3xl border border-stone-200 bg-white p-8 text-center shadow-sm"><Image src="/logoandtext.png" alt="LoreVia" width={180} height={48} className="mx-auto h-10 w-auto" /><h1 className="mt-7 text-2xl font-semibold text-stone-950">You are offline</h1><p className="mt-3 text-sm leading-6 text-stone-600">Already-open manuscript drafts continue saving on this device. LoreVia will replay queued chapter edits when your connection returns and will stop for review if another session changed the same chapter.</p></section></main>
}
