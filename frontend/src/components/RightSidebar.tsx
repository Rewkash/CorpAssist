import clsx from 'clsx'
import type { RefObject } from 'react'

import type { Conversation } from '../api'

type UserRole = 'admin' | 'worker' | 'client'

type ClientOption = {
  id: number
  email: string
  assigned_worker_id: number | null
}

type WorkerOption = {
  id: number
  email: string
}

type RightSidebarProps = {
  mobileMode: 'list' | 'chat' | 'info'
  activeConversation: Conversation | null
  activeClientEmail: string
  clientHistory: Conversation[]
  conversationId: number | null
  role: UserRole
  activeTags: string[]
  suggestedTags: string[]
  isGeneratingTags: boolean
  frequentTags: string[]
  manualTag: string
  showTagDropdown: boolean
  tagDropdownRef: RefObject<HTMLDivElement | null>
  assignClientId: number | null
  assignWorkerId: number | null
  clients: ClientOption[]
  workers: WorkerOption[]
  onTakeConversation: (conversationId: number) => void
  onTogglePriority: () => void
  onAddTag: (tag: string) => void
  onRemoveTag: (tag: string) => void
  onRegenerateTags: () => void
  onManualTagChange: (tag: string) => void
  onShowTagDropdown: () => void
  onHideTagDropdown: () => void
  onAssignClientId: (clientId: number) => void
  onAssignWorkerId: (workerId: number) => void
  onAssignWorker: () => void
  formatHistoryDate: (iso: string) => string
}

export function RightSidebar({
  mobileMode,
  activeConversation,
  activeClientEmail,
  clientHistory,
  conversationId,
  role,
  activeTags,
  suggestedTags,
  isGeneratingTags,
  frequentTags,
  manualTag,
  showTagDropdown,
  tagDropdownRef,
  assignClientId,
  assignWorkerId,
  clients,
  workers,
  onTakeConversation,
  onTogglePriority,
  onAddTag,
  onRemoveTag,
  onRegenerateTags,
  onManualTagChange,
  onShowTagDropdown,
  onHideTagDropdown,
  onAssignClientId,
  onAssignWorkerId,
  onAssignWorker,
  formatHistoryDate
}: RightSidebarProps) {
  return (
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
            {clientHistory.map((conversation) => (
              <button
                key={`h-${conversation.id}`}
                className={clsx('historyItem', 'historyItemBtn', conversationId === conversation.id && 'active')}
                onClick={() => onTakeConversation(conversation.id)}
                title={new Date(conversation.created_at).toLocaleDateString('ru-RU')}
              >
                <div className="historyTop">
                  <span className="historyTicket">#{conversation.id}</span>
                  <span className={clsx('historyStatus', conversation.status === 'closed' ? 'closed' : 'open')}>
                    {conversation.status === 'closed' ? 'Закрыт' : 'Открыт'}
                  </span>
                </div>
                <div className="historyPreview">{conversation.first_message_preview || conversation.title}</div>
                <div className="historyMeta">
                  <span className="historyDate">{formatHistoryDate(conversation.created_at)}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="cardTitle">Теги и метки</div>
          {role !== 'client' && (
            <div className="tagsToolbar">
              <button
                className="btn ghostAccent tagRegenerateBtn"
                onClick={onRegenerateTags}
                disabled={isGeneratingTags || !conversationId}
              >
                {isGeneratingTags ? 'Генерация…' : 'Перегенерировать теги'}
              </button>
              {isGeneratingTags && <span className="tagGeneratingHint">ИИ подбирает теги…</span>}
            </div>
          )}
          {role !== 'client' && (
            <button
              className={clsx('priorityBtn', activeTags.includes('Срочно') && 'active')}
              onClick={onTogglePriority}
            >
              <span aria-hidden="true">⚑</span>
              <span>{activeTags.includes('Срочно') ? 'Приоритет активен' : 'Сделать приоритетным'}</span>
            </button>
          )}
          <div className="tags" style={{ marginBottom: 8 }}>
            {activeTags.map((tag) => (
              <span key={`t-${tag}`} className="tag tagWithClose">
                {tag}
                {role !== 'client' && <button className="tagClose" onClick={() => onRemoveTag(tag)}>×</button>}
              </span>
            ))}
          </div>
          {role !== 'client' && (
            <>
              <div className="tags" style={{ marginBottom: 8 }}>
                {suggestedTags.filter((tag) => !activeTags.includes(tag)).map((tag) => (
                  <button key={`s-${tag}`} className="tagAddBtn" onClick={() => onAddTag(tag)}>+ {tag}</button>
                ))}
              </div>
              <div className="tagManualRow">
                <div className="tagInputWrap" ref={tagDropdownRef}>
                  <input
                    value={manualTag}
                    onChange={(event) => onManualTagChange(event.target.value)}
                    onFocus={onShowTagDropdown}
                    onClick={onShowTagDropdown}
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
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => {
                            onAddTag(tag)
                            onManualTagChange('')
                            onHideTagDropdown()
                          }}
                        >
                          {tag}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button className="btn" onClick={() => { onAddTag(manualTag); onManualTagChange('') }}>Добавить тег</button>
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
              <select value={assignClientId ?? ''} onChange={(event) => onAssignClientId(Number(event.target.value))} className="input" style={{ minHeight: 40, maxHeight: 40 }}>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>{client.email}</option>
                ))}
              </select>
              <select value={assignWorkerId ?? ''} onChange={(event) => onAssignWorkerId(Number(event.target.value))} className="input" style={{ minHeight: 40, maxHeight: 40 }}>
                {workers.map((worker) => (
                  <option key={worker.id} value={worker.id}>{worker.email}</option>
                ))}
              </select>
              <button onClick={onAssignWorker} className="btn primary">Назначить</button>
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
