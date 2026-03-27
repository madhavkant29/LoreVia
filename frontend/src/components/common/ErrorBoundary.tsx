"use client"
import { Component, type ReactNode } from "react"

export class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }
  static getDerivedStateFromError() { return { hasError: true } }
  render() {
    if (this.state.hasError)
      return <div className="text-center py-10 text-gray-400">Something went wrong. Please refresh.</div>
    return this.props.children
  }
}
