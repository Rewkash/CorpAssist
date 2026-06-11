import type { MutableRefObject } from 'react'

import type { Role } from '../../../store'
import { useConversationTags } from '../hooks/useConversationTags'
import { useTakeConversation } from '../hooks/useTakeConversation'
import { useTicketActions } from '../hooks/useTicketActions'
import { useWorkerAssignment } from '../hooks/useWorkerAssignment'

type UseTicketWorkflowControllerParams = {
  token: string
  role: Role | null
  conversationId: number | null
  setConversationId: (conversationId: number | null) => void
  activeTags: string[]
  setFirstUnreadId: (value: number | null) => void
  forceScrollOnNextRenderRef: MutableRefObject<boolean>
  setText: (value: string) => void
  setReplySuggestions: (value: string[]) => void
  setError: (value: string) => void
  setAssistHint: (value: string) => void
}

export function useTicketWorkflowController({
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
}: UseTicketWorkflowControllerParams) {
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

  return {
    takeSelectedConversation,
    assignSelectedWorker,
    addTag,
    removeTag,
    togglePriority,
    closeTicket,
    transferTicket,
    createClientConversation,
  }
}
