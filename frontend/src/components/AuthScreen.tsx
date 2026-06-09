import { FormEvent, useState } from 'react'
import clsx from 'clsx'

import { login, me, register } from '../api'
import { useAssistStore } from '../store'

type AuthMode = 'login' | 'register'

export function AuthScreen() {
  const { setAuth, theme, toggleTheme } = useAssistStore()
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [registerRole, setRegisterRole] = useState<'client' | 'worker'>('client')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const token = mode === 'login' ? await login({ email, password }) : await register({ email, password, role: registerRole })
      const profile = await me(token)
      setAuth(token, profile.email, profile.role)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось выполнить вход')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_0%_0%,#dde9ff_0%,#f6f8fc_40%,#eef2f8_100%)] p-4 dark:bg-[radial-gradient(circle_at_0%_0%,#1a2437_0%,#0b1220_45%,#0a101b_100%)]">
      <div className="w-full max-w-md rounded-3xl border border-white/50 bg-white/80 p-6 shadow-2xl backdrop-blur-xl dark:border-slate-700/80 dark:bg-slate-900/75">
        <div className="mb-5 flex items-start justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">CorpAssist</p>
            <h1 className="text-2xl font-semibold">Чат с поддержкой</h1>
          </div>
          <button onClick={toggleTheme} className="rounded-lg border border-slate-300 px-3 py-2 text-xs dark:border-slate-700">
            {theme === 'light' ? 'Dark' : 'Light'}
          </button>
        </div>

        <div className="mb-4 grid grid-cols-2 rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
          <button onClick={() => setMode('login')} className={clsx('rounded-lg py-2 text-sm', mode === 'login' && 'bg-white shadow dark:bg-slate-700')}>
            Вход
          </button>
          <button onClick={() => setMode('register')} className={clsx('rounded-lg py-2 text-sm', mode === 'register' && 'bg-white shadow dark:bg-slate-700')}>
            Регистрация
          </button>
        </div>

        <form onSubmit={onSubmit} className="space-y-3">
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" type="email" required className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-cyan-500 dark:border-slate-700 dark:bg-slate-950" />
          <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Пароль" type="password" minLength={8} required className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-cyan-500 dark:border-slate-700 dark:bg-slate-950" />
          {mode === 'register' && (
            <select value={registerRole} onChange={(e) => setRegisterRole(e.target.value as 'client' | 'worker')} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-cyan-500 dark:border-slate-700 dark:bg-slate-950">
              <option value="client">Я клиент</option>
              <option value="worker">Я сотрудник</option>
            </select>
          )}
          {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/30 dark:text-rose-300">{error}</div>}
          <button disabled={loading} className="w-full rounded-xl bg-slate-900 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:opacity-60 dark:bg-cyan-600 dark:hover:bg-cyan-500">
            {loading ? 'Проверяем...' : mode === 'login' ? 'Войти' : 'Создать аккаунт'}
          </button>
        </form>
      </div>
    </div>
  )
}
