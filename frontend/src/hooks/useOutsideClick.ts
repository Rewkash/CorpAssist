import { RefObject, useEffect } from 'react'

export function useOutsideClick<T extends HTMLElement>(ref: RefObject<T | null>, onOutsideClick: () => void) {
  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!ref.current) return
      if (!ref.current.contains(event.target as Node)) {
        onOutsideClick()
      }
    }

    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [ref, onOutsideClick])
}
