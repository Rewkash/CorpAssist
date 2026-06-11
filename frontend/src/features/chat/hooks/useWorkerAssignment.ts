import { assignWorker, getClients } from '../../../api'
import { useChatStore } from '../store/chatStore'

type UseWorkerAssignmentParams = {
  token: string
  setError: (message: string) => void
}

export function useWorkerAssignment({
  token,
  setError,
}: UseWorkerAssignmentParams) {
  const assignClientId = useChatStore((state) => state.assignClientId)
  const assignWorkerId = useChatStore((state) => state.assignWorkerId)
  const setClients = useChatStore((state) => state.setClients)

  const assignSelectedWorker = async () => {
    if (!token || !assignClientId || !assignWorkerId) return
    try {
      await assignWorker(token, assignClientId, assignWorkerId)
      const clientList = await getClients(token)
      setClients(clientList)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось назначить сотрудника')
    }
  }

  return { assignSelectedWorker }
}
