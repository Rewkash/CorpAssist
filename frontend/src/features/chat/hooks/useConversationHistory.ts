import { useEffect, useRef } from 'react'

import { getClientConversationHistory } from '../../../api'
import { useChatStore } from '../store/chatStore'

type UseConversationHistoryParams = {
  token: string | null
  conversationId: number | null
  onError: (message: string) => void
}

export function useConversationHistory({
  token,
  conversationId,
  onError,
}: UseConversationHistoryParams) {
  const selectedConversation = useChatStore((state) => state.selectedConversation)
  const conversations = useChatStore((state) => state.conversations)
  const setClientHistory = useChatStore((state) => state.setClientHistory)
  const updateSelectedConversation = useChatStore((state) => state.updateSelectedConversation)
  const conversationsRef = useRef(conversations)

  useEffect(() => {
    conversationsRef.current = conversations
  }, [conversations])

  useEffect(() => {
    if (!token || !conversationId || !selectedConversation) {
      setClientHistory([])
      return
    }

    let cancelled = false

    const loadClientHistory = async () => {
      try {
        const history = await getClientConversationHistory(token, conversationId)
        if (!cancelled) {
          setClientHistory(history.length > 0 ? history : [selectedConversation])
          const updatedConversation = history.find((conversation) => conversation.id === conversationId)
          if (updatedConversation) {
            updateSelectedConversation(updatedConversation)
          }
        }
      } catch (err) {
        if (!cancelled) {
          const fallbackHistory = conversationsRef.current.filter((conversation) => conversation.client_id === selectedConversation.client_id)
          setClientHistory(fallbackHistory.length > 0 ? fallbackHistory : [selectedConversation])
          onError(err instanceof Error ? err.message : 'Не удалось загрузить историю клиента')
        }
      }
    }

    loadClientHistory()

    return () => {
      cancelled = true
    }
  }, [token, conversationId, selectedConversation?.id, selectedConversation?.client_id])

  return {}
}
