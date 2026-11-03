import { describe, expect, it } from 'vitest'
import { CLASH_DISTANCE, colorDistance, matchupThemes, teamTheme } from './branding'

const ALL = ['ATL', 'BOS', 'CLE', 'NOP', 'CHI', 'DAL', 'DEN', 'GSW', 'HOU', 'LAC', 'LAL', 'MIA', 'MIL', 'MIN', 'BKN',
  'NYK', 'ORL', 'IND', 'PHI', 'PHX', 'POR', 'SAC', 'SAS', 'OKC', 'TOR', 'UTA', 'MEM', 'WAS', 'DET', 'CHA']
const main = (theme: object) => (theme as Record<string, string>)['--team-1']

describe('colorDistance', () => {
  it('is zero for the same color and large for opposites', () => {
    expect(colorDistance('#007AC1', '#007AC1')).toBe(0)
    expect(colorDistance('#000000', '#FFFFFF')).toBeGreaterThan(700)
    expect(colorDistance('#007AC1', '#006BB6')).toBeLessThan(CLASH_DISTANCE) // Thunder vs Knicks blue
  })
})

describe('matchupThemes', () => {
  it('keeps both main colors when they already differ', () => {
    const [home, away] = matchupThemes('LAL', 'BOS')
    expect(home).toEqual(teamTheme('LAL'))
    expect(away).toEqual(teamTheme('BOS'))
  })

  it('switches the away team to its alternate when the main colors clash', () => {
    const [home, away] = matchupThemes('OKC', 'NYK')
    expect(main(home)).toBe(main(teamTheme('OKC')))
    expect(main(away)).toBe('#F58426') // Knicks orange
  })

  it('keeps every pair of teams distinguishable', () => {
    for (const home of ALL) {
      for (const away of ALL) {
        if (home === away) continue
        const [h, a] = matchupThemes(home, away)
        expect(colorDistance(main(h), main(a)), `${home} vs ${away}`).toBeGreaterThanOrEqual(CLASH_DISTANCE)
      }
    }
  })

  it("leaves a lone team's colors alone while the other side is unpicked", () => {
    expect(matchupThemes('NYK', undefined)[0]).toEqual(teamTheme('NYK'))
    expect(matchupThemes(undefined, 'OKC')[1]).toEqual(teamTheme('OKC'))
  })
})
