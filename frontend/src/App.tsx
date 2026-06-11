import { AuthScreen } from './components/AuthScreen'
import { ChatScreen } from './features/chat/ChatScreen'
import { useAssistStore } from './store'

export function App() {
  const token = useAssistStore((state) => state.token)

  if (!token) {
    return <AuthScreen />
  }

  return <ChatScreen />
}
