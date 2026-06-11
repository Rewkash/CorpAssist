import { useCallback, useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import '../../supportChat.css'

import { markMessagesRead } from '../../api'
import type { ChatMessage, Conversation } from '../../api'
import { ChatHeader } from '../../components/ChatHeader'
import { ClosedConversationPanel } from '../../components/ClosedConversationPanel'
import { ConversationList } from '../../components/ConversationList'
import { JumpToBottomButton } from '../../components/JumpToBottomButton'
import { MessageComposer } from '../../components/MessageComposer'
import { MessageList } from '../../components/MessageList'
import { RightSidebar } from '../../components/RightSidebar'
import { useDocumentThemeClass } from '../../hooks/useDocumentThemeClass'
import { useOutsideClick } from '../../hooks/useOutsideClick'
import { useChat } from '../../useChat'
import { useAssistStore } from '../../store'
import { formatHistoryDate } from './chatFormatters'
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
  const conversations = useChatStore((state) => state.conversations)
  const selectedConversation = useChatStore((state) => state.selectedConversation)
  const clientHistory = useChatStore((state) => state.clientHistory)
  const clients = useChatStore((state) => state.clients)
  const workers = useChatStore((state) => state.workers)
  const myId = useChatStore((state) => state.myId)
  const connectionError = useChatStore((state) => state.connectionError)
  const reconnectIn = useChatStore((state) => state.reconnectIn)
  const isReconnectingNow = useChatStore((state) => state.isReconnectingNow)
  const assignClientId = useChatStore((state) => state.assignClientId)
  const assignWorkerId = useChatStore((state) => state.assignWorkerId)
  const setMessages = useChatStore((state) => state.setMessages)
  const appendMessageIfMissing = useChatStore((state) => state.appendMessageIfMissing)
  const setConversations = useChatStore((state) => state.setConversations)
  const setConversationsSnapshot = useChatStore((state) => state.setConversationsSnapshot)
  const setSelectedConversation = useChatStore((state) => state.setSelectedConversation)
  const updateSelectedConversation = useChatStore((state) => state.updateSelectedConversation)
  const setClientHistory = useChatStore((state) => state.setClientHistory)
  const setClients = useChatStore((state) => state.setClients)
  const setWorkers = useChatStore((state) => state.setWorkers)
  const setMyId = useChatStore((state) => state.setMyId)
  const setConnectionError = useChatStore((state) => state.setConnectionError)
  const setReconnectIn = useChatStore((state) => state.setReconnectIn)
  const setIsReconnectingNow = useChatStore((state) => state.setIsReconnectingNow)
  const setAssignClientId = useChatStore((state) => state.setAssignClientId)
  const setAssignWorkerId = useChatStore((state) => state.setAssignWorkerId)
  const sidebarUi = useSidebarUiState()
  const suggestedTags = useSuggestedTags({ token, conversationId, role })
  const frequentTags = ['Миграция', 'Срочно', 'VIP', 'Ожидание', 'Технический', 'Оплата']

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

  const handleSelectedConversationUpdate = useCallback((conversation: Conversation) => {
    updateSelectedConversation(conversation)
  }, [updateSelectedConversation])

  const handleHistoryError = useCallback((message: string) => {
    setError(message)
  }, [])

  useConversationHistory({
    token,
    conversationId,
    selectedConversation,
    conversations,
    onSelectedConversationUpdate: handleSelectedConversationUpdate,
    onError: handleHistoryError,
  })

  useChatBootstrap({
    token,
    role,
    conversationId,
    reconnectPhaseStartedAtRef,
    forceScrollOnNextRenderRef,
    setConnectionError,
    setIsReconnectingNow,
    setReconnectIn,
    setError,
    setMyId,
    setConversations,
    setSelectedConversation,
    setMessages,
    setFirstUnreadId,
    setClients,
    setWorkers,
    setAssignClientId,
    setAssignWorkerId,
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
    conversations,
    clientHistory,
    selectedConversation,
    clients,
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
      setSelectedConversation,
      setConversations,
    },
    composer: {
      text,
      setText,
      setBusy,
      setError,
      setAssistHint,
      setReplySuggestions,
    },
    messages: { setMessages },
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
    myId,
    setConversationId,
    setConversations,
    setSelectedConversation,
    setClientHistory,
    setMessages,
    setFirstUnreadId,
    forceScrollOnNextRenderRef,
    setError,
  })

  const { assignSelectedWorker } = useWorkerAssignment({
    token,
    assignClientId,
    assignWorkerId,
    setClients,
    setError,
  })

  const { addTag, removeTag, togglePriority } = useConversationTags({
    token,
    conversationId,
    role,
    activeTags,
    setConversations,
    setSelectedConversation,
    setClientHistory,
    setError,
  })

  const { closeTicket, transferTicket, createClientConversation } = useTicketActions({
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
    <div className="supportRoot">
      <div
        className={clsx('appShell', rightCollapsed && 'rightCollapsed')}
      >
        <ConversationList
          email={email}
          role={role}
          search={search}
          conversations={filteredConversations}
          conversationId={conversationId}
          onSearchChange={setSearch}
          onTakeConversation={takeSelectedConversation}
          onLogout={logout}
        />

        <main className="center" style={{ display: mobileMode === 'chat' ? 'flex' : undefined }}>
          <ChatHeader
            activeConversation={activeConversation}
            role={role}
            conversationId={conversationId}
            rightCollapsed={rightCollapsed}
            onCreateClientConversation={createClientConversation}
            onCloseTicket={closeTicket}
            onTransferTicket={transferTicket}
            onToggleRightCollapsed={() => setRightCollapsed((v) => !v)}
          />
          <MessageList
            conversationId={conversationId}
            messages={messages}
            myId={myId}
            firstUnreadId={firstUnreadId}
            isUnreadDividerHiding={isUnreadDividerHiding}
            messagesRef={messagesRef}
            onScroll={handleMessagesScroll}
          />
          {showJumpDown && (
            <JumpToBottomButton bottomOffset={jumpBottomOffset} newMessagesCount={newMessagesCount} onClick={jumpToBottom} />
          )}
          {isActiveConversationClosed ? (
            <ClosedConversationPanel closedAt={activeConversation?.closed_at} bottomPanelRef={bottomPanelRef} />
          ) : (
            <MessageComposer
              text={text}
              busy={busy}
              role={role}
              conversationId={conversationId}
              assistBusy={assistBusy}
              generatingStatus={generatingStatus}
              replySuggestions={replySuggestions}
              connectionError={connectionError}
              isReconnectingNow={isReconnectingNow}
              reconnectIn={reconnectIn}
              error={error}
              assistHint={assistHint}
              bottomPanelRef={bottomPanelRef}
              onSuggest={onSuggest}
              onImprove={onImprove}
              onSend={sendCurrentMessage}
              onTextChange={(e) => setText(e.target.value)}
              onTextKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendCurrentMessage()
                }
              }}
              onHideSuggestions={() => setReplySuggestions([])}
              onSelectSuggestion={(suggestion) => {
                setText(suggestion)
                setReplySuggestions([])
                setAssistHint('Вариант подставлен в поле ввода.')
              }}
            />
          )}
        </main>

        <RightSidebar
          mobileMode={mobileMode}
          activeConversation={activeConversation}
          activeClientEmail={activeClientEmail}
          clientHistory={clientHistory}
          conversationId={conversationId}
          role={role}
          activeTags={activeTags}
          suggestedTags={suggestedTags}
          frequentTags={frequentTags}
          manualTag={manualTag}
          showTagDropdown={showTagDropdown}
          tagDropdownRef={tagDropdownRef}
          assignClientId={assignClientId}
          assignWorkerId={assignWorkerId}
          clients={clients}
          workers={workers}
          onTakeConversation={takeSelectedConversation}
          onTogglePriority={() => void togglePriority()}
          onAddTag={(tag) => void addTag(tag)}
          onRemoveTag={(tag) => void removeTag(tag)}
          onManualTagChange={setManualTag}
          onShowTagDropdown={() => setShowTagDropdown(true)}
          onHideTagDropdown={() => setShowTagDropdown(false)}
          onAssignClientId={setAssignClientId}
          onAssignWorkerId={setAssignWorkerId}
          onAssignWorker={assignSelectedWorker}
          formatHistoryDate={formatHistoryDate}
        />
      </div>
    </div>
  )
}
