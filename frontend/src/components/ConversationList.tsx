import clsx from 'clsx'

import type { Conversation } from '../api'

type UserRole = 'admin' | 'worker' | 'client'

type ConversationListProps = {
  email: string
  role: UserRole
  search: string
  conversations: Conversation[]
  conversationId: number | null
  onSearchChange: (search: string) => void
  onTakeConversation: (conversationId: number) => void
  onLogout: () => void
}

export function ConversationList({
  email,
  role,
  search,
  conversations,
  conversationId,
  onSearchChange,
  onTakeConversation,
  onLogout
}: ConversationListProps) {
  return (
    <aside className="panel left">
      <div className="leftHeader">
        <div className="userChip">
          <div className="avatar">{email.slice(0, 2).toUpperCase()}</div>
          <div className="nameWrap">
            <div className="name">{email}</div>
            <div className="sub">{role === 'admin' ? 'Администратор' : role === 'worker' ? 'Сотрудник' : 'Клиент'}</div>
          </div>
        </div>
        <button onClick={onLogout} className="btn">Выйти</button>
      </div>
      <div className="searchWrap">
        <input className="searchInput" placeholder="Поиск по диалогам..." value={search} onChange={(event) => onSearchChange(event.target.value)} />
      </div>
      <div className="dialogList">
        {conversations.map((conversation) => (
          <button key={conversation.id} onClick={() => onTakeConversation(conversation.id)} className={clsx('dialogCard', conversationId === conversation.id && 'active')}>
            {conversation.unread_count > 0 && <span className="unreadBadge">{conversation.unread_count}</span>}
            <div className="row">
              <span className="ticket">
                {role !== 'client' && conversation.priority_at && <span className="priorityDot" aria-hidden="true">●</span>}
                Диалог #{conversation.id}
              </span>
            </div>
            <div className="preview">{conversation.title}</div>
            <div className="row" style={{ marginTop: 8 }}>
              <span className={clsx('badge', conversation.status === 'closed' ? 'closed' : conversation.worker_id ? 'open' : 'pending')}>
                {conversation.status === 'closed' ? 'Закрыт' : conversation.worker_id ? 'Назначен' : 'Свободен'}
              </span>
              {role !== 'client' && conversation.priority_at && <span className="badge urgent">Срочно</span>}
            </div>
          </button>
        ))}
      </div>
    </aside>
  )
}
