import { useCallback, useState } from 'react'

import { useAssistStore } from '../../../store'
import type { ChatLayoutProps } from '../chatScreenTypes'
import { useChatViewModel } from '../hooks/useChatViewModel'
import { useComposerState } from '../hooks/useComposerState'
import { useConversationHistory } from '../hooks/useConversationHistory'
import {
  buildChatCenterPanelProps,
  buildChatLayoutProps,
  buildChatSidebarPanelProps,
  buildConversationPanelProps,
} from './buildChatScreenProps'
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

  const sharedPanelContext = {
    auth,
    sidebar,
    viewModel,
    tickets: ticketWorkflow,
  }

  return buildChatLayoutProps({
    rightCollapsed: sidebar.rightCollapsed,
    conversation: buildConversationPanelProps(sharedPanelContext),
    center: buildChatCenterPanelProps({
      ...sharedPanelContext,
      composer,
      composerWorkflow,
      error,
      runtime,
    }),
    sidebar: buildChatSidebarPanelProps(sharedPanelContext),
  })
}
