type PasswordValidationResult = {
  isValid: boolean
  message: string | null
}

export function validateRegisterPassword(password: string, email: string): PasswordValidationResult {
  const normalizedPassword = password.trim()
  const normalizedEmail = email.trim().toLowerCase()
  const emailLocal = normalizedEmail.split("@")[0] ?? ""

  if (normalizedPassword.length < 12) {
    return {
      isValid: false,
      message: "Password must be at least 12 characters long.",
    }
  }

  if (!/[a-z]/.test(normalizedPassword) || !/[A-Z]/.test(normalizedPassword)) {
    return {
      isValid: false,
      message: "Password must include both uppercase and lowercase letters.",
    }
  }

  if (!/\d/.test(normalizedPassword)) {
    return {
      isValid: false,
      message: "Password must include at least one number.",
    }
  }

  if (!/[^A-Za-z0-9]/.test(normalizedPassword)) {
    return {
      isValid: false,
      message: "Password must include at least one symbol.",
    }
  }

  if (emailLocal.length >= 3 && normalizedPassword.toLowerCase().includes(emailLocal)) {
    return {
      isValid: false,
      message: "Password cannot contain the name from your email address.",
    }
  }

  if (/(.)\1{2,}/.test(normalizedPassword)) {
    return {
      isValid: false,
      message: "Password cannot contain the same character repeated three or more times in a row.",
    }
  }

  return {
    isValid: true,
    message: null,
  }
}

export function validateRegisterUsername(username: string): string | null {
  const trimmedUsername = username.trim()

  if (trimmedUsername.length < 3) {
    return "Username must be at least 3 characters long."
  }

  if (trimmedUsername.length > 32) {
    return "Username must be 32 characters or fewer."
  }

  return null
}
