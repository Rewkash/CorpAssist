import { useCallback, useState } from 'react'
import '../../supportChat.css'

import { useAssistStore } from '../../store'
import { ChatLayout } from './ChatLayout'
import { FREQUENT_TAGS } from './chatConstants'
import { useComposerWorkflowController } from './controllers/useComposerWorkflowController'
import { useChatRuntimeController } from './controllers/useChatRuntimeController'
import { useSidebarWorkflowController } from './controllers/useSidebarWorkflowController'
import { useTicketWorkflowController } from './controllers/useTicketWorkflowController'
import { useChatViewModel } from './hooks/useChatViewModel'
import { useComposerState } from './hooks/useComposerState'
import { useConversationHistory } from './hooks/useConversationHistory'

export function ChatScreen() {
  const { token, role, email, theme, toggleTheme, logout, conversationId, setConversationId } = useAssistStore()
  const [error, setError] = useState('')
  const composer = useComposerState()
  const sidebar = useSidebarWorkflowController({ token, conversationId, role })

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
    tagDropdownRef,
    clientHistory,
    clients,
    workers,
    assignClientId,
    assignWorkerId,
    setAssignClientId,
    setAssignWorkerId,
    suggestedTags,
    onShowTagDropdown,
    onHideTagDropdown,
  } = sidebar

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
    messages,
    myId,
    connectionError,
    reconnectIn,
    isReconnectingNow,
    scroll,
  } = useChatRuntimeController({
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
  })

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
  } = scroll

  const handleHistoryError = useCallback((message: string) => {
    setError(message)
  }, [])

  useConversationHistory({
    token,
    conversationId,
    onError: handleHistoryError,
  })

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

  const composerWorkflow = useComposerWorkflowController({
    token,
    role,
    conversationId,
    setConversationId,
    isActiveConversationClosed,
    messages,
    myId,
    text,
    setText,
    setBusy,
    setAssistBusy,
    setAssistHint,
    setGeneratingStatus,
    setReplySuggestions,
    setError,
    clearUnreadDividerSmooth,
    forceScrollOnNextRenderRef,
    isAtBottomRef,
  })

  const ticketWorkflow = useTicketWorkflowController({
    token,
    role,
    conversationId,
    setConversationId,
    activeTags,
    setFirstUnreadId,
    forceScrollOnNextRenderRef,
    setText,
    setReplySuggestions,
    setError,
    setAssistHint,
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
        onTakeConversation: ticketWorkflow.takeSelectedConversation,
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
        onCreateClientConversation: ticketWorkflow.createClientConversation,
        onCloseTicket: ticketWorkflow.closeTicket,
        onTransferTicket: ticketWorkflow.transferTicket,
        onToggleRightCollapsed: () => setRightCollapsed((v) => !v),
        onMessagesScroll: handleMessagesScroll,
        onJumpToBottom: jumpToBottom,
        onSuggest: composerWorkflow.onSuggest,
        onImprove: composerWorkflow.onImprove,
        onSend: composerWorkflow.onSend,
        onTextChange: composerWorkflow.onTextChange,
        onTextKeyDown: composerWorkflow.onTextKeyDown,
        onHideSuggestions: composerWorkflow.onHideSuggestions,
        onSelectSuggestion: composerWorkflow.onSelectSuggestion,
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
        onTakeConversation: ticketWorkflow.takeSelectedConversation,
        onTogglePriority: ticketWorkflow.togglePriority,
        onAddTag: ticketWorkflow.addTag,
        onRemoveTag: ticketWorkflow.removeTag,
        onManualTagChange: setManualTag,
        onShowTagDropdown,
        onHideTagDropdown,
        onAssignClientId: setAssignClientId,
        onAssignWorkerId: setAssignWorkerId,
        onAssignWorker: ticketWorkflow.assignSelectedWorker,
      }}
    />
  )
}
