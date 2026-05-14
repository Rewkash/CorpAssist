const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_BASE = (import.meta.env.VITE_WS_URL || 'ws://localhost:8000') + '/ws/assist'
const WS_CHAT_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

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

export async function login(payload: AuthPayload): Promise<string> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  } catch {
    throw new Error('Не удалось подключиться. Проверьте интернет и попробуйте еще раз.')
  }
  if (!response.ok) throw new Error('Не получилось войти. Проверьте email и пароль.')
  const data = await response.json()
  return data.access_token
}

export async function register(payload: AuthPayload): Promise<string> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  } catch {
    throw new Error('Не удалось подключиться. Проверьте интернет и попробуйте еще раз.')
  }
  if (!response.ok) {
    let message = 'Не получилось создать аккаунт. Попробуйте еще раз.'
    try {
      const data = await response.json()
      const detail = data?.detail
      if (typeof detail === 'string' && detail.includes('exists')) {
        message = 'Такой email уже зарегистрирован. Войдите в аккаунт или используйте другой email.'
      } else if (Array.isArray(detail)) {
        message = 'Проверьте email и пароль и попробуйте еще раз.'
      }
    } catch {}
    throw new Error(message)
  }
  const data = await response.json()
  return data.access_token
}

async function authFetch(path: string, token: string, init?: RequestInit) {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(init?.headers || {})
      }
    })
  } catch {
    throw new Error('Не удалось подключиться. Проверьте интернет и попробуйте еще раз.')
  }
  if (!response.ok) {
    let message = 'Что-то пошло не так. Попробуйте еще раз.'
    try {
      const data = await response.json()
      if (typeof data?.detail === 'string') message = data.detail
    } catch {}
    throw new Error(message)
  }
  return response
}

export async function me(token: string): Promise<Me> {
  const response = await authFetch('/auth/me', token)
  return response.json()
}

export async function startConversation(token: string): Promise<Conversation> {
  const response = await authFetch('/chat/conversations/start', token, { method: 'POST' })
  return response.json()
}

export async function getConversations(token: string): Promise<Conversation[]> {
  const response = await authFetch('/chat/conversations', token)
  return response.json()
}

export async function getClientConversationHistory(token: string, conversationId: number): Promise<Conversation[]> {
  const response = await authFetch(`/chat/conversations/${conversationId}/client-history`, token)
  return response.json()
}

export async function getMessages(token: string, conversationId: number): Promise<ChatMessage[]> {
  const response = await authFetch(`/chat/messages/${conversationId}`, token)
  return response.json()
}

export async function sendMessage(token: string, conversationId: number, text: string): Promise<ChatMessage> {
  const response = await authFetch('/chat/messages', token, {
    method: 'POST',
    body: JSON.stringify({ conversation_id: conversationId, text })
  })
  return response.json()
}

export async function markMessagesRead(token: string, conversationId: number): Promise<void> {
  await authFetch('/chat/messages/read', token, {
    method: 'POST',
    body: JSON.stringify({ conversation_id: conversationId })
  })
}

export async function takeConversation(token: string, conversationId: number): Promise<Conversation> {
  const response = await authFetch(`/chat/conversations/${conversationId}/take`, token, { method: 'POST' })
  return response.json()
}

export async function closeConversation(token: string, conversationId: number): Promise<Conversation> {
  const response = await authFetch(`/chat/conversations/${conversationId}/close`, token, { method: 'POST' })
  return response.json()
}

export async function suggestConversationTags(token: string, conversationId: number): Promise<{ tags: string[] }> {
  const response = await authFetch(`/chat/conversations/${conversationId}/suggest-tags`, token)
  return response.json()
}

export async function setConversationTags(token: string, conversationId: number, tags: string[]): Promise<Conversation> {
  const response = await authFetch('/chat/conversations/tags', token, {
    method: 'POST',
    body: JSON.stringify({ conversation_id: conversationId, tags })
  })
  return response.json()
}

export async function getWorkers(token: string): Promise<AdminUser[]> {
  const response = await authFetch('/admin/workers', token)
  return response.json()
}

export async function getClients(token: string): Promise<AdminUser[]> {
  const response = await authFetch('/admin/clients', token)
  return response.json()
}

export async function assignWorker(token: string, clientId: number, workerId: number): Promise<void> {
  await authFetch('/admin/assign-worker', token, {
    method: 'POST',
    body: JSON.stringify({ client_id: clientId, worker_id: workerId })
  })
}

export async function suggestReply(token: string, text: string, conversationId?: number): Promise<ReplyAssistResult> {
  const response = await authFetch('/assist/reply', token, {
    method: 'POST',
    body: JSON.stringify({ text, conversation_id: conversationId })
  })
  return response.json()
}

export async function improveDraft(token: string, text: string): Promise<ImproveResult> {
  const response = await authFetch('/assist/improve', token, {
    method: 'POST',
    body: JSON.stringify({ text })
  })
  return response.json()
}

export function createAssistSocket(token: string, onMessage: (payload: any) => void): WebSocket {
  const socket = new WebSocket(`${WS_BASE}?token=${encodeURIComponent(token)}`)
  socket.onmessage = (event) => onMessage(JSON.parse(event.data))
  return socket
}

export function createChatSocket(token: string, conversationId: number): WebSocket {
  return new WebSocket(`${WS_CHAT_BASE}/ws/chat/${conversationId}?token=${encodeURIComponent(token)}`)
}

export function createChatUpdatesSocket(token: string): WebSocket {
  return new WebSocket(`${WS_CHAT_BASE}/ws/chat-updates?token=${encodeURIComponent(token)}`)
}
