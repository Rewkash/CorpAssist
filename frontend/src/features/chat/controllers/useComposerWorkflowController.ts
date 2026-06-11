import { useCallback } from 'react'
import type { ChangeEvent, KeyboardEvent, MutableRefObject } from 'react'

import type { ChatMessage } from '../../../api'
import type { Role } from '../../../store'
import { useComposerAssistActions } from '../hooks/useComposerAssistActions'
import { useMessageSending } from '../hooks/useMessageSending'

type UseComposerWorkflowControllerParams = {
  token: string
  role: Role | null
  conversationId: number | null
  setConversationId: (conversationId: number | null) => void
  isActiveConversationClosed: boolean
  messages: ChatMessage[]
  myId: number | null
  text: string
  setText: (value: string) => void
  setBusy: (value: boolean) => void
  setAssistBusy: (value: boolean) => void
  setAssistHint: (value: string) => void
  setGeneratingStatus: (value: string) => void
  setReplySuggestions: (value: string[]) => void
  setError: (value: string) => void
  clearUnreadDividerSmooth: () => void
  forceScrollOnNextRenderRef: MutableRefObject<boolean>
  isAtBottomRef: MutableRefObject<boolean>
}

export function useComposerWorkflowController({
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
}: UseComposerWorkflowControllerParams) {
  const { sendCurrentMessage } = useMessageSending({
    auth: { token, role },
    guards: { isActiveConversationClosed },
    conversation: {
      conversationId,
      setConversationId,
    },
    composer: {
      text,
      setText,
      setBusy,
      setError,
      setAssistHint,
      setReplySuggestions,
    },
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

  const handleTextChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setText(event.target.value)
  }, [setText])

  const handleTextKeyDown = useCallback((event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendCurrentMessage()
    }
  }, [sendCurrentMessage])

  const hideSuggestions = useCallback(() => {
    setReplySuggestions([])
  }, [setReplySuggestions])

  const selectSuggestion = useCallback((suggestion: string) => {
    setText(suggestion)
    setReplySuggestions([])
    setAssistHint('Вариант подставлен в поле ввода.')
  }, [setAssistHint, setReplySuggestions, setText])

  return {
    onSend: sendCurrentMessage,
    onSuggest,
    onImprove,
    onTextChange: handleTextChange,
    onTextKeyDown: handleTextKeyDown,
    onHideSuggestions: hideSuggestions,
    onSelectSuggestion: selectSuggestion,
  }
}
