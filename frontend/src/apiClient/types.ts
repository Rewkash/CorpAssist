export type AuthPayload = {
  email: string
  password: string
  role?: 'client' | 'worker'
}

export type Me = {
  id: number
  email: string
  role: 'admin' | 'worker' | 'client'
  assigned_worker_id: number | null
}

export type Conversation = {
  id: number
  title: string
  client_id: number
  client_email?: string | null
  worker_id: number | null
  status: 'open' | 'closed'
  unread_count: number
  tags: string[]
  priority_at?: string | null
  message_count: number
  first_message_preview?: string | null
  created_at: string
  closed_at?: string | null
}

export type ChatMessage = {
  id: number
  conversation_id: number
  sender_id: number
  text: string
  status: 'sent' | 'delivered' | 'read'
  created_at: string
  read_at?: string | null
}

export type Analysis = {
  sentiment: 'neutral' | 'tense' | 'positive'
  topics: string[]
  formality: 'low' | 'medium' | 'high'
}

export type ReplyAssistResult = {
  analysis: Analysis
  suggestions: string[]
}

export type ImproveResult = {
  analysis: Analysis
  improved_text: string
}

export type AdminUser = {
  id: number
  email: string
  role: 'admin' | 'worker' | 'client'
  assigned_worker_id: number | null
}
