import { useCallback, useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import '../../supportChat.css'

import { getClientConversationHistory, getConversations, getMessages, markMessagesRead, sendMessage, startConversation, takeConversation } from '../../api'
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
import { useSidebarUiState } from './hooks/useSidebarUiState'
import { useSuggestedTags } from './hooks/useSuggestedTags'
import { useTicketActions } from './hooks/useTicketActions'
import { useWorkerAssignment } from './hooks/useWorkerAssignment'

export function ChatScreen() {
  const { token, role, email, theme, toggleTheme, logout, conversationId, setConversationId } = useAssistStore()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [error, setError] = useState('')
  const [connectionError, setConnectionError] = useState(false)
  const [reconnectIn, setReconnectIn] = useState<number | null>(null)
  const [isReconnectingNow, setIsReconnectingNow] = useState(false)
  const composer = useComposerState()
  const [myId, setMyId] = useState<number | null>(null)
  const reconnectPhaseStartedAtRef = useRef<number | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null)
  const [clients, setClients] = useState<{ id: number; email: string; assigned_worker_id: number | null }[]>([])
  const [workers, setWorkers] = useState<{ id: number; email: string }[]>([])
  const [assignClientId, setAssignClientId] = useState<number | null>(null)
  const [assignWorkerId, setAssignWorkerId] = useState<number | null>(null)
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
    setSelectedConversation((current) => (conversation.id === conversationId ? conversation : current))
  }, [conversationId])

  const handleHistoryError = useCallback((message: string) => {
    setError(message)
  }, [])

  const { clientHistory, setClientHistory } = useConversationHistory({
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

  const onSend = async () => {
    if (!token || text.trim().length < 1) return
    if (isActiveConversationClosed) {
      setError('')
      setAssistHint('Этот диалог закрыт. Начните новый диалог, чтобы написать сообщение.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const outgoingText = text.trim()
      let targetConversationId = conversationId
      if (!targetConversationId && role === 'client') {
        const conv = await startConversation(token)
        targetConversationId = conv.id
        setConversationId(conv.id)
        setSelectedConversation(conv)
        const list = await getConversations(token)
        setConversations(list)
      }
      if (!targetConversationId) {
        setError('Сначала выберите диалог из списка или создайте новый.')
        return
      }

      const item = await sendMessage(token, targetConversationId, outgoingText)
      setMessages((prev) => [...prev, item])
      clearUnreadDividerSmooth()
      setText('')
      setReplySuggestions([])
      const items = await getMessages(token, targetConversationId)
      forceScrollOnNextRenderRef.current = true
      setMessages(items)
      if (isAtBottomRef.current) {
        await markMessagesRead(token, targetConversationId)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Не удалось отправить сообщение'
      if (message.includes('Диалог закрыт')) {
        setError('')
        setAssistHint('Этот диалог уже закрыт. Нажмите + Новый диалог, чтобы продолжить.')
      } else {
        setError(message)
      }
    } finally {
      setBusy(false)
    }
  }

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

  const onTakeConversation = async (id: number) => {
    if (!token) return
    try {
      if (role !== 'client') {
        const taken = await takeConversation(token, id)
        setSelectedConversation(taken)
      }
      setConversationId(id)
      const [list, items, history] = await Promise.all([getConversations(token), getMessages(token, id), getClientConversationHistory(token, id)])
      setConversations(list)
      setSelectedConversation((current) => list.find((c) => c.id === id) || current || null)
      setClientHistory(history.length > 0 ? history : list.filter((c) => c.id === id))
      const firstUnread = items.find((m) => m.sender_id !== myId && !m.read_at)
      setFirstUnreadId(firstUnread?.id ?? null)
      forceScrollOnNextRenderRef.current = true
      setMessages(items)
      await markMessagesRead(token, id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось взять диалог')
    }
  }

  const { assignSelectedWorker } = useWorkerAssignment({
    token,
    assignClientId,
    assignWorkerId,
    setClients,
    setError,
  })

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
    setMessages((prev) => {
      if (prev.some((item) => item.id === message.id)) return prev
      return [...prev, message]
    })
    if (myId !== null && message.sender_id !== myId && !message.read_at && firstUnreadId === null && !isAtBottomRef.current) {
      setFirstUnreadId(message.id)
    }
    if (token && isAtBottomRef.current) {
      markMessagesRead(token, conversationId).catch(() => {})
    }
  }, [conversationId, token, myId, firstUnreadId])

  const handleSocketConversationsSnapshot = useCallback((items: Conversation[]) => {
    setConversations(items)
    setSelectedConversation((current) => {
      if (!current) return null
      return items.find((c) => c.id === current.id) || current
    })
  }, [])

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
          onTakeConversation={onTakeConversation}
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
              onSend={onSend}
              onTextChange={(e) => setText(e.target.value)}
              onTextKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  onSend()
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
          onTakeConversation={onTakeConversation}
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
