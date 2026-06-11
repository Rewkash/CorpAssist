import { useCallback } from 'react'

import type { Role } from '../../../store'
import { useOutsideClick } from '../../../hooks/useOutsideClick'
import { useSidebarUiState } from '../hooks/useSidebarUiState'
import { useSuggestedTags } from '../hooks/useSuggestedTags'
import { useChatStore } from '../store/chatStore'

type UseSidebarWorkflowControllerParams = {
  token: string
  conversationId: number | null
  role: Role | null
}

export function useSidebarWorkflowController({ token, conversationId, role }: UseSidebarWorkflowControllerParams) {
  const clientHistory = useChatStore((state) => state.clientHistory)
  const clients = useChatStore((state) => state.clients)
  const workers = useChatStore((state) => state.workers)
  const assignClientId = useChatStore((state) => state.assignClientId)
  const assignWorkerId = useChatStore((state) => state.assignWorkerId)
  const setAssignClientId = useChatStore((state) => state.setAssignClientId)
  const setAssignWorkerId = useChatStore((state) => state.setAssignWorkerId)
  const sidebarUi = useSidebarUiState()
  const suggestedTags = useSuggestedTags({ token, conversationId, role })

  const hideTagDropdown = useCallback(() => {
    sidebarUi.setShowTagDropdown(false)
  }, [sidebarUi.setShowTagDropdown])

  const showTagDropdown = useCallback(() => {
    sidebarUi.setShowTagDropdown(true)
  }, [sidebarUi.setShowTagDropdown])

  useOutsideClick(sidebarUi.tagDropdownRef, hideTagDropdown)

  return {
    ...sidebarUi,
    clientHistory,
    clients,
    workers,
    assignClientId,
    assignWorkerId,
    setAssignClientId,
    setAssignWorkerId,
    suggestedTags,
    onShowTagDropdown: showTagDropdown,
    onHideTagDropdown: hideTagDropdown,
  }
}
