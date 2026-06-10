import { useEffect, useState } from 'react'

import { suggestConversationTags } from '../../../api'

type UseSuggestedTagsParams = {
  token: string | null
  conversationId: number | null
  role: string | null
}

export function useSuggestedTags({ token, conversationId, role }: UseSuggestedTagsParams) {
  const [suggestedTags, setSuggestedTags] = useState<string[]>([])

  useEffect(() => {
    const loadTags = async () => {
      if (!token || !conversationId || role === 'client') {
        setSuggestedTags([])
        return
      }

      try {
        const res = await suggestConversationTags(token, conversationId)
        setSuggestedTags(Array.isArray(res.tags) ? res.tags : [])
      } catch {
        setSuggestedTags([])
      }
    }

    loadTags()
  }, [token, conversationId, role])

  return suggestedTags
}
