import { useEffect } from 'react'

export function useDocumentThemeClass(theme: 'light' | 'dark') {
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])
}
