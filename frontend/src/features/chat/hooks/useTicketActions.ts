import { closeConversation, getConversations, getMessages, sendMessage } from '../../../api'
import type { ChatMessage, Conversation } from '../../../api'
import type { Role } from '../../../store'

type SetState<T> = (value: T | ((prev: T) => T)) => void

type UseTicketActionsParams = {
  token: string
  role: Role | null
  conversationId: number | null
  setConversationId: (id: number | null) => void
  setConversations: SetState<Conversation[]>
  setSelectedConversation: SetState<Conversation | null>
  setClientHistory: SetState<Conversation[]>
  setMessages: SetState<ChatMessage[]>
  setFirstUnreadId: (id: number | null) => void
  setText: (value: string) => void
  setReplySuggestions: (suggestions: string[]) => void
  setError: (message: string) => void
  setAssistHint: (message: string) => void
}

export function useTicketActions({
  token,
  role,
  conversationId,
  setConversationId,
  setConversations,
  setSelectedConversation,
  setClientHistory,
  setMessages,
  setFirstUnreadId,
  setText,
  setReplySuggestions,
  setError,
  setAssistHint,
}: UseTicketActionsParams) {
  const closeTicket = async () => {
    if (!token || !conversationId) return
    if (role !== 'worker' && role !== 'admin') {
      setError('Только сотрудник или администратор может закрыть тикет')
      return
    }
    try {
      await closeConversation(token, conversationId)
      await sendMessage(token, conversationId, 'Тикет закрыт. Спасибо за обращение! Если понадобится помощь, напишите снова.')
      const [list, items] = await Promise.all([getConversations(token), getMessages(token, conversationId)])
      setConversations(list)
      setMessages(items)
      setConversationId(null)
      setSelectedConversation(null)
      setClientHistory([])
      setAssistHint('Тикет закрыт и скрыт из списка открытых диалогов.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось закрыть тикет')
    }
  }

  const transferTicket = async () => {
    if (!token || !conversationId) return
    await sendMessage(token, conversationId, 'Тикет передан в профильную линию. Коллега подключится в течение 10 минут.')
    const items = await getMessages(token, conversationId)
    setMessages(items)
  }

  const createClientConversation = async () => {
    if (role !== 'client') return
    setConversationId(null)
    setSelectedConversation(null)
    setClientHistory([])
    setMessages([])
    setFirstUnreadId(null)
    setText('')
    setReplySuggestions([])
    setError('')
    setAssistHint('Новый диалог будет создан после первого сообщения.')
  }

  return { closeTicket, transferTicket, createClientConversation }
}
