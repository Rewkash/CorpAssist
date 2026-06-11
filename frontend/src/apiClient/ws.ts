import { WS_BASE, WS_CHAT_BASE } from './client'

export function createAssistSocket(token: string, onMessage: (payload: any) => void): WebSocket {
  const socket = new WebSocket(`${WS_BASE}?token=${encodeURIComponent(token)}`)
  socket.onmessage = (event) => onMessage(JSON.parse(event.data))
  return socket
}

export function createChatSocket(token: string, conversationId: number): WebSocket {
  return new WebSocket(`${WS_CHAT_BASE}/ws/chat/${conversationId}?token=${encodeURIComponent(token)}`)
}

export function createChatUpdatesSocket(token: string): WebSocket {
  return new WebSocket(`${WS_CHAT_BASE}/ws/chat-updates?token=${encodeURIComponent(token)}`)
}
