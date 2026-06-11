import type { Conversation } from '../api'

type ChatHeaderProps = {
  activeConversation: Conversation | null
  role: 'admin' | 'worker' | 'client'
  conversationId: number | null
  rightCollapsed: boolean
  onCreateClientConversation: () => void
  onCloseTicket: () => void
  onTransferTicket: () => void
  onToggleRightCollapsed: () => void
}

export function ChatHeader({
  activeConversation,
  role,
  conversationId,
  rightCollapsed,
  onCreateClientConversation,
  onCloseTicket,
  onTransferTicket,
  onToggleRightCollapsed
}: ChatHeaderProps) {
  return (
    <div className="centerHeader">
      <div className="headerLeft">
        <div className="clientName">{activeConversation ? `Диалог #${activeConversation.id}` : 'Диалог не выбран'}</div>
        <div className="sub">{activeConversation ? activeConversation.title : '—'}</div>
      </div>
      <div className="headerActions">
        {role === 'client' && (
          <button className="btn ghostAccent headerActionBtn" onClick={onCreateClientConversation} title="Новый диалог" aria-label="Новый диалог">
            <span className="actionIcon" aria-hidden="true">＋</span>
            <span className="actionLabel">Новый диалог</span>
          </button>
        )}
        <button className="btn headerActionBtn" onClick={onCloseTicket} disabled={!conversationId || role === 'client'} title="Закрыть тикет" aria-label="Закрыть тикет">
          <span className="actionIcon" aria-hidden="true">✓</span>
          <span className="actionLabel">Закрыть тикет</span>
        </button>
        <button className="btn ghostAccent headerActionBtn" onClick={onTransferTicket} title="Передать" aria-label="Передать">
          <span className="actionIcon" aria-hidden="true">⇄</span>
          <span className="actionLabel">Передать</span>
        </button>
        <button className="collapseBtn" title="Свернуть правую панель" onClick={onToggleRightCollapsed}>{rightCollapsed ? '◀' : '▶'}</button>
      </div>
    </div>
  )
}
