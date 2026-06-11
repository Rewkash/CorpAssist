import { ChatLayout } from './ChatLayout'
import { useChatScreenController } from './controllers/useChatScreenController'

export function ChatScreenContainer() {
  const screen = useChatScreenController()

  return <ChatLayout {...screen} />
}
