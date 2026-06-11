import { useCallback, useEffect, useRef } from 'react'

import { markMessagesRead } from '../../../api'
import type { ChatMessage, Conversation } from '../../../api'
import type { Role } from '../../../store'
import { useChat } from '../../../useChat'
import { useDocumentThemeClass } from '../../../hooks/useDocumentThemeClass'
import { useChatBootstrap } from '../hooks/useChatBootstrap'
import { useChatScroll } from '../hooks/useChatScroll'
import { useChatStore } from '../store/chatStore'

type UseChatRuntimeControllerParams = {
  token: string
  role: Role | null
  theme: 'light' | 'dark'
  conversationId: number | null
  text: string
  assistHint: string
  error: string
  viewportWidth: number
  setRightCollapsed: (value: boolean | ((prev: boolean) => boolean)) => void
  setError: (value: string) => void
}

export function useChatRuntimeController({
  token,
  role,
  theme,
  conversationId,
  text,
  assistHint,
  error,
  viewportWidth,
  setRightCollapsed,
  setError,
}: UseChatRuntimeControllerParams) {
  const reconnectPhaseStartedAtRef = useRef<number | null>(null)
  const messages = useChatStore((state) => state.messages)
  const myId = useChatStore((state) => state.myId)
  const connectionError = useChatStore((state) => state.connectionError)
  const reconnectIn = useChatStore((state) => state.reconnectIn)
  const isReconnectingNow = useChatStore((state) => state.isReconnectingNow)
  const appendMessageIfMissing = useChatStore((state) => state.appendMessageIfMissing)
  const setConversationsSnapshot = useChatStore((state) => state.setConversationsSnapshot)
  const setConnectionError = useChatStore((state) => state.setConnectionError)
  const setReconnectIn = useChatStore((state) => state.setReconnectIn)
  const setIsReconnectingNow = useChatStore((state) => state.setIsReconnectingNow)

  useDocumentThemeClass(theme)

  useEffect(() => {
    if (viewportWidth < 1100) {
      setRightCollapsed(true)
    } else {
      setRightCollapsed(false)
    }
  }, [viewportWidth])

  const scroll = useChatScroll({
    token,
    conversationId,
    messages,
    myId,
    text,
    assistHint,
    connectionError,
    error,
  })

  useChatBootstrap({
    token,
    role,
    conversationId,
    reconnectPhaseStartedAtRef,
    forceScrollOnNextRenderRef: scroll.forceScrollOnNextRenderRef,
    setError,
    setFirstUnreadId: scroll.setFirstUnreadId,
  })

  const handleSocketMessageCreated = useCallback((message: ChatMessage) => {
    if (!conversationId || message.conversation_id !== conversationId) return
    appendMessageIfMissing(message)
    if (myId !== null && message.sender_id !== myId && !message.read_at && scroll.firstUnreadId === null && !scroll.isAtBottomRef.current) {
      scroll.setFirstUnreadId(message.id)
    }
    if (token && scroll.isAtBottomRef.current) {
      markMessagesRead(token, conversationId).catch(() => {})
    }
  }, [conversationId, token, myId, scroll.firstUnreadId])

  const handleSocketConversationsSnapshot = useCallback((items: Conversation[]) => {
    setConversationsSnapshot(items)
  }, [setConversationsSnapshot])

  const handleSocketConnectionState = useCallback((isConnected: boolean) => {
    setConnectionError(!isConnected)
    setIsReconnectingNow(!isConnected)
    if (isConnected) {
      setReconnectIn(null)
      reconnectPhaseStartedAtRef.current = null
    }
  }, [])

  useChat({
    token,
    conversationId,
    onMessageCreated: handleSocketMessageCreated,
    onConversationsSnapshot: handleSocketConversationsSnapshot,
    onConnectionStateChange: handleSocketConnectionState,
  })

  return {
    messages,
    myId,
    connectionError,
    reconnectIn,
    isReconnectingNow,
    scroll,
  }
}
