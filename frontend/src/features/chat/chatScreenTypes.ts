import type { ChangeEventHandler, KeyboardEventHandler, RefObject, UIEventHandler } from 'react'

import type { ChatMessage, Conversation } from '../../api'
import type { Role } from '../../store'
import type { ClientOption, WorkerOption } from './store/chatStore'

export type ConversationPanelProps = {
  email: string
  role: Role
  search: string
  conversations: Conversation[]
  conversationId: number | null
  onSearchChange: (search: string) => void
  onTakeConversation: (conversationId: number) => void
  onLogout: () => void
}

export type ChatCenterPanelProps = {
  mobileMode: 'list' | 'chat' | 'info'
  activeConversation: Conversation | null
  role: Role
  conversationId: number | null
  rightCollapsed: boolean
  messages: ChatMessage[]
  myId: number | null
  firstUnreadId: number | null
  isUnreadDividerHiding: boolean
  messagesRef: RefObject<HTMLDivElement | null>
  bottomPanelRef: RefObject<HTMLDivElement | null>
  showJumpDown: boolean
  jumpBottomOffset: number
  newMessagesCount: number
  isActiveConversationClosed: boolean
  text: string
  busy: boolean
  assistBusy: boolean
  generatingStatus: string
  replySuggestions: string[]
  connectionError: boolean
  isReconnectingNow: boolean
  reconnectIn: number | null
  error: string
  assistHint: string
  onCreateClientConversation: () => void
  onCloseTicket: () => void
  onTransferTicket: () => void
  onToggleRightCollapsed: () => void
  onMessagesScroll: UIEventHandler<HTMLDivElement>
  onJumpToBottom: () => void
  onSuggest: () => void
  onImprove: () => void
  onSend: () => void
  onTextChange: ChangeEventHandler<HTMLInputElement>
  onTextKeyDown: KeyboardEventHandler<HTMLInputElement>
  onHideSuggestions: () => void
  onSelectSuggestion: (suggestion: string) => void
}

export type ChatSidebarPanelProps = {
  mobileMode: 'list' | 'chat' | 'info'
  activeConversation: Conversation | null
  activeClientEmail: string
  clientHistory: Conversation[]
  conversationId: number | null
  role: Role
  activeTags: string[]
  suggestedTags: string[]
  frequentTags: string[]
  manualTag: string
  showTagDropdown: boolean
  tagDropdownRef: RefObject<HTMLDivElement | null>
  assignClientId: number | null
  assignWorkerId: number | null
  clients: ClientOption[]
  workers: WorkerOption[]
  onTakeConversation: (conversationId: number) => void
  onTogglePriority: () => Promise<void>
  onAddTag: (tag: string) => Promise<void>
  onRemoveTag: (tag: string) => Promise<void>
  onManualTagChange: (tag: string) => void
  onShowTagDropdown: () => void
  onHideTagDropdown: () => void
  onAssignClientId: (clientId: number) => void
  onAssignWorkerId: (workerId: number) => void
  onAssignWorker: () => void
}

export type ChatLayoutProps = {
  rightCollapsed: boolean
  conversation: ConversationPanelProps
  center: ChatCenterPanelProps
  sidebar: ChatSidebarPanelProps
}
