import { assignWorker, getClients } from '../../../api'

type ClientOption = { id: number; email: string; assigned_worker_id: number | null }

type UseWorkerAssignmentParams = {
  token: string
  assignClientId: number | null
  assignWorkerId: number | null
  setClients: (clients: ClientOption[]) => void
  setError: (message: string) => void
}

export function useWorkerAssignment({
  token,
  assignClientId,
  assignWorkerId,
  setClients,
  setError,
}: UseWorkerAssignmentParams) {
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
