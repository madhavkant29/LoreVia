"use client"

interface Props {
  recall: string
  lastChapter: number
  onDismiss: () => void
  onContinue: () => void
}

export function RecallCard({ recall, lastChapter, onDismiss, onContinue }: Props) {
  return (
    <div className="bg-indigo-50 border border-indigo-100 rounded-2xl p-5 mb-6">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-medium text-indigo-600 uppercase tracking-wide">Previously on… (Ch. {lastChapter})</p>
        <button onClick={onDismiss} className="text-indigo-300 hover:text-indigo-500 text-lg">×</button>
      </div>
      <p className="text-sm text-gray-700 leading-relaxed mb-4">{recall}</p>
      <button onClick={onContinue}
        className="text-sm bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors">
        Continue Reading
      </button>
    </div>
  )
}
