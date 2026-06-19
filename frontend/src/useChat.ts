import { useEffect, useRef, useState } from 'react'

import { createChatSocket, createChatUpdatesSocket, type ChatMessage, type Conversation } from './api'

type UseChatParams = {
  token: string | null
  conversationId: number | null
  onMessageCreated: (message: ChatMessage) => void
  onConversationsSnapshot: (items: Conversation[]) => void
  onConnectionStateChange?: (isConnected: boolean) => void
}

/** Generic reconnecting WebSocket helper shared between the two sockets. */
function connectWithReconnect(opts: {
  createSocket: () => WebSocket
  onMessage: (data: unknown) => void
  onOpen?: () => void
  onClose?: () => void
  socketRef: React.MutableRefObject<WebSocket | null>
  timerRef: React.MutableRefObject<number | null>
  attemptRef: React.MutableRefObject<number>
  aliveRef: { value: boolean }
}) {
  const { createSocket, onMessage, onOpen, onClose, socketRef, timerRef, attemptRef, aliveRef } = opts

  const clearTimer = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }

  const connect = () => {
    if (!aliveRef.value) return
    const socket = createSocket()
    socketRef.current = socket

    socket.onopen = () => {
      attemptRef.current = 0
      onOpen?.()
    }

    socket.onmessage = (event) => {
      onMessage(JSON.parse(event.data))
    }

    socket.onclose = () => {
      onClose?.()
      if (!aliveRef.value) return
      const attempt = attemptRef.current + 1
      attemptRef.current = attempt
      const delay = Math.min(1000 * 2 ** (attempt - 1), 15000)
      timerRef.current = window.setTimeout(connect, delay)
    }

    socket.onerror = () => {
      socket.close()
    }
  }

  return { connect, clearTimer }
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
    const cleanupSocket = (
      socketRef: React.MutableRefObject<WebSocket | null>,
      timerRef: React.MutableRefObject<number | null>,
      attemptRef: React.MutableRefObject<number>,
    ) => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current)
        timerRef.current = null
      }
      attemptRef.current = 0
      if (socketRef.current) {
        socketRef.current.close()
        socketRef.current = null
      }
    }

    const setDisconnected = () => {
      setConnected(false)
      onConnectionStateChangeRef.current?.(false)
    }

    if (!token) {
      cleanupSocket(socketRef, reconnectTimerRef, reconnectAttemptRef)
      cleanupSocket(updatesSocketRef, updatesReconnectTimerRef, updatesReconnectAttemptRef)
      setDisconnected()
      return
    }

    let alive = true
    const aliveRef = { value: true }

    // Updates socket (conversations list)
    const updatesConnector = connectWithReconnect({
      createSocket: () => createChatUpdatesSocket(token),
      onMessage: (data: unknown) => {
        const payload = data as { type: string; payload: unknown }
        if (payload.type === 'conversations_snapshot' && Array.isArray(payload.payload)) {
          onConversationsSnapshotRef.current(payload.payload as Conversation[])
        }
      },
      socketRef: updatesSocketRef,
      timerRef: updatesReconnectTimerRef,
      attemptRef: updatesReconnectAttemptRef,
      aliveRef,
    })
    updatesConnector.connect()

    if (!conversationId) {
      cleanupSocket(socketRef, reconnectTimerRef, reconnectAttemptRef)
      setDisconnected()

      return () => {
        alive = false
        aliveRef.value = false
        cleanupSocket(socketRef, reconnectTimerRef, reconnectAttemptRef)
        cleanupSocket(updatesSocketRef, updatesReconnectTimerRef, updatesReconnectAttemptRef)
        setDisconnected()
      }
    }

    // Chat socket (messages)
    const chatConnector = connectWithReconnect({
      createSocket: () => createChatSocket(token, conversationId),
      onMessage: (data: unknown) => {
        const payload = data as { type: string; payload: unknown }
        if (payload.type === 'message_created' && payload.payload) {
          onMessageCreatedRef.current(payload.payload as ChatMessage)
        }
        if (payload.type === 'conversations_snapshot' && Array.isArray(payload.payload)) {
          onConversationsSnapshotRef.current(payload.payload as Conversation[])
        }
      },
      onOpen: () => {
        setConnected(true)
        onConnectionStateChangeRef.current?.(true)
      },
      onClose: () => {
        setDisconnected()
      },
      socketRef,
      timerRef: reconnectTimerRef,
      attemptRef: reconnectAttemptRef,
      aliveRef,
    })
    chatConnector.connect()

    return () => {
      alive = false
      aliveRef.value = false
      cleanupSocket(socketRef, reconnectTimerRef, reconnectAttemptRef)
      cleanupSocket(updatesSocketRef, updatesReconnectTimerRef, updatesReconnectAttemptRef)
      setDisconnected()
    }
  }, [token, conversationId])

  return { connected }
}
