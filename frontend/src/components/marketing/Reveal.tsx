"use client"

import { useEffect, useRef, useState } from "react"

export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: React.ReactNode
  delay?: number
  className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(true)
  const [canAnimate, setCanAnimate] = useState(false)

  useEffect(() => {
    const node = ref.current
    if (!node || typeof IntersectionObserver === "undefined") return

    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    if (reducedMotion) return

    setCanAnimate(true)
    const initiallyVisible = node.getBoundingClientRect().top <= window.innerHeight
    setInView(initiallyVisible)

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          observer.disconnect()
        }
      },
      { threshold: 0.14 }
    )

    observer.observe(node)

    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={`transform-gpu transition-[opacity,transform] duration-300 ease-out motion-reduce:transition-none ${
        !canAnimate || inView ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"
      } ${className}`}
    >
      {children}
    </div>
  )
}
