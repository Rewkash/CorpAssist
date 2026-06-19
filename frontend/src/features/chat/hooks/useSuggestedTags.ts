import { useCallback, useEffect, useState } from 'react'

import { regenerateConversationTags, suggestConversationTags } from '../../../api'

type UseSuggestedTagsParams = {
  token: string | null
  conversationId: number | null
  role: string | null
}

export function useSuggestedTags({ token, conversationId, role }: UseSuggestedTagsParams) {
  const [suggestedTags, setSuggestedTags] = useState<string[]>([])
  const [isGeneratingTags, setIsGeneratingTags] = useState(false)

  useEffect(() => {
    let cancelled = false

    const loadTags = async () => {
      if (!token || !conversationId || role === 'client') {
        setSuggestedTags([])
        return
      }

      setIsGeneratingTags(true)
      try {
        const res = await suggestConversationTags(token, conversationId)
        if (!cancelled) {
          setSuggestedTags(Array.isArray(res.tags) ? res.tags : [])
        }
      } catch {
        if (!cancelled) {
          setSuggestedTags([])
        }
      } finally {
        if (!cancelled) {
          setIsGeneratingTags(false)
        }
      }
    }

    loadTags()

    return () => {
      cancelled = true
    }
  }, [token, conversationId, role])

  const regenerateTags = useCallback(async () => {
    if (!token || !conversationId || role === 'client') return

    setIsGeneratingTags(true)
    try {
      const res = await regenerateConversationTags(token, conversationId)
      setSuggestedTags(Array.isArray(res.tags) ? res.tags : [])
    } catch {
      setSuggestedTags([])
    } finally {
      setIsGeneratingTags(false)
    }
  }, [token, conversationId, role])

  return { suggestedTags, isGeneratingTags, regenerateTags }
}
