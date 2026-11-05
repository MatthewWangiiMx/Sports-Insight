import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { GameLogEntry } from '../api'
import { GameChart, GamesTable, shortDate } from './GameChart'

const game = (date: string, opp: string, us: number, them: number, elo: number): GameLogEntry => ({
  game_id: `g-${date}`, date, opponent_id: 1, opponent_abbreviation: opp, is_home: true, neutral_site: false,
  win: us > them, team_score: us, opp_score: them, point_diff: us - them, elo,
})

const GAMES = [
  game('2026-10-22', 'BOS', 110, 98, 1610),
  game('2026-10-24', 'NYK', 101, 108, 1601),
  game('2026-11-02', 'DEN', 118, 106, 1612),
]

describe('shortDate', () => {
  it("formats without shifting the day in any time zone", () => {
    expect(shortDate('2026-11-02')).toBe('Nov 2')
  })
})

describe('GameChart', () => {
  it('shows the latest game until a bar is hovered', () => {
    render(<GameChart games={GAMES} onOpenGame={vi.fn()} onSelectGame={vi.fn()} />)
    expect(screen.getByText('Latest game')).toBeInTheDocument()
    expect(screen.getByText('(+12)')).toBeInTheDocument()

    fireEvent.mouseEnter(screen.getByRole('button', { name: /NYK: lost 101 to 108/ }))
    expect(screen.getByText('Game 2')).toBeInTheDocument()
    expect(screen.getByText('(-7)')).toBeInTheDocument()
  })

  it('draws one bar per game, up for wins and down for losses', () => {
    const { container } = render(<GameChart games={GAMES} onOpenGame={vi.fn()} onSelectGame={vi.fn()} />)
    expect(container.querySelectorAll('.chart-bar.win')).toHaveLength(2)
    expect(container.querySelectorAll('.chart-bar.loss')).toHaveLength(1)
    // Month labels only where the month changes.
    expect([...container.querySelectorAll('.chart-month')].map((m) => m.textContent)).toEqual(['Oct', 'Nov'])
  })

  it('opens a clicked bar as a box score, and the shown game in the games list', () => {
    const onOpenGame = vi.fn()
    const onSelectGame = vi.fn()
    render(<GameChart games={GAMES} onOpenGame={onOpenGame} onSelectGame={onSelectGame} />)
    fireEvent.click(screen.getByRole('button', { name: /BOS: won 110 to 98/ }))
    expect(onSelectGame).toHaveBeenCalledWith(0)
    // The click also pins the readout to that game.
    fireEvent.click(screen.getByRole('button', { name: /See in games list/ }))
    expect(onOpenGame).toHaveBeenCalledWith(0)
  })
})

describe('GamesTable', () => {
  it('lists games most recent first and highlights the focused one', () => {
    const onSelectGame = vi.fn()
    render(<GamesTable games={GAMES} focus={0} onSelectGame={onSelectGame} />)
    const rows = screen.getAllByRole('row').slice(1) // skip the header
    expect(within(rows[0]).getByText('DEN')).toBeInTheDocument()
    expect(within(rows[2]).getByText('BOS')).toBeInTheDocument()
    expect(rows[2]).toHaveClass('focused')
    // Elo change since the previous game.
    expect(within(rows[0]).getByText('+11')).toBeInTheDocument()
    fireEvent.click(rows[0])
    expect(onSelectGame).toHaveBeenCalledWith(2) // index into the season, oldest first
  })
})
