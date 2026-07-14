export interface EmailPreferences {
  email: string
  product_updates: boolean
  marketing: boolean
  unsubscribed_all: boolean
  unsubscribed_at?: string | null
}

export interface UpdateEmailPreferencesBody {
  product_updates: boolean
  marketing: boolean
}

export interface EmailUnsubscribeResponse {
  ok?: boolean
  email: string
  product_updates: boolean
  marketing: boolean
  unsubscribed_all: boolean
}
