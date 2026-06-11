import type { ChangeEventHandler, KeyboardEventHandler, RefObject } from 'react'

type MessageComposerProps = {
  text: string
  busy: boolean
  role: 'admin' | 'worker' | 'client'
  conversationId: number | null
  assistBusy: boolean
  generatingStatus: string
  replySuggestions: string[]
  connectionError: boolean
  isReconnectingNow: boolean
  reconnectIn: number | null
  error: string
  assistHint: string
  bottomPanelRef: RefObject<HTMLDivElement | null>
  onSuggest: () => void
  onImprove: () => void
  onSend: () => void
  onTextChange: ChangeEventHandler<HTMLInputElement>
  onTextKeyDown: KeyboardEventHandler<HTMLInputElement>
  onHideSuggestions: () => void
  onSelectSuggestion: (suggestion: string) => void
}

export function MessageComposer({
  text,
  busy,
  role,
  conversationId,
  assistBusy,
  generatingStatus,
  replySuggestions,
  connectionError,
  isReconnectingNow,
  reconnectIn,
  error,
  assistHint,
  bottomPanelRef,
  onSuggest,
  onImprove,
  onSend,
  onTextChange,
  onTextKeyDown,
  onHideSuggestions,
  onSelectSuggestion
}: MessageComposerProps) {
  return (
    <div ref={bottomPanelRef} className="composer">
      <div className="aiRow">
        <button onClick={onSuggest} disabled={assistBusy} className="btn ghostAccent">Подсказать ответ</button>
        <button onClick={onImprove} disabled={assistBusy} className="btn">Улучшить текст</button>
        {assistBusy && <span className="text-sm text-cyan-300">{generatingStatus || 'Генерация...'}</span>}
      </div>
      {replySuggestions.length > 0 && (
        <div className="replySuggestions">
          <div className="replySuggestionsHead">
            <span>Варианты ответа</span>
            <button className="replySuggestionsClose" onClick={onHideSuggestions} aria-label="Скрыть варианты">×</button>
          </div>
          <div className="replySuggestionsGrid">
            {replySuggestions.map((suggestion, index) => (
              <button
                key={`${index}-${suggestion.slice(0, 24)}`}
                className="replySuggestionCard"
                onClick={() => onSelectSuggestion(suggestion)}
              >
                <span className="replySuggestionNum">{index + 1}</span>
                <span>{suggestion}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="textareaWrap">
        <input value={text} onChange={onTextChange} onKeyDown={onTextKeyDown} placeholder="Введите сообщение..." className="input" />
        <button onClick={onSend} disabled={busy || (role !== 'client' && !conversationId)} className="sendBtn">{busy ? '...' : 'Отправить'}</button>
      </div>
      {connectionError && (
        <p className="mt-2 text-sm text-amber-300">
          {isReconnectingNow ? 'Подключение...' : `Не удалось подключиться. Проверьте интернет и попробуйте еще раз. Повторная попытка через ${reconnectIn ?? 5} сек.`}
        </p>
      )}
      {error && !(connectionError && error.includes('Не удалось подключиться')) && <p className="mt-2 text-sm text-rose-300">{error}</p>}
      {assistHint && <p className="mt-2 text-sm text-emerald-300">{assistHint}</p>}
    </div>
  )
}
