"use client"
import { Component, type ReactNode } from "react"

export class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }
  static getDerivedStateFromError() { return { hasError: true } }
  render() {
    if (this.state.hasError)
      return (
        <div className="rounded-3xl border border-slate-200 bg-white px-6 py-10 text-center shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-rose-600">Component error</p>
          <p className="mt-3 text-sm text-slate-600">This part of the page crashed. Refresh, or try again from a clean page state.</p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => this.setState({ hasError: false })}
              className="rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
            >
              Retry component
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              Refresh page
            </button>
          </div>
        </div>
      )
    return this.props.children
  }
}
