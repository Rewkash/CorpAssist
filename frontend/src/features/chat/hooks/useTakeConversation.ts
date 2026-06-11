import type { MutableRefObject } from 'react'
import { getClientConversationHistory, getConversations, getMessages, markMessagesRead, takeConversation } from '../../../api'
import type { Role } from '../../../store'
import { useChatStore } from '../store/chatStore'

type UseTakeConversationParams = {
  token: string
  role: Role | null
  setConversationId: (id: number | null) => void
  setFirstUnreadId: (id: number | null) => void
  forceScrollOnNextRenderRef: MutableRefObject<boolean>
  setError: (message: string) => void
}

export function useTakeConversation({
  token,
  role,
  setConversationId,
  setFirstUnreadId,
  forceScrollOnNextRenderRef,
  setError,
}: UseTakeConversationParams) {
  const myId = useChatStore((state) => state.myId)
  const setConversations = useChatStore((state) => state.setConversations)
  const setSelectedConversation = useChatStore((state) => state.setSelectedConversation)
  const setClientHistory = useChatStore((state) => state.setClientHistory)
  const setMessages = useChatStore((state) => state.setMessages)

  const takeSelectedConversation = async (id: number) => {
    if (!token) return
    try {
      if (role !== 'client') {
        const taken = await takeConversation(token, id)
        setSelectedConversation(taken)
      }
      setConversationId(id)
      const [list, items, history] = await Promise.all([getConversations(token), getMessages(token, id), getClientConversationHistory(token, id)])
      setConversations(list)
      setSelectedConversation((current) => list.find((conversation) => conversation.id === id) || current || null)
      setClientHistory(history.length > 0 ? history : list.filter((conversation) => conversation.id === id))
      const firstUnread = items.find((message) => message.sender_id !== myId && !message.read_at)
      setFirstUnreadId(firstUnread?.id ?? null)
      forceScrollOnNextRenderRef.current = true
      setMessages(items)
      await markMessagesRead(token, id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось взять диалог')
    }
  }

  return { takeSelectedConversation }
}
