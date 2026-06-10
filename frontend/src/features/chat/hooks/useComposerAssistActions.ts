import { improveDraft, suggestReply } from '../../../api'
import type { ChatMessage } from '../../../api'

type UseComposerAssistActionsParams = {
  token: string
  text: string
  conversationId: number | null
  messages: ChatMessage[]
  myId: number | null
  setText: (value: string) => void
  setAssistBusy: (value: boolean) => void
  setGeneratingStatus: (value: string) => void
  setError: (message: string) => void
  setReplySuggestions: (suggestions: string[]) => void
  setAssistHint: (message: string) => void
}

export function useComposerAssistActions({
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
}: UseComposerAssistActionsParams) {
  const suggest = async () => {
    if (!token) return
    const fallbackIncoming = [...messages].reverse().find((message) => myId !== null && message.sender_id !== myId)?.text || ''
    const sourceText = text.trim().length > 0 ? text.trim() : fallbackIncoming.trim()
    if (sourceText.length < 3) {
      setError('Нет текста для подсказки. Напишите сообщение или дождитесь сообщения собеседника.')
      return
    }
    setAssistBusy(true)
    setGeneratingStatus('Генерация ответа нейросетью...')
    setError('')
    try {
      const result = await suggestReply(token, sourceText, conversationId ?? undefined)
      setReplySuggestions(result.suggestions)
      setAssistHint(result.suggestions.length > 0 ? 'Выберите подходящий вариант ответа.' : 'Нейросеть не вернула варианты ответа.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось подсказать ответ')
    } finally {
      setAssistBusy(false)
      setGeneratingStatus('')
    }
  }

  const improve = async () => {
    if (!token || text.trim().length < 3) return
    setAssistBusy(true)
    setGeneratingStatus('Генерация ответа нейросетью...')
    setError('')
    try {
      const result = await improveDraft(token, text.trim(), conversationId ?? undefined)
      setText(result.improved_text)
      setReplySuggestions([])
      setAssistHint('Готово: текст стал более деловым и понятным.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось улучшить текст')
    } finally {
      setAssistBusy(false)
      setGeneratingStatus('')
    }
  }

  return { suggest, improve }
}
