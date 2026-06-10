import type { MutableRefObject } from 'react'
import { getConversations, getMessages, markMessagesRead, sendMessage, startConversation } from '../../../api'
import type { ChatMessage, Conversation } from '../../../api'
import type { Role } from '../../../store'

type SetState<T> = (value: T | ((prev: T) => T)) => void

type UseMessageSendingParams = {
  auth: {
    token: string
    role: Role | null
  }
  guards: {
    isActiveConversationClosed: boolean
  }
  conversation: {
    conversationId: number | null
    setConversationId: (id: number | null) => void
    setSelectedConversation: SetState<Conversation | null>
    setConversations: SetState<Conversation[]>
  }
  composer: {
    text: string
    setText: (value: string) => void
    setBusy: (value: boolean) => void
    setError: (message: string) => void
    setAssistHint: (message: string) => void
    setReplySuggestions: (suggestions: string[]) => void
  }
  messages: {
    setMessages: SetState<ChatMessage[]>
  }
  scroll: {
    clearUnreadDividerSmooth: () => void
    forceScrollOnNextRenderRef: MutableRefObject<boolean>
    isAtBottomRef: MutableRefObject<boolean>
  }
}

export function useMessageSending({ auth, guards, conversation, composer, messages, scroll }: UseMessageSendingParams) {
  const ensureTargetConversation = async () => {
    let targetConversationId = conversation.conversationId
    if (!targetConversationId && auth.role === 'client') {
      const createdConversation = await startConversation(auth.token)
      targetConversationId = createdConversation.id
      conversation.setConversationId(createdConversation.id)
      conversation.setSelectedConversation(createdConversation)
      const list = await getConversations(auth.token)
      conversation.setConversations(list)
    }
    return targetConversationId
  }

  const synchronizeSentMessage = async (targetConversationId: number, outgoingText: string) => {
    const item = await sendMessage(auth.token, targetConversationId, outgoingText)
    messages.setMessages((prev) => [...prev, item])
    scroll.clearUnreadDividerSmooth()
    composer.setText('')
    composer.setReplySuggestions([])
    const items = await getMessages(auth.token, targetConversationId)
    scroll.forceScrollOnNextRenderRef.current = true
    messages.setMessages(items)
    if (scroll.isAtBottomRef.current) {
      await markMessagesRead(auth.token, targetConversationId)
    }
  }

  const handleSendError = (err: unknown) => {
    const message = err instanceof Error ? err.message : 'Не удалось отправить сообщение'
    if (message.includes('Диалог закрыт')) {
      composer.setError('')
      composer.setAssistHint('Этот диалог уже закрыт. Нажмите + Новый диалог, чтобы продолжить.')
    } else {
      composer.setError(message)
    }
  }

  const sendCurrentMessage = async () => {
    if (!auth.token || composer.text.trim().length < 1) return
    if (guards.isActiveConversationClosed) {
      composer.setError('')
      composer.setAssistHint('Этот диалог закрыт. Начните новый диалог, чтобы написать сообщение.')
      return
    }
    composer.setBusy(true)
    composer.setError('')
    try {
      const outgoingText = composer.text.trim()
      const targetConversationId = await ensureTargetConversation()
      if (!targetConversationId) {
        composer.setError('Сначала выберите диалог из списка или создайте новый.')
        return
      }
      await synchronizeSentMessage(targetConversationId, outgoingText)
    } catch (err) {
      handleSendError(err)
    } finally {
      composer.setBusy(false)
    }
  }

  return { sendCurrentMessage }
}
