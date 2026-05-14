import { create } from 'zustand'

export type Role = 'admin' | 'worker' | 'client'

type DiffChunk = {
  type: 'equal' | 'insert' | 'delete'
  value: string
}

type Analysis = {
  sentiment: 'neutral' | 'tense' | 'positive'
  topics: string[]
  formality: 'low' | 'medium' | 'high'
}

type AssistState = {
  token: string
  email: string
  role: Role | null
  input: string
  conversationId: number | null
  analysis: Analysis | null
  suggestions: string[]
  improvedText: string
  diff: DiffChunk[]
  loading: boolean
  theme: 'light' | 'dark'
  setAuth: (token: string, email: string, role: Role) => void
  logout: () => void
  setConversationId: (id: number | null) => void
  setInput: (value: string) => void
  setAnalysis: (value: Analysis | null) => void
  setSuggestions: (value: string[]) => void
  setImproved: (text: string, diff: DiffChunk[]) => void
  setLoading: (value: boolean) => void
  toggleTheme: () => void
}

export const useAssistStore = create<AssistState>((set) => ({
  token: localStorage.getItem('ca_token') || '',
  email: localStorage.getItem('ca_email') || '',
  role: (localStorage.getItem('ca_role') as Role | null) || null,
  input: '',
  conversationId: null,
  analysis: null,
  suggestions: [],
  improvedText: '',
  diff: [],
  loading: false,
  theme: 'light',
  setAuth: (token, email, role) => {
    localStorage.setItem('ca_token', token)
    localStorage.setItem('ca_email', email)
    localStorage.setItem('ca_role', role)
    set({ token, email, role })
  },
  logout: () => {
    localStorage.removeItem('ca_token')
    localStorage.removeItem('ca_email')
    localStorage.removeItem('ca_role')
    set({ token: '', email: '', role: null, conversationId: null, suggestions: [], improvedText: '', diff: [], analysis: null, input: '' })
  },
  setConversationId: (conversationId) => set({ conversationId }),
  setInput: (input) => set({ input }),
  setAnalysis: (analysis) => set({ analysis }),
  setSuggestions: (suggestions) => set({ suggestions }),
  setImproved: (improvedText, diff) => set({ improvedText, diff }),
  setLoading: (loading) => set({ loading }),
  toggleTheme: () => set((s) => ({ theme: s.theme === 'light' ? 'dark' : 'light' }))
}))
