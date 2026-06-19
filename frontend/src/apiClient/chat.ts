import { authFetch } from './client'
import type { ChatMessage, Conversation } from './types'

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

export async function regenerateConversationTags(token: string, conversationId: number): Promise<{ tags: string[] }> {
  const response = await authFetch(`/chat/conversations/${conversationId}/regenerate-tags`, token, { method: 'POST' })
  return response.json()
}

export async function setConversationTags(token: string, conversationId: number, tags: string[]): Promise<Conversation> {
  const response = await authFetch('/chat/conversations/tags', token, {
    method: 'POST',
    body: JSON.stringify({ conversation_id: conversationId, tags })
  })
  return response.json()
}
