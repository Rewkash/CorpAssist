import type { Role } from '../../../store'
import { filterConversations, getActiveClientEmail, getActiveConversation, getVisibleConversationTags, isConversationClosed } from '../chatSelectors'
import { useChatStore } from '../store/chatStore'

type UseChatViewModelParams = {
  conversationId: number | null
  role: Role | null
  email: string
  search: string
}

export function useChatViewModel({
  conversationId,
  role,
  email,
  search,
}: UseChatViewModelParams) {
  const conversations = useChatStore((state) => state.conversations)
  const clientHistory = useChatStore((state) => state.clientHistory)
  const selectedConversation = useChatStore((state) => state.selectedConversation)
  const clients = useChatStore((state) => state.clients)

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
