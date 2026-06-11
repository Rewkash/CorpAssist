export function formatHistoryDate(iso: string) {
  const dt = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - dt.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays >= 0 && diffDays < 7) {
    if (diffDays === 0) return 'сегодня'
    if (diffDays === 1) return '1 день назад'
    if (diffDays < 5) return `${diffDays} дня назад`
    return `${diffDays} дней назад`
  }

  return dt.toLocaleDateString('ru-RU')
}
