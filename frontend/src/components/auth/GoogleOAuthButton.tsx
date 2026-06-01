"use client"

import { GoogleOAuthButtonShell } from "@/components/auth/GoogleOAuthButtonShell"
import { supabase } from "@/lib/supabase"

export function GoogleOAuthButton({
  acceptedTerms = false,
  className,
  requireAcceptedTerms = false,
  onError,
}: {
  acceptedTerms?: boolean
  className?: string
  requireAcceptedTerms?: boolean
  onError: (message: string) => void
}) {
  const signInWithGoogle = async () => {
    if (!supabase) {
      onError("Google sign-in is not configured right now.")
      return
    }
    if (requireAcceptedTerms && !acceptedTerms) {
      onError("Please accept the Terms, Compliance notice, and EULA before continuing with Google.")
      return
    }
    window.sessionStorage.setItem("lorevia-oauth-accepted-terms", String(acceptedTerms))
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    })
  }

  return <GoogleOAuthButtonShell className={className} onClick={signInWithGoogle} />
}
