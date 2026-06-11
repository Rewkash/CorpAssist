import { getConversations, setConversationTags } from '../../../api'
import type { Role } from '../../../store'
import { useChatStore } from '../store/chatStore'

type UseConversationTagsParams = {
  token: string
  conversationId: number | null
  role: Role | null
  activeTags: string[]
  setError: (message: string) => void
}

export function useConversationTags({
  token,
  conversationId,
  role,
  activeTags,
  setError,
}: UseConversationTagsParams) {
  const setConversations = useChatStore((state) => state.setConversations)
  const setSelectedConversation = useChatStore((state) => state.setSelectedConversation)
  const setClientHistory = useChatStore((state) => state.setClientHistory)

  const updateTags = async (nextTags: string[], fallbackError: string) => {
    if (!token || !conversationId || role === 'client') return
    try {
      const updated = await setConversationTags(token, conversationId, nextTags)
      setConversations((prev) => prev.map((conversation) => (conversation.id === updated.id ? updated : conversation)))
      setSelectedConversation((current) => (current?.id === updated.id ? updated : current))
      setClientHistory((prev) => prev.map((conversation) => (conversation.id === updated.id ? updated : conversation)))
      const list = await getConversations(token)
      setConversations(list)
    } catch (err) {
      setError(err instanceof Error ? err.message : fallbackError)
    }
  }

  const addTag = async (tag: string) => {
    const normalized = tag.trim()
    if (!normalized) return
    const nextTags = activeTags.includes(normalized) ? activeTags : [...activeTags, normalized]
    await updateTags(nextTags, 'Не удалось добавить тег')
  }

  const removeTag = async (tag: string) => {
    await updateTags(activeTags.filter((currentTag) => currentTag !== tag), 'Не удалось удалить тег')
  }

  const togglePriority = async () => {
    if (activeTags.includes('Срочно')) {
      await removeTag('Срочно')
    } else {
      await addTag('Срочно')
    }
  }

  return { addTag, removeTag, togglePriority }
}
