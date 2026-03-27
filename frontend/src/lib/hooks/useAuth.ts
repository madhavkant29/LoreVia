import { useEffect } from "react"
import { useAuthStore } from "@/lib/stores/authStore"
import { authApi } from "@/lib/api/auth"
import { useRouter } from "next/navigation"

export function useAuth(requireAuth = false) {
  const { user, accessToken, setUser, logout } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    if (accessToken && !user) {
      authApi.me().then(setUser).catch(() => logout())
    }
    if (requireAuth && !accessToken) {
      router.push("/login")
    }
  }, [accessToken, user, requireAuth])

  return { user, isLoggedIn: !!accessToken }
}
