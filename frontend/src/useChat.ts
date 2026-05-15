import { useEffect, useRef, useState } from 'react'

import { createChatSocket, createChatUpdatesSocket, type ChatMessage, type Conversation } from './api'

type UseChatParams = {
  token: string | null
  conversationId: number | null
  onMessageCreated: (message: ChatMessage) => void
  onConversationsSnapshot: (items: Conversation[]) => void
  onConnectionStateChange?: (isConnected: boolean) => void
}

export function useChat({ token, conversationId, onMessageCreated, onConversationsSnapshot, onConnectionStateChange }: UseChatParams) {
  const socketRef = useRef<WebSocket | null>(null)
  const updatesSocketRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const updatesReconnectTimerRef = useRef<number | null>(null)
  const reconnectAttemptRef = useRef(0)
  const updatesReconnectAttemptRef = useRef(0)
  const [connected, setConnected] = useState(false)
  const onMessageCreatedRef = useRef(onMessageCreated)
  const onConversationsSnapshotRef = useRef(onConversationsSnapshot)
  const onConnectionStateChangeRef = useRef(onConnectionStateChange)

  useEffect(() => {
    onMessageCreatedRef.current = onMessageCreated
  }, [onMessageCreated])

  useEffect(() => {
    onConversationsSnapshotRef.current = onConversationsSnapshot
  }, [onConversationsSnapshot])

  useEffect(() => {
    onConnectionStateChangeRef.current = onConnectionStateChange
  }, [onConnectionStateChange])

  useEffect(() => {
    const clearReconnect = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
    }

    const clearUpdatesReconnect = () => {
      if (updatesReconnectTimerRef.current !== null) {
        window.clearTimeout(updatesReconnectTimerRef.current)
        updatesReconnectTimerRef.current = null
      }
    }

    const connectUpdates = (aliveRef: { value: boolean }, authToken: string) => {
      if (!aliveRef.value) return
      const socket = createChatUpdatesSocket(authToken)
      updatesSocketRef.current = socket

      socket.onopen = () => {
        updatesReconnectAttemptRef.current = 0
      }

      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data)
        if (payload.type === 'conversations_snapshot' && Array.isArray(payload.payload)) {
          onConversationsSnapshotRef.current(payload.payload as Conversation[])
        }
      }

      socket.onclose = () => {
        if (!aliveRef.value) return
        const attempt = updatesReconnectAttemptRef.current + 1
        updatesReconnectAttemptRef.current = attempt
        const delay = Math.min(1000 * 2 ** (attempt - 1), 15000)
        updatesReconnectTimerRef.current = window.setTimeout(() => connectUpdates(aliveRef, authToken), delay)
      }

      socket.onerror = () => {
        socket.close()
      }
    }

    if (!token) {
      clearReconnect()
      clearUpdatesReconnect()
      reconnectAttemptRef.current = 0
      updatesReconnectAttemptRef.current = 0
      if (socketRef.current) {
        socketRef.current.close()
        socketRef.current = null
      }
      if (updatesSocketRef.current) {
        updatesSocketRef.current.close()
        updatesSocketRef.current = null
      }
      setConnected(false)
       onConnectionStateChangeRef.current?.(false)
      return
    }

    let alive = true
    const aliveRef = { value: true }
    connectUpdates(aliveRef, token)

    if (!conversationId) {
      clearReconnect()
      reconnectAttemptRef.current = 0
      if (socketRef.current) {
        socketRef.current.close()
        socketRef.current = null
      }
      setConnected(false)
      onConnectionStateChangeRef.current?.(false)
      return () => {
        alive = false
        aliveRef.value = false
        clearReconnect()
        clearUpdatesReconnect()
        reconnectAttemptRef.current = 0
        updatesReconnectAttemptRef.current = 0
        if (socketRef.current) {
          socketRef.current.close()
          socketRef.current = null
        }
        if (updatesSocketRef.current) {
          updatesSocketRef.current.close()
          updatesSocketRef.current = null
        }
        setConnected(false)
        onConnectionStateChangeRef.current?.(false)
      }
    }

    const connect = () => {
      if (!alive) return
      const socket = createChatSocket(token, conversationId)
      socketRef.current = socket

      socket.onopen = () => {
        reconnectAttemptRef.current = 0
        setConnected(true)
        onConnectionStateChangeRef.current?.(true)
      }

      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data)
        if (payload.type === 'message_created' && payload.payload) {
          onMessageCreatedRef.current(payload.payload as ChatMessage)
        }
        if (payload.type === 'conversations_snapshot' && Array.isArray(payload.payload)) {
          onConversationsSnapshotRef.current(payload.payload as Conversation[])
        }
      }

      socket.onclose = () => {
        setConnected(false)
        onConnectionStateChangeRef.current?.(false)
        if (!alive) return
        const attempt = reconnectAttemptRef.current + 1
        reconnectAttemptRef.current = attempt
        const delay = Math.min(1000 * 2 ** (attempt - 1), 15000)
        reconnectTimerRef.current = window.setTimeout(connect, delay)
      }

      socket.onerror = () => {
        socket.close()
      }
    }

    connect()

    return () => {
      alive = false
      aliveRef.value = false
      clearReconnect()
      clearUpdatesReconnect()
      reconnectAttemptRef.current = 0
      updatesReconnectAttemptRef.current = 0
      if (socketRef.current) {
        socketRef.current.close()
        socketRef.current = null
      }
      if (updatesSocketRef.current) {
        updatesSocketRef.current.close()
        updatesSocketRef.current = null
      }
      setConnected(false)
      onConnectionStateChangeRef.current?.(false)
    }
  }, [token, conversationId])

  return { connected }
}
