import type { CSSProperties } from 'react'

// Static team branding. NBA team ids never change, so hardcoding them lets us
// show a logo anywhere we only have an abbreviation (player pages, game logs).
// Colors are each team's official primary/secondary, darkened where the real
// primary is too light to sit behind white text (e.g. Spurs silver).
const TEAMS: Record<string, { id: number; colors: [string, string] }> = {
  ATL: { id: 1610612737, colors: ['#C8102E', '#FDB927'] },
  BOS: { id: 1610612738, colors: ['#007A33', '#BA9653'] },
  CLE: { id: 1610612739, colors: ['#860038', '#FDBB30'] },
  NOP: { id: 1610612740, colors: ['#0C2340', '#C8102E'] },
  CHI: { id: 1610612741, colors: ['#CE1141', '#000000'] },
  DAL: { id: 1610612742, colors: ['#00538C', '#B8C4CA'] },
  DEN: { id: 1610612743, colors: ['#0E2240', '#FEC524'] },
  GSW: { id: 1610612744, colors: ['#1D428A', '#FFC72C'] },
  HOU: { id: 1610612745, colors: ['#CE1141', '#C4CED4'] },
  LAC: { id: 1610612746, colors: ['#C8102E', '#1D428A'] },
  LAL: { id: 1610612747, colors: ['#552583', '#FDB927'] },
  MIA: { id: 1610612748, colors: ['#98002E', '#F9A01B'] },
  MIL: { id: 1610612749, colors: ['#00471B', '#EEE1C6'] },
  MIN: { id: 1610612750, colors: ['#0C2340', '#78BE20'] },
  BKN: { id: 1610612751, colors: ['#111111', '#777D84'] },
  NYK: { id: 1610612752, colors: ['#006BB6', '#F58426'] },
  ORL: { id: 1610612753, colors: ['#0077C0', '#C4CED4'] },
  IND: { id: 1610612754, colors: ['#002D62', '#FDBB30'] },
  PHI: { id: 1610612755, colors: ['#006BB6', '#ED174C'] },
  PHX: { id: 1610612756, colors: ['#1D1160', '#E56020'] },
  POR: { id: 1610612757, colors: ['#E03A3E', '#000000'] },
  SAC: { id: 1610612758, colors: ['#5A2D81', '#63727A'] },
  SAS: { id: 1610612759, colors: ['#1A1A1A', '#C4CED4'] },
  OKC: { id: 1610612760, colors: ['#007AC1', '#EF3B24'] },
  TOR: { id: 1610612761, colors: ['#CE1141', '#000000'] },
  UTA: { id: 1610612762, colors: ['#002B5C', '#F9A01B'] },
  MEM: { id: 1610612763, colors: ['#5D76A9', '#12173F'] },
  WAS: { id: 1610612764, colors: ['#002B5C', '#E31837'] },
  DET: { id: 1610612765, colors: ['#C8102E', '#1D42BA'] },
  CHA: { id: 1610612766, colors: ['#1D1160', '#00788C'] },
}

const FALLBACK_COLORS: [string, string] = ['#4c1d95', '#9333ea']

export function teamIdFor(abbreviation: string): number | undefined {
  return TEAMS[abbreviation]?.id
}

// Served by the NBA's public CDN - the same images nba.com uses.
export function teamLogoUrl(teamId: number): string {
  return `https://cdn.nba.com/logos/nba/${teamId}/global/L/logo.svg`
}

export function headshotUrl(playerId: number, large = false): string {
  const size = large ? '1040x760' : '260x190'
  return `https://cdn.nba.com/headshots/nba/latest/${size}/${playerId}.png`
}

function colorsFor(abbreviation: string | undefined): [string, string] {
  return (abbreviation && TEAMS[abbreviation]?.colors) || FALLBACK_COLORS
}

function themeOf([main, accent]: [string, string]): CSSProperties {
  return { '--team-1': main, '--team-2': accent } as CSSProperties
}

// CSS custom properties consumed by .hero and friends in App.css.
export function teamTheme(abbreviation: string | undefined): CSSProperties {
  return themeOf(colorsFor(abbreviation))
}

// How different two colors look (0 = identical, ~765 = black vs white). The
// "redmean" formula: plain RGB distance, weighted the way the eye weighs
// red/green/blue differences, which is close to perceptual at a fraction of
// the cost of a full Lab conversion.
export function colorDistance(a: string, b: string): number {
  const rgb = (hex: string) => {
    const n = parseInt(hex.slice(1), 16)
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
  }
  const [r1, g1, b1] = rgb(a)
  const [r2, g2, b2] = rgb(b)
  const rMean = (r1 + r2) / 2
  const [dr, dg, db] = [r1 - r2, g1 - g2, b1 - b2]
  return Math.sqrt((2 + rMean / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rMean) / 256) * db * db)
}

// Below this, two main colors read as the "same color family" side by side
// (e.g. Thunder vs Knicks blue = 36, Celtics vs Bucks green = 110).
export const CLASH_DISTANCE = 130

/**
 * Colors for two teams shown together. Like an "alternate kit" in sports
 * broadcasts: if their main colors clash, the away team switches to its
 * secondary color - or, if that still clashes, the home team does - so the two
 * sides stay distinguishable in every bar, tag and card.
 */
export function matchupThemes(home: string | undefined, away: string | undefined): [CSSProperties, CSSProperties] {
  // Only a real pair can clash - with one side still unpicked, keep the chosen team's own colors.
  if (!home || !away) return [teamTheme(home), teamTheme(away)]
  const [hp, hs] = colorsFor(home)
  const [ap, as] = colorsFor(away)
  // In order of preference: both main colors, away alternate, home alternate, both alternate.
  const options: [[string, string], [string, string]][] = [
    [[hp, hs], [ap, as]],
    [[hp, hs], [as, ap]],
    [[hs, hp], [ap, as]],
    [[hs, hp], [as, ap]],
  ]
  const gap = ([h, a]: (typeof options)[number]) => colorDistance(h[0], a[0])
  const pick = options.find((o) => gap(o) >= CLASH_DISTANCE) ?? options.reduce((best, o) => (gap(o) > gap(best) ? o : best))
  return [themeOf(pick[0]), themeOf(pick[1])]
}
