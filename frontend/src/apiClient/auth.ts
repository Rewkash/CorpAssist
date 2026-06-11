import { API_BASE, authFetch } from './client'
import type { AuthPayload, Me } from './types'

export async function login(payload: AuthPayload): Promise<string> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  } catch {
    throw new Error('Не удалось подключиться. Проверьте интернет и попробуйте еще раз.')
  }
  if (!response.ok) throw new Error('Не получилось войти. Проверьте email и пароль.')
  const data = await response.json()
  return data.access_token
}

export async function register(payload: AuthPayload): Promise<string> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  } catch {
    throw new Error('Не удалось подключиться. Проверьте интернет и попробуйте еще раз.')
  }
  if (!response.ok) {
    let message = 'Не получилось создать аккаунт. Попробуйте еще раз.'
    try {
      const data = await response.json()
      const detail = data?.detail
      if (typeof detail === 'string' && detail.includes('exists')) {
        message = 'Такой email уже зарегистрирован. Войдите в аккаунт или используйте другой email.'
      } else if (Array.isArray(detail)) {
        message = 'Проверьте email и пароль и попробуйте еще раз.'
      }
    } catch {}
    throw new Error(message)
  }
  const data = await response.json()
  return data.access_token
}

export async function me(token: string): Promise<Me> {
  const response = await authFetch('/auth/me', token)
  return response.json()
}
