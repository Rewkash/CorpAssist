import { authFetch } from './client'
import type { AdminUser } from './types'

export async function getWorkers(token: string): Promise<AdminUser[]> {
  const response = await authFetch('/admin/workers', token)
  return response.json()
}

export async function getClients(token: string): Promise<AdminUser[]> {
  const response = await authFetch('/admin/clients', token)
  return response.json()
}

export async function assignWorker(token: string, clientId: number, workerId: number): Promise<void> {
  await authFetch('/admin/assign-worker', token, {
    method: 'POST',
    body: JSON.stringify({ client_id: clientId, worker_id: workerId })
  })
}
