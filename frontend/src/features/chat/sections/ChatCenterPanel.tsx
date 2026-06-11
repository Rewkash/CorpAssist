import { ChatHeader } from '../../../components/ChatHeader'
import { ClosedConversationPanel } from '../../../components/ClosedConversationPanel'
import { JumpToBottomButton } from '../../../components/JumpToBottomButton'
import { MessageComposer } from '../../../components/MessageComposer'
import { MessageList } from '../../../components/MessageList'
import type { ChatCenterPanelProps } from '../chatScreenTypes'

export function ChatCenterPanel({
  mobileMode,
  activeConversation,
  role,
  conversationId,
  rightCollapsed,
  messages,
  myId,
  firstUnreadId,
  isUnreadDividerHiding,
  messagesRef,
  bottomPanelRef,
  showJumpDown,
  jumpBottomOffset,
  newMessagesCount,
  isActiveConversationClosed,
  text,
  busy,
  assistBusy,
  generatingStatus,
  replySuggestions,
  connectionError,
  isReconnectingNow,
  reconnectIn,
  error,
  assistHint,
  onCreateClientConversation,
  onCloseTicket,
  onTransferTicket,
  onToggleRightCollapsed,
  onMessagesScroll,
  onJumpToBottom,
  onSuggest,
  onImprove,
  onSend,
  onTextChange,
  onTextKeyDown,
  onHideSuggestions,
  onSelectSuggestion,
}: ChatCenterPanelProps) {
  return (
    <main className="center" style={{ display: mobileMode === 'chat' ? 'flex' : undefined }}>
      <ChatHeader
        activeConversation={activeConversation}
        role={role}
        conversationId={conversationId}
        rightCollapsed={rightCollapsed}
        onCreateClientConversation={onCreateClientConversation}
        onCloseTicket={onCloseTicket}
        onTransferTicket={onTransferTicket}
        onToggleRightCollapsed={onToggleRightCollapsed}
      />
      <MessageList
        conversationId={conversationId}
        messages={messages}
        myId={myId}
        firstUnreadId={firstUnreadId}
        isUnreadDividerHiding={isUnreadDividerHiding}
        messagesRef={messagesRef}
        onScroll={onMessagesScroll}
      />
      {showJumpDown && (
        <JumpToBottomButton bottomOffset={jumpBottomOffset} newMessagesCount={newMessagesCount} onClick={onJumpToBottom} />
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
          onTextChange={onTextChange}
          onTextKeyDown={onTextKeyDown}
          onHideSuggestions={onHideSuggestions}
          onSelectSuggestion={onSelectSuggestion}
        />
      )}
    </main>
  )
}
