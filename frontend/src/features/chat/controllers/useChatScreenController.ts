import { useCallback, useState } from 'react'

import { useAssistStore } from '../../../store'
import { FREQUENT_TAGS } from '../chatConstants'
import type { ChatLayoutProps } from '../chatScreenTypes'
import { useChatViewModel } from '../hooks/useChatViewModel'
import { useComposerState } from '../hooks/useComposerState'
import { useConversationHistory } from '../hooks/useConversationHistory'
import { useComposerWorkflowController } from './useComposerWorkflowController'
import { useChatRuntimeController } from './useChatRuntimeController'
import { useSidebarWorkflowController } from './useSidebarWorkflowController'
import { useTicketWorkflowController } from './useTicketWorkflowController'

export function useChatScreenController(): ChatLayoutProps {
  const auth = useAssistStore()
  const [error, setError] = useState('')
  const composer = useComposerState()
  const sidebar = useSidebarWorkflowController({
    token: auth.token,
    conversationId: auth.conversationId,
    role: auth.role,
  })

  const runtime = useChatRuntimeController({
    token: auth.token,
    role: auth.role,
    theme: auth.theme,
    conversationId: auth.conversationId,
    text: composer.text,
    assistHint: composer.assistHint,
    error,
    viewportWidth: sidebar.viewportWidth,
    setRightCollapsed: sidebar.setRightCollapsed,
    setError,
  })

  const handleHistoryError = useCallback((message: string) => {
    setError(message)
  }, [])

  useConversationHistory({
    token: auth.token,
    conversationId: auth.conversationId,
    onError: handleHistoryError,
  })

  const viewModel = useChatViewModel({
    conversationId: auth.conversationId,
    role: auth.role,
    email: auth.email,
    search: sidebar.search,
  })

  const composerWorkflow = useComposerWorkflowController({
    token: auth.token,
    role: auth.role,
    conversationId: auth.conversationId,
    setConversationId: auth.setConversationId,
    isActiveConversationClosed: viewModel.isActiveConversationClosed,
    messages: runtime.messages,
    myId: runtime.myId,
    text: composer.text,
    setText: composer.setText,
    setBusy: composer.setBusy,
    setAssistBusy: composer.setAssistBusy,
    setAssistHint: composer.setAssistHint,
    setGeneratingStatus: composer.setGeneratingStatus,
    setReplySuggestions: composer.setReplySuggestions,
    setError,
    clearUnreadDividerSmooth: runtime.scroll.clearUnreadDividerSmooth,
    forceScrollOnNextRenderRef: runtime.scroll.forceScrollOnNextRenderRef,
    isAtBottomRef: runtime.scroll.isAtBottomRef,
  })

  const ticketWorkflow = useTicketWorkflowController({
    token: auth.token,
    role: auth.role,
    conversationId: auth.conversationId,
    setConversationId: auth.setConversationId,
    activeTags: viewModel.activeTags,
    setFirstUnreadId: runtime.scroll.setFirstUnreadId,
    forceScrollOnNextRenderRef: runtime.scroll.forceScrollOnNextRenderRef,
    setText: composer.setText,
    setReplySuggestions: composer.setReplySuggestions,
    setError,
    setAssistHint: composer.setAssistHint,
  })

  const conversationProps = {
    email: auth.email,
    role: auth.role,
    search: sidebar.search,
    conversations: viewModel.filteredConversations,
    conversationId: auth.conversationId,
    onSearchChange: sidebar.setSearch,
    onTakeConversation: ticketWorkflow.takeSelectedConversation,
    onLogout: auth.logout,
  }

  const centerProps = {
    mobileMode: sidebar.mobileMode,
    activeConversation: viewModel.activeConversation,
    role: auth.role,
    conversationId: auth.conversationId,
    rightCollapsed: sidebar.rightCollapsed,
    messages: runtime.messages,
    myId: runtime.myId,
    firstUnreadId: runtime.scroll.firstUnreadId,
    isUnreadDividerHiding: runtime.scroll.isUnreadDividerHiding,
    messagesRef: runtime.scroll.messagesRef,
    bottomPanelRef: runtime.scroll.bottomPanelRef,
    showJumpDown: runtime.scroll.showJumpDown,
    jumpBottomOffset: runtime.scroll.jumpBottomOffset,
    newMessagesCount: runtime.scroll.newMessagesCount,
    isActiveConversationClosed: viewModel.isActiveConversationClosed,
    text: composer.text,
    busy: composer.busy,
    assistBusy: composer.assistBusy,
    generatingStatus: composer.generatingStatus,
    replySuggestions: composer.replySuggestions,
    connectionError: runtime.connectionError,
    isReconnectingNow: runtime.isReconnectingNow,
    reconnectIn: runtime.reconnectIn,
    error,
    assistHint: composer.assistHint,
    onCreateClientConversation: ticketWorkflow.createClientConversation,
    onCloseTicket: ticketWorkflow.closeTicket,
    onTransferTicket: ticketWorkflow.transferTicket,
    onToggleRightCollapsed: () => sidebar.setRightCollapsed((value) => !value),
    onMessagesScroll: runtime.scroll.handleMessagesScroll,
    onJumpToBottom: runtime.scroll.jumpToBottom,
    onSuggest: composerWorkflow.onSuggest,
    onImprove: composerWorkflow.onImprove,
    onSend: composerWorkflow.onSend,
    onTextChange: composerWorkflow.onTextChange,
    onTextKeyDown: composerWorkflow.onTextKeyDown,
    onHideSuggestions: composerWorkflow.onHideSuggestions,
    onSelectSuggestion: composerWorkflow.onSelectSuggestion,
  }

  const sidebarProps = {
    mobileMode: sidebar.mobileMode,
    activeConversation: viewModel.activeConversation,
    activeClientEmail: viewModel.activeClientEmail,
    clientHistory: sidebar.clientHistory,
    conversationId: auth.conversationId,
    role: auth.role,
    activeTags: viewModel.activeTags,
    suggestedTags: sidebar.suggestedTags,
    frequentTags: FREQUENT_TAGS,
    manualTag: sidebar.manualTag,
    showTagDropdown: sidebar.showTagDropdown,
    tagDropdownRef: sidebar.tagDropdownRef,
    assignClientId: sidebar.assignClientId,
    assignWorkerId: sidebar.assignWorkerId,
    clients: sidebar.clients,
    workers: sidebar.workers,
    onTakeConversation: ticketWorkflow.takeSelectedConversation,
    onTogglePriority: ticketWorkflow.togglePriority,
    onAddTag: ticketWorkflow.addTag,
    onRemoveTag: ticketWorkflow.removeTag,
    onManualTagChange: sidebar.setManualTag,
    onShowTagDropdown: sidebar.onShowTagDropdown,
    onHideTagDropdown: sidebar.onHideTagDropdown,
    onAssignClientId: sidebar.setAssignClientId,
    onAssignWorkerId: sidebar.setAssignWorkerId,
    onAssignWorker: ticketWorkflow.assignSelectedWorker,
  }

  return {
    rightCollapsed: sidebar.rightCollapsed,
    conversation: conversationProps,
    center: centerProps,
    sidebar: sidebarProps,
  }
}
