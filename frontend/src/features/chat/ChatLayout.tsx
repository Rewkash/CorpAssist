import clsx from 'clsx'

import type { ChatLayoutProps } from './chatScreenTypes'
import { ChatCenterPanel } from './sections/ChatCenterPanel'
import { ChatSidebarPanel } from './sections/ChatSidebarPanel'
import { ConversationPanel } from './sections/ConversationPanel'

export function ChatLayout({ rightCollapsed, conversation, center, sidebar }: ChatLayoutProps) {
  return (
    <div className="supportRoot">
      <div className={clsx('appShell', rightCollapsed && 'rightCollapsed')}>
        <ConversationPanel {...conversation} />
        <ChatCenterPanel {...center} />
        <ChatSidebarPanel {...sidebar} />
      </div>
    </div>
  )
}
