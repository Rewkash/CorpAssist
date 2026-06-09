import { useCallback, useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import './supportChat.css'

import { assignWorker, closeConversation, getClientConversationHistory, getClients, getConversations, getMessages, getWorkers, improveDraft, markMessagesRead, me, sendMessage, setConversationTags, startConversation, suggestConversationTags, suggestReply, takeConversation } from './api'
import type { ChatMessage, Conversation } from './api'
import { AuthScreen } from './components/AuthScreen'
import { ChatHeader } from './components/ChatHeader'
import { ClosedConversationPanel } from './components/ClosedConversationPanel'
import { ConversationList } from './components/ConversationList'
import { JumpToBottomButton } from './components/JumpToBottomButton'
import { MessageComposer } from './components/MessageComposer'
import { MessageList } from './components/MessageList'
import { RightSidebar } from './components/RightSidebar'
import { formatHistoryDate } from './features/chat/chatFormatters'
import { filterConversations, getActiveClientEmail, getActiveConversation, getVisibleConversationTags, isConversationClosed } from './features/chat/chatSelectors'
import { useChat } from './useChat'
import { useAssistStore } from './store'

function useComposerState() {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [assistBusy, setAssistBusy] = useState(false)
  const [assistHint, setAssistHint] = useState('')
  const [generatingStatus, setGeneratingStatus] = useState('')
  const [replySuggestions, setReplySuggestions] = useState<string[]>([])

  return {
    text,
    setText,
    busy,
    setBusy,
    assistBusy,
    setAssistBusy,
    assistHint,
    setAssistHint,
    generatingStatus,
    setGeneratingStatus,
    replySuggestions,
    setReplySuggestions,
  }
}

function useSidebarUiState() {
  const [search, setSearch] = useState('')
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [mobileMode, setMobileMode] = useState<'list' | 'chat' | 'info'>('chat')
  const [viewportWidth, setViewportWidth] = useState<number>(typeof window !== 'undefined' ? window.innerWidth : 1440)
  const [manualTag, setManualTag] = useState('')
  const [showTagDropdown, setShowTagDropdown] = useState(false)
  const tagDropdownRef = useRef<HTMLDivElement | null>(null)

  return {
    search,
    setSearch,
    rightCollapsed,
    setRightCollapsed,
    mobileMode,
    setMobileMode,
    viewportWidth,
    setViewportWidth,
    manualTag,
    setManualTag,
    showTagDropdown,
    setShowTagDropdown,
    tagDropdownRef,
  }
}

function ChatScreen() {
  const { token, role, email, theme, toggleTheme, logout, conversationId, setConversationId } = useAssistStore()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [error, setError] = useState('')
  const [connectionError, setConnectionError] = useState(false)
  const [reconnectIn, setReconnectIn] = useState<number | null>(null)
  const [isReconnectingNow, setIsReconnectingNow] = useState(false)
  const composer = useComposerState()
  const [myId, setMyId] = useState<number | null>(null)
  const messagesRef = useRef<HTMLDivElement | null>(null)
  const prevConversationRef = useRef<number | null>(null)
  const prevMessagesCountRef = useRef(0)
  const prevIncomingCountRef = useRef(0)
  const openedConversationsRef = useRef<Record<number, boolean>>({})
  const forceScrollOnNextRenderRef = useRef(false)
  const isAtBottomRef = useRef(true)
  const isScrollingToBottomRef = useRef(false)
  const reconnectPhaseStartedAtRef = useRef<number | null>(null)
  const [firstUnreadId, setFirstUnreadId] = useState<number | null>(null)
  const [isUnreadDividerHiding, setIsUnreadDividerHiding] = useState(false)
  const unreadDividerHideTimerRef = useRef<number | null>(null)
  const [newMessagesCount, setNewMessagesCount] = useState(0)
  const [showJumpDown, setShowJumpDown] = useState(false)
  const [jumpBottomOffset, setJumpBottomOffset] = useState(138)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null)
  const [clientHistory, setClientHistory] = useState<Conversation[]>([])
  const [clients, setClients] = useState<{ id: number; email: string; assigned_worker_id: number | null }[]>([])
  const [workers, setWorkers] = useState<{ id: number; email: string }[]>([])
  const [assignClientId, setAssignClientId] = useState<number | null>(null)
  const [assignWorkerId, setAssignWorkerId] = useState<number | null>(null)
  const sidebarUi = useSidebarUiState()
  const [suggestedTags, setSuggestedTags] = useState<string[]>([])
  const bottomPanelRef = useRef<HTMLDivElement | null>(null)
  const frequentTags = ['Миграция', 'Срочно', 'VIP', 'Ожидание', 'Технический', 'Оплата']

  const {
    text,
    setText,
    busy,
    setBusy,
    assistBusy,
    setAssistBusy,
    assistHint,
    setAssistHint,
    generatingStatus,
    setGeneratingStatus,
    replySuggestions,
    setReplySuggestions,
  } = composer

  const {
    search,
    setSearch,
    rightCollapsed,
    setRightCollapsed,
    mobileMode,
    viewportWidth,
    setViewportWidth,
    manualTag,
    setManualTag,
    showTagDropdown,
    setShowTagDropdown,
    tagDropdownRef,
  } = sidebarUi

  const scrollToUnreadAnchor = (behavior: ScrollBehavior = 'auto') => {
    const el = messagesRef.current
    if (!el) return false
    const anchor = el.querySelector('#unread-anchor') as HTMLElement | null
    if (!anchor) return false
    const targetTop = Math.max(0, anchor.offsetTop - el.clientHeight / 2 + anchor.clientHeight / 2)
    el.scrollTo({ top: targetTop, behavior })
    return true
  }

  const clearUnreadDividerSmooth = () => {
    if (firstUnreadId === null) return
    if (unreadDividerHideTimerRef.current !== null) {
      window.clearTimeout(unreadDividerHideTimerRef.current)
      unreadDividerHideTimerRef.current = null
    }
    setIsUnreadDividerHiding(true)
    unreadDividerHideTimerRef.current = window.setTimeout(() => {
      setFirstUnreadId(null)
      setIsUnreadDividerHiding(false)
      unreadDividerHideTimerRef.current = null
    }, 220)
  }

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    if (viewportWidth < 1100) {
      setRightCollapsed(true)
    } else {
      setRightCollapsed(false)
    }
  }, [viewportWidth])

  useEffect(() => {
    return () => {
      if (unreadDividerHideTimerRef.current !== null) {
        window.clearTimeout(unreadDividerHideTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let countdownTimer: ReturnType<typeof setInterval> | null = null

    const clearTimers = () => {
      if (retryTimer) clearTimeout(retryTimer)
      if (countdownTimer) clearInterval(countdownTimer)
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
        setConversations(list)
        let convId = conversationId
        const selected = convId ? list.find((c) => c.id === convId) : null
        setSelectedConversation(selected || null)

        if (convId) {
          const items = await getMessages(token, convId)
          const firstUnread = items.find((m) => m.sender_id !== profile.id && !m.read_at)
          setFirstUnreadId(firstUnread?.id ?? null)
          forceScrollOnNextRenderRef.current = true
          setMessages(items)
          await markMessagesRead(token, convId)
        } else {
          setSelectedConversation(null)
          setMessages([])
          setFirstUnreadId(null)
        }
        if (role === 'admin') {
            const [clientList, workerList] = await Promise.all([getClients(token), getWorkers(token)])
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
          setTimeout(() => { if (!cancelled) void finishSuccess() }, delay)
        } else {
          await finishSuccess()
        }
      } catch (err) {
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
  }, [token, role, conversationId, setConversationId])

  useEffect(() => {
    if (!token || !conversationId || !selectedConversation) {
      setClientHistory([])
      return
    }
    let cancelled = false
    const loadClientHistory = async () => {
      try {
        const history = await getClientConversationHistory(token, conversationId)
        if (!cancelled) {
          setClientHistory(history.length > 0 ? history : [selectedConversation])
          setSelectedConversation((current) => history.find((c) => c.id === conversationId) || current)
        }
      } catch (err) {
        if (!cancelled) {
          const fallbackHistory = conversations.filter((c) => c.client_id === selectedConversation.client_id)
          setClientHistory(fallbackHistory.length > 0 ? fallbackHistory : [selectedConversation])
          setError(err instanceof Error ? err.message : 'Не удалось загрузить историю клиента')
        }
      }
    }
    loadClientHistory()
    return () => {
      cancelled = true
    }
  }, [token, conversationId, selectedConversation?.id, selectedConversation?.client_id])

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

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!tagDropdownRef.current) return
      if (!tagDropdownRef.current.contains(event.target as Node)) {
        setShowTagDropdown(false)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [])

  useEffect(() => {
    const panel = bottomPanelRef.current
    if (!panel) return
    const updateOffset = () => {
      const panelHeight = panel.offsetHeight
      setJumpBottomOffset(panelHeight + 12)
    }
    updateOffset()
    const observer = new ResizeObserver(updateOffset)
    observer.observe(panel)
    window.addEventListener('resize', updateOffset)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', updateOffset)
    }
  }, [conversationId, text, assistHint, connectionError, error])

  useEffect(() => {
    const el = messagesRef.current
    if (!el) return
    const conversationChanged = prevConversationRef.current !== conversationId
    const firstOpenOfConversation = conversationId ? !openedConversationsRef.current[conversationId] : false

    if (conversationChanged || firstOpenOfConversation || forceScrollOnNextRenderRef.current) {
      const scrollToBottomHard = () => {
        el.scrollTop = el.scrollHeight
        requestAnimationFrame(() => {
          el.scrollTop = el.scrollHeight
        })
        setTimeout(() => {
          el.scrollTop = el.scrollHeight
        }, 0)
        isAtBottomRef.current = true
      }
      if (firstUnreadId) {
        if (scrollToUnreadAnchor('auto')) {
          isAtBottomRef.current = false
          setShowJumpDown(true)
        } else {
          scrollToBottomHard()
        }
      } else {
        scrollToBottomHard()
      }
      if (conversationId) openedConversationsRef.current[conversationId] = true
      forceScrollOnNextRenderRef.current = false
      setNewMessagesCount(0)
      if (!firstUnreadId) {
        setShowJumpDown(false)
      }
      prevMessagesCountRef.current = messages.length
      prevIncomingCountRef.current = messages.filter((m) => myId === null || m.sender_id !== myId).length
    } else {
      const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
      const incomingCount = messages.filter((m) => myId === null || m.sender_id !== myId).length
      if (isAtBottom) {
        setNewMessagesCount(0)
        setShowJumpDown(false)
        prevIncomingCountRef.current = incomingCount
        if (messages.length > prevMessagesCountRef.current) {
          el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
        }
      } else if (messages.length > prevMessagesCountRef.current) {
        const incomingDelta = Math.max(0, incomingCount - prevIncomingCountRef.current)
        if (incomingDelta > 0) {
          setNewMessagesCount((v) => v + incomingDelta)
        }
        setShowJumpDown(true)
      }
      prevMessagesCountRef.current = messages.length
      prevIncomingCountRef.current = incomingCount
    }
    prevConversationRef.current = conversationId
  }, [messages, conversationId, firstUnreadId])

  const handleMessagesScroll = () => {
    const el = messagesRef.current
    if (!el) return
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
    if (isAtBottom) {
      setNewMessagesCount(0)
      setShowJumpDown(false)
      isAtBottomRef.current = true
      isScrollingToBottomRef.current = false
      if (token && conversationId) {
        markMessagesRead(token, conversationId).catch(() => {})
      }
    } else {
      if (!isScrollingToBottomRef.current) {
        setShowJumpDown(true)
      }
      isAtBottomRef.current = false
    }
  }

  const jumpToBottom = () => {
    const el = messagesRef.current
    if (!el) return
    if (firstUnreadId) {
      const anchor = el.querySelector('#unread-anchor') as HTMLElement | null
      if (anchor) {
        const targetTop = Math.max(0, anchor.offsetTop - el.clientHeight / 2 + anchor.clientHeight / 2)
        const alreadyAtUnread = Math.abs(el.scrollTop - targetTop) < 40
        if (!alreadyAtUnread) {
          isScrollingToBottomRef.current = true
          el.scrollTo({ top: targetTop, behavior: 'smooth' })
          return
        }
      }
      if (scrollToUnreadAnchor('smooth')) {
        isScrollingToBottomRef.current = true
      }
    }
    isScrollingToBottomRef.current = true
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    setNewMessagesCount(0)
    setShowJumpDown(false)
    isAtBottomRef.current = true
    prevIncomingCountRef.current = messages.filter((m) => myId === null || m.sender_id !== myId).length
    if (token && conversationId) {
      markMessagesRead(token, conversationId).catch(() => {})
    }
  }

  const onSend = async () => {
    if (!token || text.trim().length < 1) return
    if (isActiveConversationClosed) {
      setError('')
      setAssistHint('Этот диалог закрыт. Начните новый диалог, чтобы написать сообщение.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const outgoingText = text.trim()
      let targetConversationId = conversationId
      if (!targetConversationId && role === 'client') {
        const conv = await startConversation(token)
        targetConversationId = conv.id
        setConversationId(conv.id)
        setSelectedConversation(conv)
        const list = await getConversations(token)
        setConversations(list)
      }
      if (!targetConversationId) {
        setError('Сначала выберите диалог из списка или создайте новый.')
        return
      }

      const item = await sendMessage(token, targetConversationId, outgoingText)
      setMessages((prev) => [...prev, item])
      clearUnreadDividerSmooth()
      setText('')
      setReplySuggestions([])
      const items = await getMessages(token, targetConversationId)
      forceScrollOnNextRenderRef.current = true
      setMessages(items)
      if (isAtBottomRef.current) {
        await markMessagesRead(token, targetConversationId)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Не удалось отправить сообщение'
      if (message.includes('Диалог закрыт')) {
        setError('')
        setAssistHint('Этот диалог уже закрыт. Нажмите + Новый диалог, чтобы продолжить.')
      } else {
        setError(message)
      }
    } finally {
      setBusy(false)
    }
  }

  const onSuggest = async () => {
    if (!token) return
    const fallbackIncoming = [...messages].reverse().find((m) => myId !== null && m.sender_id !== myId)?.text || ''
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

  const onImprove = async () => {
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

  const onTakeConversation = async (id: number) => {
    if (!token) return
    try {
      if (role !== 'client') {
        const taken = await takeConversation(token, id)
        setSelectedConversation(taken)
      }
      setConversationId(id)
      const [list, items, history] = await Promise.all([getConversations(token), getMessages(token, id), getClientConversationHistory(token, id)])
      setConversations(list)
      setSelectedConversation((current) => list.find((c) => c.id === id) || current || null)
      setClientHistory(history.length > 0 ? history : list.filter((c) => c.id === id))
      const firstUnread = items.find((m) => m.sender_id !== myId && !m.read_at)
      setFirstUnreadId(firstUnread?.id ?? null)
      forceScrollOnNextRenderRef.current = true
      setMessages(items)
      await markMessagesRead(token, id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось взять диалог')
    }
  }

  const onAssignWorker = async () => {
    if (!token || !assignClientId || !assignWorkerId) return
    try {
      await assignWorker(token, assignClientId, assignWorkerId)
      const clientList = await getClients(token)
      setClients(clientList)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось назначить сотрудника')
    }
  }

  const activeConversation = getActiveConversation(conversationId, conversations, clientHistory, selectedConversation)
  const activeClientEmail = getActiveClientEmail(activeConversation, clients, role, email)
  const isActiveConversationClosed = isConversationClosed(activeConversation)
  const filteredConversations = filterConversations(conversations, search)

  const closeTicket = async () => {
    if (!token || !conversationId) return
    if (role !== 'worker' && role !== 'admin') {
      setError('Только сотрудник или администратор может закрыть тикет')
      return
    }
    try {
      await closeConversation(token, conversationId)
      await sendMessage(token, conversationId, 'Тикет закрыт. Спасибо за обращение! Если понадобится помощь, напишите снова.')
      const [list, items] = await Promise.all([getConversations(token), getMessages(token, conversationId)])
      setConversations(list)
      setMessages(items)
      setConversationId(null)
      setSelectedConversation(null)
      setClientHistory([])
      setAssistHint('Тикет закрыт и скрыт из списка открытых диалогов.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось закрыть тикет')
    }
  }

  const transferTicket = async () => {
    if (!token || !conversationId) return
    await sendMessage(token, conversationId, 'Тикет передан в профильную линию. Коллега подключится в течение 10 минут.')
    const items = await getMessages(token, conversationId)
    setMessages(items)
  }

  const createClientConversation = async () => {
    if (role !== 'client') return
    setConversationId(null)
    setSelectedConversation(null)
    setClientHistory([])
    setMessages([])
    setFirstUnreadId(null)
    setText('')
    setReplySuggestions([])
    setError('')
    setAssistHint('Новый диалог будет создан после первого сообщения.')
  }

  const activeTags = getVisibleConversationTags(activeConversation, role)
  const addTag = async (tag: string) => {
    if (!token || !conversationId || role === 'client') return
    const normalized = tag.trim()
    if (!normalized) return
    const nextTags = activeTags.includes(normalized) ? activeTags : [...activeTags, normalized]
    try {
      const updated = await setConversationTags(token, conversationId, nextTags)
      setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
      setSelectedConversation((current) => (current?.id === updated.id ? updated : current))
      setClientHistory((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
      const list = await getConversations(token)
      setConversations(list)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось добавить тег')
    }
  }

  const removeTag = async (tag: string) => {
    if (!token || !conversationId || role === 'client') return
    try {
      const updated = await setConversationTags(token, conversationId, activeTags.filter((t) => t !== tag))
      setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
      setSelectedConversation((current) => (current?.id === updated.id ? updated : current))
      setClientHistory((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
      const list = await getConversations(token)
      setConversations(list)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось удалить тег')
    }
  }

  const togglePriority = async () => {
    if (!token || !conversationId || role === 'client') return
    const hasPriority = activeTags.includes('Срочно')
    if (hasPriority) {
      await removeTag('Срочно')
    } else {
      await addTag('Срочно')
    }
  }

  const handleSocketMessageCreated = useCallback((message: ChatMessage) => {
    if (!conversationId || message.conversation_id !== conversationId) return
    setMessages((prev) => {
      if (prev.some((item) => item.id === message.id)) return prev
      return [...prev, message]
    })
    if (myId !== null && message.sender_id !== myId && !message.read_at && firstUnreadId === null && !isAtBottomRef.current) {
      setFirstUnreadId(message.id)
    }
    if (token && isAtBottomRef.current) {
      markMessagesRead(token, conversationId).catch(() => {})
    }
  }, [conversationId, token, myId, firstUnreadId])

  const handleSocketConversationsSnapshot = useCallback((items: Conversation[]) => {
    setConversations(items)
    setSelectedConversation((current) => {
      if (!current) return null
      return items.find((c) => c.id === current.id) || current
    })
  }, [])

  const handleSocketConnectionState = useCallback((isConnected: boolean) => {
    setConnectionError(!isConnected)
    setIsReconnectingNow(!isConnected)
    if (isConnected) {
      setReconnectIn(null)
      reconnectPhaseStartedAtRef.current = null
    }
  }, [])

  useChat({
    token,
    conversationId,
    onMessageCreated: handleSocketMessageCreated,
    onConversationsSnapshot: handleSocketConversationsSnapshot,
    onConnectionStateChange: handleSocketConnectionState,
  })

  return (
    <div className="supportRoot">
      <div
        className={clsx('appShell', rightCollapsed && 'rightCollapsed')}
      >
        <ConversationList
          email={email}
          role={role}
          search={search}
          conversations={filteredConversations}
          conversationId={conversationId}
          onSearchChange={setSearch}
          onTakeConversation={onTakeConversation}
          onLogout={logout}
        />

        <main className="center" style={{ display: mobileMode === 'chat' ? 'flex' : undefined }}>
          <ChatHeader
            activeConversation={activeConversation}
            role={role}
            conversationId={conversationId}
            rightCollapsed={rightCollapsed}
            onCreateClientConversation={createClientConversation}
            onCloseTicket={closeTicket}
            onTransferTicket={transferTicket}
            onToggleRightCollapsed={() => setRightCollapsed((v) => !v)}
          />
          <MessageList
            conversationId={conversationId}
            messages={messages}
            myId={myId}
            firstUnreadId={firstUnreadId}
            isUnreadDividerHiding={isUnreadDividerHiding}
            messagesRef={messagesRef}
            onScroll={handleMessagesScroll}
          />
          {showJumpDown && (
            <JumpToBottomButton bottomOffset={jumpBottomOffset} newMessagesCount={newMessagesCount} onClick={jumpToBottom} />
          )}
          {isActiveConversationClosed ? (
            <ClosedConversationPanel closedAt={activeConversation?.closed_at} bottomPanelRef={bottomPanelRef} />
          ) : (
            <MessageComposer
              text={text}
              busy={busy}
              role={role}
              conversationId={conversationId}
              assistBusy={assistBusy}
              generatingStatus={generatingStatus}
              replySuggestions={replySuggestions}
              connectionError={connectionError}
              isReconnectingNow={isReconnectingNow}
              reconnectIn={reconnectIn}
              error={error}
              assistHint={assistHint}
              bottomPanelRef={bottomPanelRef}
              onSuggest={onSuggest}
              onImprove={onImprove}
              onSend={onSend}
              onTextChange={(e) => setText(e.target.value)}
              onTextKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  onSend()
                }
              }}
              onHideSuggestions={() => setReplySuggestions([])}
              onSelectSuggestion={(suggestion) => {
                setText(suggestion)
                setReplySuggestions([])
                setAssistHint('Вариант подставлен в поле ввода.')
              }}
            />
          )}
        </main>

        <RightSidebar
          mobileMode={mobileMode}
          activeConversation={activeConversation}
          activeClientEmail={activeClientEmail}
          clientHistory={clientHistory}
          conversationId={conversationId}
          role={role}
          activeTags={activeTags}
          suggestedTags={suggestedTags}
          frequentTags={frequentTags}
          manualTag={manualTag}
          showTagDropdown={showTagDropdown}
          tagDropdownRef={tagDropdownRef}
          assignClientId={assignClientId}
          assignWorkerId={assignWorkerId}
          clients={clients}
          workers={workers}
          onTakeConversation={onTakeConversation}
          onTogglePriority={() => void togglePriority()}
          onAddTag={(tag) => void addTag(tag)}
          onRemoveTag={(tag) => void removeTag(tag)}
          onManualTagChange={setManualTag}
          onShowTagDropdown={() => setShowTagDropdown(true)}
          onHideTagDropdown={() => setShowTagDropdown(false)}
          onAssignClientId={setAssignClientId}
          onAssignWorkerId={setAssignWorkerId}
          onAssignWorker={onAssignWorker}
          formatHistoryDate={formatHistoryDate}
        />
      </div>
    </div>
  )
}

export function App() {
  const token = useAssistStore((s) => s.token)
  return token ? <ChatScreen /> : <AuthScreen />
}
