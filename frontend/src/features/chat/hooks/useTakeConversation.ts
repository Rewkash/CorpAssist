import type { MutableRefObject } from 'react'
import { getClientConversationHistory, getConversations, getMessages, markMessagesRead, takeConversation } from '../../../api'
import type { ChatMessage, Conversation } from '../../../api'
import type { Role } from '../../../store'

type SetState<T> = (value: T | ((prev: T) => T)) => void

type UseTakeConversationParams = {
  token: string
  role: Role | null
  myId: number | null
  setConversationId: (id: number | null) => void
  setConversations: SetState<Conversation[]>
  setSelectedConversation: SetState<Conversation | null>
  setClientHistory: SetState<Conversation[]>
  setMessages: SetState<ChatMessage[]>
  setFirstUnreadId: (id: number | null) => void
  forceScrollOnNextRenderRef: MutableRefObject<boolean>
  setError: (message: string) => void
}

export function useTakeConversation({
  token,
  role,
  myId,
  setConversationId,
  setConversations,
  setSelectedConversation,
  setClientHistory,
  setMessages,
  setFirstUnreadId,
  forceScrollOnNextRenderRef,
  setError,
}: UseTakeConversationParams) {
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
