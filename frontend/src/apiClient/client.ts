export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
export const WS_BASE = (import.meta.env.VITE_WS_URL || 'ws://localhost:8000') + '/ws/assist'
export const WS_CHAT_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export async function authFetch(path: string, token: string, init?: RequestInit) {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(init?.headers || {})
      }
    })
  } catch {
    throw new Error('Не удалось подключиться. Проверьте интернет и попробуйте еще раз.')
  }
  if (!response.ok) {
    let message = 'Что-то пошло не так. Попробуйте еще раз.'
    try {
      const data = await response.json()
      if (typeof data?.detail === 'string') message = data.detail
    } catch {}
    throw new Error(message)
  }
  return response
}
