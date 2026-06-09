import type { RefObject } from 'react'

type ClosedConversationPanelProps = {
  closedAt?: string | null
  bottomPanelRef: RefObject<HTMLDivElement | null>
}

export function ClosedConversationPanel({ closedAt, bottomPanelRef }: ClosedConversationPanelProps) {
  return (
    <div ref={bottomPanelRef} className="closedUiWrap">
      <div className="closedBlock">
        <div className="checkCircle" aria-hidden="true">✓</div>
        <div className="closedText">
          <div className="closedTitle">Диалог завершен</div>
          <div className="closedSub">Тикет закрыт - новые сообщения недоступны</div>
        </div>
        <div className="closedTime">
          {closedAt
            ? new Date(closedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : '—'}
        </div>
      </div>
      <div className="inputDead" aria-hidden="true">
        <span className="inputDeadLock">🔒</span>
        <span>Ввод заблокирован</span>
      </div>
    </div>
  )
}
