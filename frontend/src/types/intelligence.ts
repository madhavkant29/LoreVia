export interface Theory {
  theory: string
  confidence: number
  evidence: string[]
  reasoning: string
}

export interface ChatMessage {
  role: "user" | "assistant"
  content: string
}
