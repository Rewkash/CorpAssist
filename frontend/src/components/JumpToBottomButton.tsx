type JumpToBottomButtonProps = {
  bottomOffset: number
  newMessagesCount: number
  onClick: () => void
}

export function JumpToBottomButton({ bottomOffset, newMessagesCount, onClick }: JumpToBottomButtonProps) {
  return (
    <div className="jumpWrap" style={{ bottom: `${bottomOffset}px` }}>
      <button onClick={onClick} className="jumpBtn" title="К последним сообщениям" aria-label="К последним сообщениям">
        <span className="jumpArrow">↓</span>
        {newMessagesCount > 0 && <span className="jumpBadge">{newMessagesCount}</span>}
      </button>
    </div>
  )
}
