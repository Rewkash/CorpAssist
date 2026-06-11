import { create } from 'zustand'

import type { ChatMessage, Conversation } from '../../../api'

export type ClientOption = { id: number; email: string; assigned_worker_id: number | null }
export type WorkerOption = { id: number; email: string }

type ValueOrUpdater<T> = T | ((prev: T) => T)

type ChatDomainState = {
  messages: ChatMessage[]
  conversations: Conversation[]
  selectedConversation: Conversation | null
  clientHistory: Conversation[]
  clients: ClientOption[]
  workers: WorkerOption[]
  myId: number | null
  connectionError: boolean
  reconnectIn: number | null
  isReconnectingNow: boolean
  assignClientId: number | null
  assignWorkerId: number | null
}

type ChatDomainActions = {
  setMessages: (value: ValueOrUpdater<ChatMessage[]>) => void
  appendMessageIfMissing: (message: ChatMessage) => void
  setConversations: (value: ValueOrUpdater<Conversation[]>) => void
  setConversationsSnapshot: (items: Conversation[]) => void
  setSelectedConversation: (value: ValueOrUpdater<Conversation | null>) => void
  updateSelectedConversation: (conversation: Conversation) => void
  setClientHistory: (value: ValueOrUpdater<Conversation[]>) => void
  setClients: (clients: ClientOption[]) => void
  setWorkers: (workers: WorkerOption[]) => void
  setMyId: (myId: number | null) => void
  setConnectionError: (connectionError: boolean) => void
  setReconnectIn: (reconnectIn: number | null) => void
  setIsReconnectingNow: (isReconnectingNow: boolean) => void
  setAssignClientId: (assignClientId: number | null) => void
  setAssignWorkerId: (assignWorkerId: number | null) => void
  resetActiveConversationState: () => void
}

export type ChatDomainStore = ChatDomainState & ChatDomainActions

const resolveValue = <T>(current: T, value: ValueOrUpdater<T>) => {
  return typeof value === 'function' ? (value as (prev: T) => T)(current) : value
}

export const useChatStore = create<ChatDomainStore>((set) => ({
  messages: [],
  conversations: [],
  selectedConversation: null,
  clientHistory: [],
  clients: [],
  workers: [],
  myId: null,
  connectionError: false,
  reconnectIn: null,
  isReconnectingNow: false,
  assignClientId: null,
  assignWorkerId: null,

  setMessages: (value) => set((state) => ({ messages: resolveValue(state.messages, value) })),
  appendMessageIfMissing: (message) => set((state) => {
    if (state.messages.some((item) => item.id === message.id)) return state
    return { messages: [...state.messages, message] }
  }),
  setConversations: (value) => set((state) => ({ conversations: resolveValue(state.conversations, value) })),
  setConversationsSnapshot: (items) => set((state) => ({
    conversations: items,
    selectedConversation: state.selectedConversation
      ? items.find((conversation) => conversation.id === state.selectedConversation?.id) || state.selectedConversation
      : null,
  })),
  setSelectedConversation: (value) => set((state) => ({
    selectedConversation: resolveValue(state.selectedConversation, value),
  })),
  updateSelectedConversation: (conversation) => set((state) => ({
    selectedConversation: state.selectedConversation?.id === conversation.id ? conversation : state.selectedConversation,
  })),
  setClientHistory: (value) => set((state) => ({ clientHistory: resolveValue(state.clientHistory, value) })),
  setClients: (clients) => set({ clients }),
  setWorkers: (workers) => set({ workers }),
  setMyId: (myId) => set({ myId }),
  setConnectionError: (connectionError) => set({ connectionError }),
  setReconnectIn: (reconnectIn) => set({ reconnectIn }),
  setIsReconnectingNow: (isReconnectingNow) => set({ isReconnectingNow }),
  setAssignClientId: (assignClientId) => set({ assignClientId }),
  setAssignWorkerId: (assignWorkerId) => set({ assignWorkerId }),
  resetActiveConversationState: () => set({
    messages: [],
    selectedConversation: null,
    clientHistory: [],
  }),
}))
