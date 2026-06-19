import { RightSidebar } from '../../../components/RightSidebar'
import { formatHistoryDate } from '../chatFormatters'
import type { ChatSidebarPanelProps } from '../chatScreenTypes'

export function ChatSidebarPanel({
  onTogglePriority,
  onAddTag,
  onRemoveTag,
  onRegenerateTags,
  ...props
}: ChatSidebarPanelProps) {
  return (
    <RightSidebar
      {...props}
      onTogglePriority={() => void onTogglePriority()}
      onAddTag={(tag) => void onAddTag(tag)}
      onRemoveTag={(tag) => void onRemoveTag(tag)}
      onRegenerateTags={() => void onRegenerateTags()}
      formatHistoryDate={formatHistoryDate}
    />
  )
}
