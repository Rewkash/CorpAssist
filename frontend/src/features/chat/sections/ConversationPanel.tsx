import { ConversationList } from '../../../components/ConversationList'
import type { ConversationPanelProps } from '../chatScreenTypes'

export function ConversationPanel(props: ConversationPanelProps) {
  return <ConversationList {...props} />
}
