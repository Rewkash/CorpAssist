import clsx from 'clsx'
import type { RefObject, UIEventHandler } from 'react'

import type { ChatMessage } from '../api'

type MessageListProps = {
  conversationId: number | null
  messages: ChatMessage[]
  myId: number | null
  firstUnreadId: number | null
  isUnreadDividerHiding: boolean
  messagesRef: RefObject<HTMLDivElement | null>
  onScroll: UIEventHandler<HTMLDivElement>
}

export function MessageList({
  conversationId,
  messages,
  myId,
  firstUnreadId,
  isUnreadDividerHiding,
  messagesRef,
  onScroll
}: MessageListProps) {
  return (
    <div key={conversationId ?? 'empty'} ref={messagesRef} onScroll={onScroll} className="messagesList">
      {messages.length === 0 ? (
        <div className="emptyState"><div className="emptyCard">Сообщений пока нет</div></div>
      ) : (
        messages.map((message) => {
          const mine = myId !== null && message.sender_id === myId
          const isFirstUnread = message.id === firstUnreadId
          const time = message.created_at ? new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
          const checks = message.status === 'sent' ? '✓' : '✓✓'
          const checksClass = message.status === 'read' ? 'text-sky-300' : 'text-slate-300'
          return (
            <div key={message.id}>
              {isFirstUnread && (
                <div className={clsx('unreadDivider', isUnreadDividerHiding && 'hiding')} id="unread-anchor">
                  <span>Новые сообщения</span>
                </div>
              )}
              <div className={clsx('messageWrap', mine ? 'operator' : 'client', isFirstUnread && 'highlightNew')}>
                <div className="bubbleCol">
                  <div className={clsx('bubble', mine ? 'operator' : 'client')}>
                    <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
                  </div>
                  <div className="msgTime">
                    {time} {mine && <span className={checksClass}>{checks}</span>}
                  </div>
                </div>
              </div>
            </div>
          )
        })
      )}
    </div>
  )
}
