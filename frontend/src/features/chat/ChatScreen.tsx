import { useCallback, useEffect, useRef, useState } from 'react'
import '../../supportChat.css'

import { markMessagesRead } from '../../api'
import type { ChatMessage, Conversation } from '../../api'
import { useDocumentThemeClass } from '../../hooks/useDocumentThemeClass'
import { useOutsideClick } from '../../hooks/useOutsideClick'
import { useChat } from '../../useChat'
import { useAssistStore } from '../../store'
import { ChatLayout } from './ChatLayout'
import { FREQUENT_TAGS } from './chatConstants'
import { useChatBootstrap } from './hooks/useChatBootstrap'
import { useChatScroll } from './hooks/useChatScroll'
import { useChatViewModel } from './hooks/useChatViewModel'
import { useComposerAssistActions } from './hooks/useComposerAssistActions'
import { useComposerState } from './hooks/useComposerState'
import { useConversationTags } from './hooks/useConversationTags'
import { useConversationHistory } from './hooks/useConversationHistory'
import { useMessageSending } from './hooks/useMessageSending'
import { useSidebarUiState } from './hooks/useSidebarUiState'
import { useSuggestedTags } from './hooks/useSuggestedTags'
import { useTakeConversation } from './hooks/useTakeConversation'
import { useTicketActions } from './hooks/useTicketActions'
import { useWorkerAssignment } from './hooks/useWorkerAssignment'
import { useChatStore } from './store/chatStore'

export function ChatScreen() {
  const { token, role, email, theme, toggleTheme, logout, conversationId, setConversationId } = useAssistStore()
  const [error, setError] = useState('')
  const composer = useComposerState()
  const reconnectPhaseStartedAtRef = useRef<number | null>(null)
  const messages = useChatStore((state) => state.messages)
  const clientHistory = useChatStore((state) => state.clientHistory)
  const clients = useChatStore((state) => state.clients)
  const workers = useChatStore((state) => state.workers)
  const myId = useChatStore((state) => state.myId)
  const connectionError = useChatStore((state) => state.connectionError)
  const reconnectIn = useChatStore((state) => state.reconnectIn)
  const isReconnectingNow = useChatStore((state) => state.isReconnectingNow)
  const assignClientId = useChatStore((state) => state.assignClientId)
  const assignWorkerId = useChatStore((state) => state.assignWorkerId)
  const appendMessageIfMissing = useChatStore((state) => state.appendMessageIfMissing)
  const setConversationsSnapshot = useChatStore((state) => state.setConversationsSnapshot)
  const setConnectionError = useChatStore((state) => state.setConnectionError)
  const setReconnectIn = useChatStore((state) => state.setReconnectIn)
  const setIsReconnectingNow = useChatStore((state) => state.setIsReconnectingNow)
  const setAssignClientId = useChatStore((state) => state.setAssignClientId)
  const setAssignWorkerId = useChatStore((state) => state.setAssignWorkerId)
  const sidebarUi = useSidebarUiState()
  const suggestedTags = useSuggestedTags({ token, conversationId, role })

  const {
    text,
    setText,
    busy,
    setBusy,
    assistBusy,
    setAssistBusy,
    assistHint,
    setAssistHint,
    generatingStatus,
    setGeneratingStatus,
    replySuggestions,
    setReplySuggestions,
  } = composer

  const {
    search,
    setSearch,
    rightCollapsed,
    setRightCollapsed,
    mobileMode,
    viewportWidth,
    manualTag,
    setManualTag,
    showTagDropdown,
    setShowTagDropdown,
    tagDropdownRef,
  } = sidebarUi

  useDocumentThemeClass(theme)

  useEffect(() => {
    if (viewportWidth < 1100) {
      setRightCollapsed(true)
    } else {
      setRightCollapsed(false)
    }
  }, [viewportWidth])

  const {
    messagesRef,
    bottomPanelRef,
    forceScrollOnNextRenderRef,
    isAtBottomRef,
    firstUnreadId,
    setFirstUnreadId,
    isUnreadDividerHiding,
    newMessagesCount,
    showJumpDown,
    jumpBottomOffset,
    clearUnreadDividerSmooth,
    handleMessagesScroll,
    jumpToBottom,
  } = useChatScroll({
    token,
    conversationId,
    messages,
    myId,
    text,
    assistHint,
    connectionError,
    error,
  })

  const handleHistoryError = useCallback((message: string) => {
    setError(message)
  }, [])

  useConversationHistory({
    token,
    conversationId,
    onError: handleHistoryError,
  })

  useChatBootstrap({
    token,
    role,
    conversationId,
    reconnectPhaseStartedAtRef,
    forceScrollOnNextRenderRef,
    setError,
    setFirstUnreadId,
  })

  const hideTagDropdown = useCallback(() => {
    setShowTagDropdown(false)
  }, [setShowTagDropdown])

  useOutsideClick(tagDropdownRef, hideTagDropdown)

  const {
    activeConversation,
    activeClientEmail,
    isActiveConversationClosed,
    filteredConversations,
    activeTags,
  } = useChatViewModel({
    conversationId,
    role,
    email,
    search,
  })

  const { sendCurrentMessage } = useMessageSending({
    auth: { token, role },
    guards: { isActiveConversationClosed },
    conversation: {
      conversationId,
      setConversationId,
    },
    composer: {
      text,
      setText,
      setBusy,
      setError,
      setAssistHint,
      setReplySuggestions,
    },
    scroll: {
      clearUnreadDividerSmooth,
      forceScrollOnNextRenderRef,
      isAtBottomRef,
    },
  })

  const { suggest: onSuggest, improve: onImprove } = useComposerAssistActions({
    token,
    text,
    conversationId,
    messages,
    myId,
    setText,
    setAssistBusy,
    setGeneratingStatus,
    setError,
    setReplySuggestions,
    setAssistHint,
  })

  const { takeSelectedConversation } = useTakeConversation({
    token,
    role,
    setConversationId,
    setFirstUnreadId,
    forceScrollOnNextRenderRef,
    setError,
  })

  const { assignSelectedWorker } = useWorkerAssignment({
    token,
    setError,
  })

  const { addTag, removeTag, togglePriority } = useConversationTags({
    token,
    conversationId,
    role,
    activeTags,
    setError,
  })

  const { closeTicket, transferTicket, createClientConversation } = useTicketActions({
    token,
    role,
    conversationId,
    setConversationId,
    setFirstUnreadId,
    setText,
    setReplySuggestions,
    setError,
    setAssistHint,
  })

  const handleSocketMessageCreated = useCallback((message: ChatMessage) => {
    if (!conversationId || message.conversation_id !== conversationId) return
    appendMessageIfMissing(message)
    if (myId !== null && message.sender_id !== myId && !message.read_at && firstUnreadId === null && !isAtBottomRef.current) {
      setFirstUnreadId(message.id)
    }
    if (token && isAtBottomRef.current) {
      markMessagesRead(token, conversationId).catch(() => {})
    }
  }, [conversationId, token, myId, firstUnreadId])

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

  return (
    <ChatLayout
      rightCollapsed={rightCollapsed}
      conversation={{
        email,
        role,
        search,
        conversations: filteredConversations,
        conversationId,
        onSearchChange: setSearch,
        onTakeConversation: takeSelectedConversation,
        onLogout: logout,
      }}
      center={{
        mobileMode,
        activeConversation,
        role,
        conversationId,
        rightCollapsed,
        messages,
        myId,
        firstUnreadId,
        isUnreadDividerHiding,
        messagesRef,
        bottomPanelRef,
        showJumpDown,
        jumpBottomOffset,
        newMessagesCount,
        isActiveConversationClosed,
        text,
        busy,
        assistBusy,
        generatingStatus,
        replySuggestions,
        connectionError,
        isReconnectingNow,
        reconnectIn,
        error,
        assistHint,
        onCreateClientConversation: createClientConversation,
        onCloseTicket: closeTicket,
        onTransferTicket: transferTicket,
        onToggleRightCollapsed: () => setRightCollapsed((v) => !v),
        onMessagesScroll: handleMessagesScroll,
        onJumpToBottom: jumpToBottom,
        onSuggest,
        onImprove,
        onSend: sendCurrentMessage,
        onTextChange: (event) => setText(event.target.value),
        onTextKeyDown: (event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            sendCurrentMessage()
          }
        },
        onHideSuggestions: () => setReplySuggestions([]),
        onSelectSuggestion: (suggestion) => {
          setText(suggestion)
          setReplySuggestions([])
          setAssistHint('Вариант подставлен в поле ввода.')
        },
      }}
      sidebar={{
        mobileMode,
        activeConversation,
        activeClientEmail,
        clientHistory,
        conversationId,
        role,
        activeTags,
        suggestedTags,
        frequentTags: FREQUENT_TAGS,
        manualTag,
        showTagDropdown,
        tagDropdownRef,
        assignClientId,
        assignWorkerId,
        clients,
        workers,
        onTakeConversation: takeSelectedConversation,
        onTogglePriority: togglePriority,
        onAddTag: addTag,
        onRemoveTag: removeTag,
        onManualTagChange: setManualTag,
        onShowTagDropdown: () => setShowTagDropdown(true),
        onHideTagDropdown: () => setShowTagDropdown(false),
        onAssignClientId: setAssignClientId,
        onAssignWorkerId: setAssignWorkerId,
        onAssignWorker: assignSelectedWorker,
      }}
    />
  )
}
