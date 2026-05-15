import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import './supportChat.css'

import { assignWorker, closeConversation, getClientConversationHistory, getClients, getConversations, getMessages, getWorkers, improveDraft, login, markMessagesRead, me, register, sendMessage, setConversationTags, startConversation, suggestConversationTags, suggestReply, takeConversation } from './api'
import type { Conversation } from './api'
import { useChat } from './useChat'
import { useAssistStore } from './store'

type AuthMode = 'login' | 'register'

function AuthScreen() {
  const { setAuth, theme, toggleTheme } = useAssistStore()
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [registerRole, setRegisterRole] = useState<'client' | 'worker'>('client')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const token = mode === 'login' ? await login({ email, password }) : await register({ email, password, role: registerRole })
      const profile = await me(token)
      setAuth(token, profile.email, profile.role)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось выполнить вход')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_0%_0%,#dde9ff_0%,#f6f8fc_40%,#eef2f8_100%)] p-4 dark:bg-[radial-gradient(circle_at_0%_0%,#1a2437_0%,#0b1220_45%,#0a101b_100%)]">
      <div className="w-full max-w-md rounded-3xl border border-white/50 bg-white/80 p-6 shadow-2xl backdrop-blur-xl dark:border-slate-700/80 dark:bg-slate-900/75">
        <div className="mb-5 flex items-start justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">CorpAssist</p>
            <h1 className="text-2xl font-semibold">Чат с поддержкой</h1>
          </div>
          <button onClick={toggleTheme} className="rounded-lg border border-slate-300 px-3 py-2 text-xs dark:border-slate-700">
            {theme === 'light' ? 'Dark' : 'Light'}
          </button>
        </div>

        <div className="mb-4 grid grid-cols-2 rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
          <button onClick={() => setMode('login')} className={clsx('rounded-lg py-2 text-sm', mode === 'login' && 'bg-white shadow dark:bg-slate-700')}>
            Вход
          </button>
          <button onClick={() => setMode('register')} className={clsx('rounded-lg py-2 text-sm', mode === 'register' && 'bg-white shadow dark:bg-slate-700')}>
            Регистрация
          </button>
        </div>

        <form onSubmit={onSubmit} className="space-y-3">
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" type="email" required className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-cyan-500 dark:border-slate-700 dark:bg-slate-950" />
          <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Пароль" type="password" minLength={8} required className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-cyan-500 dark:border-slate-700 dark:bg-slate-950" />
          {mode === 'register' && (
            <select value={registerRole} onChange={(e) => setRegisterRole(e.target.value as 'client' | 'worker')} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-cyan-500 dark:border-slate-700 dark:bg-slate-950">
              <option value="client">Я клиент</option>
              <option value="worker">Я сотрудник</option>
            </select>
          )}
          {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/30 dark:text-rose-300">{error}</div>}
          <button disabled={loading} className="w-full rounded-xl bg-slate-900 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:opacity-60 dark:bg-cyan-600 dark:hover:bg-cyan-500">
            {loading ? 'Проверяем...' : mode === 'login' ? 'Войти' : 'Создать аккаунт'}
          </button>
        </form>
      </div>
    </div>
  )
}

function ChatScreen() {
  const { token, role, email, theme, toggleTheme, logout, conversationId, setConversationId } = useAssistStore()
  const [messages, setMessages] = useState<{ id: number; sender_id: number; text: string; created_at?: string }[]>([])
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [connectionError, setConnectionError] = useState(false)
  const [reconnectIn, setReconnectIn] = useState<number | null>(null)
  const [isReconnectingNow, setIsReconnectingNow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [assistBusy, setAssistBusy] = useState(false)
  const [assistHint, setAssistHint] = useState('')
  const [myId, setMyId] = useState<number | null>(null)
  const messagesRef = useRef<HTMLDivElement | null>(null)
  const prevConversationRef = useRef<number | null>(null)
  const prevMessagesCountRef = useRef(0)
  const prevIncomingCountRef = useRef(0)
  const openedConversationsRef = useRef<Record<number, boolean>>({})
  const forceScrollOnNextRenderRef = useRef(false)
  const isAtBottomRef = useRef(true)
  const reconnectPhaseStartedAtRef = useRef<number | null>(null)
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
  const [search, setSearch] = useState('')
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [mobileMode, setMobileMode] = useState<'list' | 'chat' | 'info'>('chat')
  const [viewportWidth, setViewportWidth] = useState<number>(typeof window !== 'undefined' ? window.innerWidth : 1440)
  const [suggestedTags, setSuggestedTags] = useState<string[]>([])
  const [manualTag, setManualTag] = useState('')
  const [showTagDropdown, setShowTagDropdown] = useState(false)
  const tagDropdownRef = useRef<HTMLDivElement | null>(null)
  const bottomPanelRef = useRef<HTMLDivElement | null>(null)
  const frequentTags = ['Миграция', 'Срочно', 'VIP', 'Ожидание', 'Технический', 'Оплата']

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
          forceScrollOnNextRenderRef.current = true
          setMessages(items)
          await markMessagesRead(token, convId)
        } else {
          setSelectedConversation(null)
          setMessages([])
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
        setSuggestedTags(res.tags)
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
      scrollToBottomHard()
      if (conversationId) openedConversationsRef.current[conversationId] = true
      forceScrollOnNextRenderRef.current = false
      setNewMessagesCount(0)
      setShowJumpDown(false)
      prevMessagesCountRef.current = messages.length
      prevIncomingCountRef.current = messages.filter((m) => myId === null || m.sender_id !== myId).length
    } else {
      const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
      const incomingCount = messages.filter((m) => myId === null || m.sender_id !== myId).length
      if (isAtBottom) {
        setNewMessagesCount(0)
        setShowJumpDown(false)
        prevIncomingCountRef.current = incomingCount
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
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
  }, [messages, conversationId])

  const handleMessagesScroll = () => {
    const el = messagesRef.current
    if (!el) return
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
    if (isAtBottom) {
      setNewMessagesCount(0)
      setShowJumpDown(false)
      isAtBottomRef.current = true
    } else {
      setShowJumpDown(true)
      isAtBottomRef.current = false
    }
  }

  const jumpToBottom = () => {
    const el = messagesRef.current
    if (!el) return
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
      setText('')
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
    setError('')
    try {
      const result = await suggestReply(token, sourceText, conversationId ?? undefined)
      if (result.suggestions.length > 0) setText(result.suggestions[0])
      setAssistHint('Готово: подставили вариант ответа в поле ввода.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось подсказать ответ')
    } finally {
      setAssistBusy(false)
    }
  }

  const onImprove = async () => {
    if (!token || text.trim().length < 3) return
    setAssistBusy(true)
    setError('')
    try {
      const result = await improveDraft(token, text.trim())
      setText(result.improved_text)
      setAssistHint('Готово: текст стал более деловым и понятным.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось улучшить текст')
    } finally {
      setAssistBusy(false)
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
      forceScrollOnNextRenderRef.current = true
      setMessages(items)
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

  const activeConversation = conversationId ? (conversations.find((c) => c.id === conversationId) || clientHistory.find((c) => c.id === conversationId) || selectedConversation) : null
  const activeClientEmail = activeConversation?.client_email || clients.find((c) => c.id === activeConversation?.client_id)?.email || (role === 'client' && activeConversation ? email : activeConversation ? `Клиент #${activeConversation.client_id}` : '—')
  const isActiveConversationClosed = activeConversation?.status === 'closed'
  const filteredConversations = conversations.filter((c) => `${c.id} ${c.title}`.toLowerCase().includes(search.toLowerCase()))
  const formatHistoryDate = (iso: string) => {
    const dt = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - dt.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    if (diffDays >= 0 && diffDays < 7) {
      if (diffDays === 0) return 'сегодня'
      if (diffDays === 1) return '1 день назад'
      if (diffDays < 5) return `${diffDays} дня назад`
      return `${diffDays} дней назад`
    }
    return dt.toLocaleDateString('ru-RU')
  }

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
    setText('')
    setError('')
    setAssistHint('Новый диалог будет создан после первого сообщения.')
  }

  const hiddenClientTags = new Set(['срочно', 'приоритет'])
  const activeTags = (activeConversation?.tags || []).filter((tag) => role !== 'client' || !hiddenClientTags.has(tag.trim().toLowerCase()))
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

  const handleSocketMessageCreated = useCallback((message: { id: number; conversation_id: number; sender_id: number; text: string; created_at?: string }) => {
    if (!conversationId || message.conversation_id !== conversationId) return
    setMessages((prev) => {
      if (prev.some((item) => item.id === message.id)) return prev
      return [...prev, message]
    })
    if (token && isAtBottomRef.current) {
      markMessagesRead(token, conversationId).catch(() => {})
    }
  }, [conversationId, token])

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
        <aside className="panel left">
          <div className="leftHeader">
            <div className="userChip">
              <div className="avatar">{email.slice(0, 2).toUpperCase()}</div>
              <div className="nameWrap">
                <div className="name">{email}</div>
                <div className="sub">{role === 'admin' ? 'Администратор' : role === 'worker' ? 'Сотрудник' : 'Клиент'}</div>
              </div>
            </div>
            <button onClick={logout} className="btn">Выйти</button>
          </div>
          <div className="searchWrap">
            <input className="searchInput" placeholder="Поиск по диалогам..." value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="dialogList">
            {filteredConversations.map((c) => (
              <button key={c.id} onClick={() => onTakeConversation(c.id)} className={clsx('dialogCard', conversationId === c.id && 'active')}>
                <div className="row">
                  <span className="ticket">
                    {role !== 'client' && c.priority_at && <span className="priorityDot" aria-hidden="true">●</span>}
                    Диалог #{c.id}
                  </span>
                  <span className="time">{c.status === 'closed' ? 'Закрыт' : c.worker_id ? 'В работе' : 'Новый'}</span>
                </div>
                <div className="preview">{c.title}</div>
                <div className="row" style={{ marginTop: 8 }}>
                  <span className={clsx('badge', c.status === 'closed' ? 'closed' : c.worker_id ? 'open' : 'pending')}>
                    {c.status === 'closed' ? 'Закрыт' : c.worker_id ? 'Назначен' : 'Свободен'}
                  </span>
                  {role !== 'client' && c.priority_at && <span className="badge urgent">Срочно</span>}
                  {c.unread_count > 0 && <span className="unreadBadge">{c.unread_count}</span>}
                </div>
              </button>
            ))}
          </div>
        </aside>

        <main className="center" style={{ display: mobileMode === 'chat' ? 'flex' : undefined }}>
          <div className="centerHeader">
            <div className="headerLeft">
              <div className="clientName">{activeConversation ? `Диалог #${activeConversation.id}` : 'Диалог не выбран'}</div>
              <div className="sub">{activeConversation ? activeConversation.title : '—'}</div>
            </div>
            <div className="headerActions">
              {role === 'client' && (
                <button className="btn ghostAccent headerActionBtn" onClick={createClientConversation} title="Новый диалог" aria-label="Новый диалог">
                  <span className="actionIcon" aria-hidden="true">＋</span>
                  <span className="actionLabel">Новый диалог</span>
                </button>
              )}
              <button className="btn headerActionBtn" onClick={closeTicket} disabled={!conversationId || role === 'client'} title="Закрыть тикет" aria-label="Закрыть тикет">
                <span className="actionIcon" aria-hidden="true">✓</span>
                <span className="actionLabel">Закрыть тикет</span>
              </button>
              <button className="btn ghostAccent headerActionBtn" onClick={transferTicket} title="Передать" aria-label="Передать">
                <span className="actionIcon" aria-hidden="true">⇄</span>
                <span className="actionLabel">Передать</span>
              </button>
              <button className="collapseBtn" title="Свернуть правую панель" onClick={() => setRightCollapsed((v) => !v)}>{rightCollapsed ? '◀' : '▶'}</button>
            </div>
          </div>
          <div ref={messagesRef} onScroll={handleMessagesScroll} className="messagesList">
            {messages.length === 0 ? (
              <div className="emptyState"><div className="emptyCard">Сообщений пока нет</div></div>
            ) : (
              messages.map((m) => {
                const mine = myId !== null && m.sender_id === myId
                const time = m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
                const checks = m.status === 'sent' ? '✓' : '✓✓'
                const checksClass = m.status === 'read' ? 'text-sky-300' : 'text-slate-300'
                return (
                  <div key={m.id} className={clsx('messageWrap', mine ? 'operator' : 'client')}>
                    <div className="bubbleCol">
                      <div className={clsx('bubble', mine ? 'operator' : 'client')}>
                        <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
                      </div>
                      <div className="msgTime">
                        {time} {mine && <span className={checksClass}>{checks}</span>}
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
          {showJumpDown && (
            <div className="jumpWrap" style={{ bottom: `${jumpBottomOffset}px` }}>
              <button onClick={jumpToBottom} className="jumpBtn" title="К последним сообщениям" aria-label="К последним сообщениям">
                <span className="jumpArrow">↓</span>
                {newMessagesCount > 0 && <span className="jumpBadge">{newMessagesCount}</span>}
              </button>
            </div>
          )}
          {isActiveConversationClosed ? (
            <div ref={bottomPanelRef} className="closedUiWrap">
              <div className="closedBlock">
                <div className="checkCircle" aria-hidden="true">✓</div>
                <div className="closedText">
                  <div className="closedTitle">Диалог завершен</div>
                  <div className="closedSub">Тикет закрыт - новые сообщения недоступны</div>
                </div>
                <div className="closedTime">
                  {activeConversation?.closed_at
                    ? new Date(activeConversation.closed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : '—'}
                </div>
              </div>
              <div className="inputDead" aria-hidden="true">
                <span className="inputDeadLock">🔒</span>
                <span>Ввод заблокирован</span>
              </div>
            </div>
          ) : (
          <div ref={bottomPanelRef} className="composer">
            <div className="aiRow">
              <button onClick={onSuggest} disabled={assistBusy} className="btn ghostAccent">Подсказать ответ</button>
              <button onClick={onImprove} disabled={assistBusy} className="btn">Улучшить текст</button>
            </div>
            <div className="textareaWrap">
              <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  onSend()
                }
              }} placeholder={isActiveConversationClosed ? 'Диалог закрыт' : 'Введите сообщение...'} className="input" disabled={isActiveConversationClosed} />
              <button onClick={onSend} disabled={busy || (role !== 'client' && !conversationId) || isActiveConversationClosed} className="sendBtn">{busy ? '...' : 'Отправить'}</button>
            </div>
            {connectionError && (
              <p className="mt-2 text-sm text-amber-300">
                {isReconnectingNow ? 'Подключение...' : `Не удалось подключиться. Проверьте интернет и попробуйте еще раз. Повторная попытка через ${reconnectIn ?? 5} сек.`}
              </p>
            )}
            {error && !(connectionError && error.includes('Не удалось подключиться')) && <p className="mt-2 text-sm text-rose-300">{error}</p>}
            {assistHint && <p className="mt-2 text-sm text-emerald-300">{assistHint}</p>}
          </div>
          )}
        </main>

        <aside className="panel right" style={{ display: mobileMode === 'info' ? 'flex' : undefined }}>
          <div className="rightHeader">
            <div className="name">Инфо о клиенте</div>
          </div>
          <div className="rightBody">
            <div className="card">
              <div className="cardTitle">Карточка клиента</div>
              <div className="kv"><div className="kvKey">Email</div><div>{activeConversation ? activeClientEmail : '—'}</div></div>
              <div className="kv"><div className="kvKey">Клиент ID</div><div>{activeConversation ? activeConversation.client_id : '—'}</div></div>
              <div className="kv"><div className="kvKey">Диалог</div><div>{activeConversation ? `#${activeConversation.id}` : '—'}</div></div>
            </div>

            <div className="card historyCard">
              <div className="cardTitle">История тикетов</div>
              <div className="historyList growList">
                {clientHistory.length <= 1 && activeConversation ? <div className="historyEmpty">Первое обращение клиента</div> : null}
                {clientHistory.map((c) => (
                  <button
                    key={`h-${c.id}`}
                    className={clsx('historyItem', 'historyItemBtn', conversationId === c.id && 'active')}
                    onClick={() => onTakeConversation(c.id)}
                    title={new Date(c.created_at).toLocaleDateString('ru-RU')}
                  >
                    <div className="historyTop">
                      <span className="historyTicket">#{c.id}</span>
                      <span className={clsx('historyStatus', c.status === 'closed' ? 'closed' : 'open')}>
                        {c.status === 'closed' ? 'Закрыт' : 'Открыт'}
                      </span>
                    </div>
                    <div className="historyPreview">{c.first_message_preview || c.title}</div>
                    <div className="historyMeta">
                      <span className="historyDate">{formatHistoryDate(c.created_at)}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="cardTitle">Теги и метки</div>
              {role !== 'client' && (
                <button
                  className={clsx('priorityBtn', activeTags.includes('Срочно') && 'active')}
                  onClick={() => void togglePriority()}
                >
                  <span aria-hidden="true">⚑</span>
                  <span>{activeTags.includes('Срочно') ? 'Приоритет активен' : 'Сделать приоритетным'}</span>
                </button>
              )}
              <div className="tags" style={{ marginBottom: 8 }}>
                {activeTags.map((tag) => (
                  <span key={`t-${tag}`} className="tag tagWithClose">
                    {tag}
                    {role !== 'client' && <button className="tagClose" onClick={() => removeTag(tag)}>×</button>}
                  </span>
                ))}
              </div>
              {role !== 'client' && (
                <>
                  <div className="tags" style={{ marginBottom: 8 }}>
                    {suggestedTags.filter((tag) => !activeTags.includes(tag)).map((tag) => (
                      <button key={`s-${tag}`} className="tagAddBtn" onClick={() => addTag(tag)}>+ {tag}</button>
                    ))}
                  </div>
                  <div className="tagManualRow">
                    <div className="tagInputWrap" ref={tagDropdownRef}>
                      <input
                        value={manualTag}
                        onChange={(e) => setManualTag(e.target.value)}
                        onFocus={() => setShowTagDropdown(true)}
                        onClick={() => setShowTagDropdown(true)}
                        placeholder="Свой тег"
                        className="input"
                        style={{ minHeight: 38, maxHeight: 38 }}
                      />
                      {showTagDropdown && (
                        <div className="tagDropdown">
                          {frequentTags.filter((tag) => !activeTags.includes(tag)).map((tag) => (
                            <button
                              key={`f-${tag}`}
                              className="tagDropdownItem"
                              onMouseDown={(e) => e.preventDefault()}
                              onClick={() => {
                                void addTag(tag)
                                setManualTag('')
                                setShowTagDropdown(false)
                              }}
                            >
                              {tag}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <button className="btn" onClick={() => { void addTag(manualTag); setManualTag('') }}>Добавить тег</button>
                  </div>
                </>
              )}
              {role === 'client' && (
                <div className="tags">
                  {activeTags.length === 0 ? <span className="sub">Теги пока не заданы</span> : null}
                </div>
              )}
            </div>

          {role === 'admin' && (
            <div className="card">
              <div className="cardTitle">Админ: назначение</div>
              <div className="flex flex-wrap gap-2">
                <select value={assignClientId ?? ''} onChange={(e) => setAssignClientId(Number(e.target.value))} className="input" style={{ minHeight: 40, maxHeight: 40 }}>
                  {clients.map((c) => (
                    <option key={c.id} value={c.id}>{c.email}</option>
                  ))}
                </select>
                <select value={assignWorkerId ?? ''} onChange={(e) => setAssignWorkerId(Number(e.target.value))} className="input" style={{ minHeight: 40, maxHeight: 40 }}>
                  {workers.map((w) => (
                    <option key={w.id} value={w.id}>{w.email}</option>
                  ))}
                </select>
                <button onClick={onAssignWorker} className="btn primary">Назначить</button>
              </div>
            </div>
          )}

          </div>
        </aside>
      </div>
    </div>
  )
}

export function App() {
  const token = useAssistStore((s) => s.token)
  return token ? <ChatScreen /> : <AuthScreen />
}
