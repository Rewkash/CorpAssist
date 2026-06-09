import { authFetch } from './client'
import type { ImproveResult, ReplyAssistResult } from './types'

export async function suggestReply(token: string, text: string, conversationId?: number): Promise<ReplyAssistResult> {
  const response = await authFetch('/assist/reply', token, {
    method: 'POST',
    body: JSON.stringify({ text, conversation_id: conversationId })
  })
  return response.json()
}

export async function improveDraft(token: string, text: string, conversationId?: number): Promise<ImproveResult> {
  const response = await authFetch('/assist/improve', token, {
    method: 'POST',
    body: JSON.stringify({ text, conversation_id: conversationId })
  })
  return response.json()
}
