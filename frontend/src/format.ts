export function num(value: number, digits = 1): string {
  return value.toFixed(digits)
}

export function signed(value: number, digits = 1): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}`
}

export function pct(value: number | null, digits = 1): string {
  return value == null ? '–' : `${(value * 100).toFixed(digits)}%`
}

// Top/bottom sixth of the league get colored rank pills (30 teams -> top/bottom 5).
export function rankTone(rank: number, outOf = 30): 'good' | 'bad' | '' {
  if (rank <= outOf / 6) return 'good'
  if (rank > outOf - outOf / 6) return 'bad'
  return ''
}
