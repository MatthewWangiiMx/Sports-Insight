import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { GameDetail, GameSide, Team } from '../api'
import { GameModal } from './GameModal'

const OKC: Team = { id: 1610612760, full_name: 'Oklahoma City Thunder', abbreviation: 'OKC', conference: 'West', division: 'Northwest' }
const PHX: Team = { id: 1610612756, full_name: 'Phoenix Suns', abbreviation: 'PHX', conference: 'West', division: 'Pacific' }

const line = (player_id: number, name: string, pts: number) => ({
  player_id, name, min: 30, pts, reb: 5, ast: 4, stl: 1, blk: 0, tov: 2,
  fgm: 8, fga: 16, fg3m: 2, fg3a: 6, ftm: 3, fta: 4, plus_minus: -5,
})
const side = (team: Team, score: number, win: boolean, players: GameSide['players']): GameSide => ({
  team, score, win, elo_before: 1700, elo_after: win ? 1712 : 1688,
  totals: { fgm: 40, fga: 85, fg3m: 12, fg3a: 35, ftm: 11, fta: 14, reb: 44, ast: 25, stl: 7, blk: 5, tov: 12 },
  players,
})

const GAME: GameDetail = {
  game_id: '0022501230', date: '2026-04-12', season: 2025, postseason: false, neutral_site: false,
  home: side(OKC, 103, false, [line(1, 'Branden Carlson', 26), line(2, 'Nikola Topic', 18)]),
  away: side(PHX, 135, true, [line(3, 'Devin Booker', 31)]),
  prediction: { home_win_probability: 0.726, model_version: 'winprob_v3', correct: false },
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(GAME), { status: 200 })))
})
afterEach(() => vi.unstubAllGlobals())

describe('GameModal', () => {
  it('shows the final score, the model call and the box score', async () => {
    render(<GameModal gameId={GAME.game_id} onClose={vi.fn()} onOpenPlayer={vi.fn()} />)
    // The home score shows in the header and in the team-totals row of its box score.
    expect(await screen.findAllByText('103')).toHaveLength(2)
    expect(screen.getByText('135')).toBeInTheDocument()
    expect(screen.getByText(/model gave OKC 72.6% — upset/)).toBeInTheDocument()
    expect(screen.getByText('Branden Carlson')).toBeInTheDocument()
  })

  it("opens on the team you came from, and switches teams", async () => {
    render(<GameModal gameId={GAME.game_id} focusTeamId={PHX.id} onClose={vi.fn()} onOpenPlayer={vi.fn()} />)
    expect(await screen.findByText('Devin Booker')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: /OKC/ }))
    expect(screen.getByText('Branden Carlson')).toBeInTheDocument()
    expect(screen.queryByText('Devin Booker')).not.toBeInTheDocument()
  })

  it('opens a player and closes the popup', async () => {
    const onClose = vi.fn()
    const onOpenPlayer = vi.fn()
    render(<GameModal gameId={GAME.game_id} onClose={onClose} onOpenPlayer={onOpenPlayer} />)
    const row = (await screen.findByText('Nikola Topic')).closest('tr')!
    fireEvent.click(within(row).getByText('18'))
    expect(onOpenPlayer).toHaveBeenCalledWith(2)
    expect(onClose).toHaveBeenCalled()
  })

  it('closes with Escape, the X, or a click outside', async () => {
    const onClose = vi.fn()
    render(<GameModal gameId={GAME.game_id} onClose={onClose} onOpenPlayer={vi.fn()} />)
    await screen.findByText('Branden Carlson')
    fireEvent.keyDown(window, { key: 'Escape' })
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    fireEvent.mouseDown(screen.getByRole('dialog').parentElement!)
    expect(onClose).toHaveBeenCalledTimes(3)
  })
})
