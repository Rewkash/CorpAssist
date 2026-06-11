import type { Conversation } from '../../api'
import type { Role } from '../../store'

type UserRole = Role | null

type Client = {
  id: number
  email: string
}

const HIDDEN_CLIENT_TAGS = new Set(['срочно', 'приоритет'])

export function getActiveConversation(
  conversationId: number | null,
  conversations: Conversation[],
  clientHistory: Conversation[],
  selectedConversation: Conversation | null,
) {
  if (!conversationId) return null
  return conversations.find((conversation) => conversation.id === conversationId)
    || clientHistory.find((conversation) => conversation.id === conversationId)
    || selectedConversation
}

export function getActiveClientEmail(
  activeConversation: Conversation | null,
  clients: Client[],
  role: UserRole,
  email: string,
) {
  if (!activeConversation) return '—'
  return activeConversation.client_email
    || clients.find((client) => client.id === activeConversation.client_id)?.email
    || (role === 'client' ? email : `Клиент #${activeConversation.client_id}`)
}

export function isConversationClosed(conversation: Conversation | null) {
  return conversation?.status === 'closed'
}

export function filterConversations(conversations: Conversation[], search: string) {
  const normalizedSearch = search.toLowerCase()
  return conversations.filter((conversation) => `${conversation.id} ${conversation.title}`.toLowerCase().includes(normalizedSearch))
}

export function getVisibleConversationTags(conversation: Conversation | null, role: UserRole) {
  return (conversation?.tags || []).filter((tag) => role !== 'client' || !HIDDEN_CLIENT_TAGS.has(tag.trim().toLowerCase()))
}
