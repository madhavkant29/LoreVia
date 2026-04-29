import { useEffect } from "react"
import { useAuthStore } from "@/lib/stores/authStore"
import { useRouter } from "next/navigation"

export function useAuth(requireAuth = false) {
  const { user, hydrated } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    if (!hydrated) return
    if (requireAuth && !user) {
      router.push("/login")
    }
  }, [hydrated, user, requireAuth, router])

  return { user, isLoggedIn: hydrated && !!user, hydrated }
}
