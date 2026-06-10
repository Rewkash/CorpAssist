import { useRef, useState } from 'react'

import { useViewportWidth } from '../../../hooks/useViewportWidth'

export function useSidebarUiState() {
  const [search, setSearch] = useState('')
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [mobileMode, setMobileMode] = useState<'list' | 'chat' | 'info'>('chat')
  const viewportWidth = useViewportWidth()
  const [manualTag, setManualTag] = useState('')
  const [showTagDropdown, setShowTagDropdown] = useState(false)
  const tagDropdownRef = useRef<HTMLDivElement | null>(null)

  return {
    search,
    setSearch,
    rightCollapsed,
    setRightCollapsed,
    mobileMode,
    setMobileMode,
    viewportWidth,
    manualTag,
    setManualTag,
    showTagDropdown,
    setShowTagDropdown,
    tagDropdownRef,
  }
}
