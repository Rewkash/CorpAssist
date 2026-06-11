import { useEffect } from 'react'

import { getClients, getConversations, getMessages, getWorkers, markMessagesRead, me } from '../../../api'
import { useChatStore } from '../store/chatStore'

type RefValue<T> = {
  current: T
}

type UseChatBootstrapParams = {
  token: string | null
  role: string | null
  conversationId: number | null
  reconnectPhaseStartedAtRef: RefValue<number | null>
  forceScrollOnNextRenderRef: RefValue<boolean>
  setError: (value: string) => void
  setFirstUnreadId: (value: number | null) => void
}

export function useChatBootstrap({
  token,
  role,
  conversationId,
  reconnectPhaseStartedAtRef,
  forceScrollOnNextRenderRef,
  setError,
  setFirstUnreadId,
}: UseChatBootstrapParams) {
  const setConnectionError = useChatStore((state) => state.setConnectionError)
  const setIsReconnectingNow = useChatStore((state) => state.setIsReconnectingNow)
  const setReconnectIn = useChatStore((state) => state.setReconnectIn)
  const setMyId = useChatStore((state) => state.setMyId)
  const setConversations = useChatStore((state) => state.setConversations)
  const setSelectedConversation = useChatStore((state) => state.setSelectedConversation)
  const setMessages = useChatStore((state) => state.setMessages)
  const setClients = useChatStore((state) => state.setClients)
  const setWorkers = useChatStore((state) => state.setWorkers)
  const setAssignClientId = useChatStore((state) => state.setAssignClientId)
  const setAssignWorkerId = useChatStore((state) => state.setAssignWorkerId)
  useEffect(() => {
    if (!token) return
    let cancelled = false
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let countdownTimer: ReturnType<typeof setInterval> | null = null
    let successTimer: ReturnType<typeof setTimeout> | null = null

    const clearTimers = () => {
      if (retryTimer) clearTimeout(retryTimer)
      if (countdownTimer) clearInterval(countdownTimer)
      if (successTimer) clearTimeout(successTimer)
    }

    const scheduleReconnect = () => {
      if (cancelled) return
      setConnectionError(true)
      setIsReconnectingNow(false)
      let secondsLeft = 5
      setReconnectIn(secondsLeft)
      countdownTimer = setInterval(() => {
        secondsLeft -= 1
        if (secondsLeft <= 0) {
          setReconnectIn(0)
          if (countdownTimer) clearInterval(countdownTimer)
          return
        }
        setReconnectIn(secondsLeft)
      }, 1000)
      retryTimer = setTimeout(() => {
        if (cancelled) return
        reconnectPhaseStartedAtRef.current = Date.now()
        setIsReconnectingNow(true)
        load()
      }, 5000)
    }

    const load = async () => {
      if (cancelled) return
      try {
        const profile = await me(token)
        if (cancelled) return
        const finishSuccess = async () => {
          setConnectionError(false)
          setIsReconnectingNow(false)
          setReconnectIn(null)
          setError('')
          reconnectPhaseStartedAtRef.current = null
          setMyId(profile.id)
          const list = await getConversations(token)
          if (cancelled) return
          setConversations(list)
          const convId = conversationId
          const selected = convId ? list.find((conversation) => conversation.id === convId) : null
          setSelectedConversation(selected || null)

          if (convId) {
            const items = await getMessages(token, convId)
            if (cancelled) return
            const firstUnread = items.find((message) => message.sender_id !== profile.id && !message.read_at)
            setFirstUnreadId(firstUnread?.id ?? null)
            forceScrollOnNextRenderRef.current = true
            setMessages(items)
            await markMessagesRead(token, convId)
            if (cancelled) return
          } else {
            setSelectedConversation(null)
            setMessages([])
            setFirstUnreadId(null)
          }
          if (role === 'admin') {
            const [clientList, workerList] = await Promise.all([getClients(token), getWorkers(token)])
            if (cancelled) return
            setClients(clientList)
            setWorkers(workerList)
            if (clientList.length > 0) setAssignClientId(clientList[0].id)
            if (workerList.length > 0) setAssignWorkerId(workerList[0].id)
          }
        }
        const startedAt = reconnectPhaseStartedAtRef.current
        const elapsed = startedAt ? Date.now() - startedAt : 2000
        const delay = Math.max(0, 2000 - elapsed)
        if (delay > 0) {
          successTimer = setTimeout(() => { if (!cancelled) void finishSuccess() }, delay)
        } else {
          await finishSuccess()
        }
      } catch (err) {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'Не удалось открыть чат'
        setError(message)
        if (message.includes('Не удалось подключиться')) {
          scheduleReconnect()
        }
      }
    }

    load()

    return () => {
      cancelled = true
      clearTimers()
    }
  }, [token, role, conversationId])
}
