import { FREQUENT_TAGS } from '../chatConstants'
import type { ChatCenterPanelProps, ChatLayoutProps, ChatSidebarPanelProps, ConversationPanelProps } from '../chatScreenTypes'
import type { useAssistStore } from '../../../store'
import type { useChatViewModel } from '../hooks/useChatViewModel'
import type { useComposerState } from '../hooks/useComposerState'
import type { useComposerWorkflowController } from './useComposerWorkflowController'
import type { useChatRuntimeController } from './useChatRuntimeController'
import type { useSidebarWorkflowController } from './useSidebarWorkflowController'
import type { useTicketWorkflowController } from './useTicketWorkflowController'

type AuthContext = ReturnType<typeof useAssistStore.getState>
type ComposerState = ReturnType<typeof useComposerState>
type ComposerWorkflow = ReturnType<typeof useComposerWorkflowController>
type RuntimeController = ReturnType<typeof useChatRuntimeController>
type SidebarWorkflow = ReturnType<typeof useSidebarWorkflowController>
type TicketWorkflow = ReturnType<typeof useTicketWorkflowController>
type ViewModel = ReturnType<typeof useChatViewModel>

type SharedPanelContext = {
  auth: AuthContext
  sidebar: SidebarWorkflow
  viewModel: ViewModel
  tickets: TicketWorkflow
}

export function buildConversationPanelProps({
  auth,
  sidebar,
  viewModel,
  tickets,
}: SharedPanelContext): ConversationPanelProps {
  return {
    email: auth.email,
    role: auth.role,
    search: sidebar.search,
    conversations: viewModel.filteredConversations,
    conversationId: auth.conversationId,
    onSearchChange: sidebar.setSearch,
    onTakeConversation: tickets.takeSelectedConversation,
    onLogout: auth.logout,
  }
}

export function buildChatCenterPanelProps({
  auth,
  composer,
  composerWorkflow,
  error,
  runtime,
  sidebar,
  tickets,
  viewModel,
}: SharedPanelContext & {
  composer: ComposerState
  composerWorkflow: ComposerWorkflow
  error: string
  runtime: RuntimeController
}): ChatCenterPanelProps {
  return {
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
    onCreateClientConversation: tickets.createClientConversation,
    onCloseTicket: tickets.closeTicket,
    onTransferTicket: tickets.transferTicket,
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
}

export function buildChatSidebarPanelProps({
  auth,
  sidebar,
  tickets,
  viewModel,
}: SharedPanelContext): ChatSidebarPanelProps {
  return {
    mobileMode: sidebar.mobileMode,
    activeConversation: viewModel.activeConversation,
    activeClientEmail: viewModel.activeClientEmail,
    clientHistory: sidebar.clientHistory,
    conversationId: auth.conversationId,
    role: auth.role,
    activeTags: viewModel.activeTags,
    suggestedTags: sidebar.suggestedTags,
    isGeneratingTags: sidebar.isGeneratingTags,
    frequentTags: FREQUENT_TAGS,
    manualTag: sidebar.manualTag,
    showTagDropdown: sidebar.showTagDropdown,
    tagDropdownRef: sidebar.tagDropdownRef,
    assignClientId: sidebar.assignClientId,
    assignWorkerId: sidebar.assignWorkerId,
    clients: sidebar.clients,
    workers: sidebar.workers,
    onTakeConversation: tickets.takeSelectedConversation,
    onTogglePriority: tickets.togglePriority,
    onAddTag: tickets.addTag,
    onRemoveTag: tickets.removeTag,
    onRegenerateTags: sidebar.onRegenerateTags,
    onManualTagChange: sidebar.setManualTag,
    onShowTagDropdown: sidebar.onShowTagDropdown,
    onHideTagDropdown: sidebar.onHideTagDropdown,
    onAssignClientId: sidebar.setAssignClientId,
    onAssignWorkerId: sidebar.setAssignWorkerId,
    onAssignWorker: tickets.assignSelectedWorker,
  }
}

export function buildChatLayoutProps({
  conversation,
  center,
  sidebar,
  rightCollapsed,
}: {
  conversation: ConversationPanelProps
  center: ChatCenterPanelProps
  sidebar: ChatSidebarPanelProps
  rightCollapsed: boolean
}): ChatLayoutProps {
  return {
    rightCollapsed,
    conversation,
    center,
    sidebar,
  }
}
