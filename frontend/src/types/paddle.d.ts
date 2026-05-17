type PaddleCheckoutSettings = {
  allowLogout?: boolean
  displayMode?: "overlay" | "inline"
  locale?: string
  successUrl?: string
  theme?: "light" | "dark"
  variant?: "one-page" | "multi-page"
}

type PaddleEvent = {
  data?: {
    transaction_id?: string
  }
  name?: string
}

type PaddleInitializeOptions = {
  token: string
  checkout?: {
    settings?: PaddleCheckoutSettings
  }
  eventCallback?: (event: PaddleEvent) => void
  pwCustomer?: Record<string, never>
}

type PaddleCheckoutOpenOptions = {
  settings?: PaddleCheckoutSettings
  transactionId: string
}

type PaddleGlobal = {
  Initialized?: boolean
  Checkout: {
    open: (options: PaddleCheckoutOpenOptions) => void
  }
  Environment: {
    set: (environment: "sandbox") => void
  }
  Initialize: (options: PaddleInitializeOptions) => void
  Update?: (options: Pick<PaddleInitializeOptions, "eventCallback" | "pwCustomer">) => void
}

declare global {
  interface Window {
    Paddle?: PaddleGlobal
  }
}

export {}
