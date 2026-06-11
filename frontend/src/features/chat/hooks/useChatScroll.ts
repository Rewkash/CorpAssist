import { useEffect, useRef, useState } from 'react'

import { markMessagesRead } from '../../../api'
import type { ChatMessage } from '../../../api'

type UseChatScrollParams = {
  token: string | null
  conversationId: number | null
  messages: ChatMessage[]
  myId: number | null
  text: string
  assistHint: string
  connectionError: boolean
  error: string
}

export function useChatScroll({
  token,
  conversationId,
  messages,
  myId,
  text,
  assistHint,
  connectionError,
  error,
}: UseChatScrollParams) {
  const messagesRef = useRef<HTMLDivElement | null>(null)
  const prevConversationRef = useRef<number | null>(null)
  const prevMessagesCountRef = useRef(0)
  const prevIncomingCountRef = useRef(0)
  const openedConversationsRef = useRef<Record<number, boolean>>({})
  const forceScrollOnNextRenderRef = useRef(false)
  const isAtBottomRef = useRef(true)
  const isScrollingToBottomRef = useRef(false)
  const [firstUnreadId, setFirstUnreadId] = useState<number | null>(null)
  const [isUnreadDividerHiding, setIsUnreadDividerHiding] = useState(false)
  const unreadDividerHideTimerRef = useRef<number | null>(null)
  const [newMessagesCount, setNewMessagesCount] = useState(0)
  const [showJumpDown, setShowJumpDown] = useState(false)
  const [jumpBottomOffset, setJumpBottomOffset] = useState(138)
  const bottomPanelRef = useRef<HTMLDivElement | null>(null)

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
    return () => {
      if (unreadDividerHideTimerRef.current !== null) {
        window.clearTimeout(unreadDividerHideTimerRef.current)
      }
    }
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
      prevIncomingCountRef.current = messages.filter((message) => myId === null || message.sender_id !== myId).length
    } else {
      const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
      const incomingCount = messages.filter((message) => myId === null || message.sender_id !== myId).length
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
          setNewMessagesCount((value) => value + incomingDelta)
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
    prevIncomingCountRef.current = messages.filter((message) => myId === null || message.sender_id !== myId).length
    if (token && conversationId) {
      markMessagesRead(token, conversationId).catch(() => {})
    }
  }

  return {
    messagesRef,
    bottomPanelRef,
    forceScrollOnNextRenderRef,
    isAtBottomRef,
    firstUnreadId,
    setFirstUnreadId,
    isUnreadDividerHiding,
    newMessagesCount,
    showJumpDown,
    jumpBottomOffset,
    clearUnreadDividerSmooth,
    handleMessagesScroll,
    jumpToBottom,
  }
}
