import type { Conversation } from '../../../api'
import type { Role } from '../../../store'
import { filterConversations, getActiveClientEmail, getActiveConversation, getVisibleConversationTags, isConversationClosed } from '../chatSelectors'

type ClientOption = { id: number; email: string; assigned_worker_id: number | null }

type UseChatViewModelParams = {
  conversationId: number | null
  conversations: Conversation[]
  clientHistory: Conversation[]
  selectedConversation: Conversation | null
  clients: ClientOption[]
  role: Role | null
  email: string
  search: string
}

export function useChatViewModel({
  conversationId,
  conversations,
  clientHistory,
  selectedConversation,
  clients,
  role,
  email,
  search,
}: UseChatViewModelParams) {
  const activeConversation = getActiveConversation(conversationId, conversations, clientHistory, selectedConversation)
  const activeClientEmail = getActiveClientEmail(activeConversation, clients, role, email)
  const isActiveConversationClosed = isConversationClosed(activeConversation)
  const filteredConversations = filterConversations(conversations, search)
  const activeTags = getVisibleConversationTags(activeConversation, role)

  return {
    activeConversation,
    activeClientEmail,
    isActiveConversationClosed,
    filteredConversations,
    activeTags,
  }
}
