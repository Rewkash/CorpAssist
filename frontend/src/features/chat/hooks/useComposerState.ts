import { useState } from 'react'

export function useComposerState() {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [assistBusy, setAssistBusy] = useState(false)
  const [assistHint, setAssistHint] = useState('')
  const [generatingStatus, setGeneratingStatus] = useState('')
  const [replySuggestions, setReplySuggestions] = useState<string[]>([])

  return {
    text,
    setText,
    busy,
    setBusy,
    assistBusy,
    setAssistBusy,
    assistHint,
    setAssistHint,
    generatingStatus,
    setGeneratingStatus,
    replySuggestions,
    setReplySuggestions,
  }
}
