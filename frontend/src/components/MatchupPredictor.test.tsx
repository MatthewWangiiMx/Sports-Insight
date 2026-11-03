import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ModelInfo, PredictResponse, StandingsRow, Team, TeamSeasonStats } from '../api'
import { MatchupPredictor } from './MatchupPredictor'

const OKC: Team = { id: 1610612760, full_name: 'Oklahoma City Thunder', abbreviation: 'OKC', conference: 'West', division: 'Northwest' }
const NYK: Team = { id: 1610612752, full_name: 'New York Knicks', abbreviation: 'NYK', conference: 'East', division: 'Atlantic' }
const BOS: Team = { id: 1610612738, full_name: 'Boston Celtics', abbreviation: 'BOS', conference: 'East', division: 'Atlantic' }
const DEN: Team = { id: 1610612743, full_name: 'Denver Nuggets', abbreviation: 'DEN', conference: 'West', division: 'Northwest' }
const TEAMS = [OKC, NYK, BOS, DEN]
const ELO: Record<number, number> = { [OKC.id]: 1750, [NYK.id]: 1700, [BOS.id]: 1650, [DEN.id]: 1600 }

const STANDINGS: StandingsRow[] = TEAMS.map((team, i) => ({
  team, season: 2026, wins: 8 - i, losses: i, win_pct: (8 - i) / 8, elo: ELO[team.id],
  conference_rank: i < 2 ? 1 : 2, division_rank: 1, games_behind: 0,
}))

function stats(team: Team, netRtg: number): TeamSeasonStats {
  const ranked = (value: number) => ({ value, rank: 1 })
  return {
    team_id: team.id, season: 2026, games_played: 8, wins: 6, losses: 2, win_pct: 0.75, avg_point_diff: netRtg / 2,
    home_wins: 3, home_losses: 1, away_wins: 3, away_losses: 1, current_streak: 'W2', elo: ELO[team.id],
    advanced: {
      ppg: ranked(115), opp_ppg: ranked(108), off_rtg: ranked(118), def_rtg: ranked(118 - netRtg), net_rtg: ranked(netRtg),
      pace: ranked(99), efg: ranked(0.56), opp_efg: ranked(0.52), tov_pct: ranked(0.12), oreb_pct: ranked(0.27), ft_rate: ranked(0.2),
    },
    game_log: [true, true, false, true, true].map((win, i) => ({
      date: `2026-10-2${i}`, opponent_abbreviation: 'BOS', is_home: true, win, point_diff: win ? 5 : -5, elo: ELO[team.id],
    })),
  }
}

const MODEL: ModelInfo = {
  version: 'winprob_v3', test_accuracy: 0.693, test_auc: 0.743, test_games: 1268, test_season: 2025,
  training_games: 9825, training_seasons: [2016, 2023], min_games_for_model: 3,
  drivers: [
    { label: 'Elo rating', weight: 0.37 },
    { label: 'Recent form (last 5 & 10 games)', weight: 0.24 },
  ],
}

const PREDICTION: PredictResponse = {
  home_team: OKC,
  away_team: NYK,
  home_win_probability: 0.6328,
  away_win_probability: 0.3672,
  as_of_date: '2026-10-24',
  season: 2026,
  model_version: 'elo_early_season',
  factors: [
    { label: 'Home court advantage', favors: 'home', impact_pct: 14.0 },
    { label: 'Elo rating edge', favors: 'away', impact_pct: 0.7 },
  ],
  note: 'Early-season estimate: uses Elo ratings alone.',
}

// Stands in for the backend: answers by URL, records what was asked.
const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
  const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 })
  if (url.endsWith('/teams')) return json(TEAMS)
  if (url.endsWith('/standings')) return json(STANDINGS)
  if (url.endsWith('/model')) return json(MODEL)
  const statsMatch = url.match(/\/teams\/(\d+)\/stats$/)
  if (statsMatch) return json(stats(TEAMS.find((t) => t.id === Number(statsMatch[1]))!, Number(statsMatch[1]) === OKC.id ? 12 : 4))
  if (url.includes('/vs/')) {
    return json({ team_a: OKC, team_b: NYK, team_a_wins: 5, team_b_wins: 3, games_played: 8, last_meeting_date: null, last_meeting_winner_id: null })
  }
  if (url.endsWith('/predict/winprob') && init?.method === 'POST') return json(PREDICTION)
  return new Response(JSON.stringify({ detail: 'not found' }), { status: 404 })
})

beforeEach(() => {
  fetchMock.mockClear()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => vi.unstubAllGlobals())

async function pickTeams(home: Team, away: Team) {
  // Wait for the team list to load into the dropdowns.
  await screen.findAllByRole('option', { name: home.full_name })
  fireEvent.change(screen.getByLabelText(/Home team/), { target: { value: String(home.id) } })
  fireEvent.change(screen.getByLabelText(/Away team/), { target: { value: String(away.id) } })
}

describe('MatchupPredictor', () => {
  it('only allows predicting two different teams', async () => {
    render(<MatchupPredictor />)
    const button = screen.getByRole('button', { name: 'Predict' })
    expect(button).toBeDisabled()
    await pickTeams(OKC, OKC)
    expect(button).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/Away team/), { target: { value: String(NYK.id) } })
    expect(button).toBeEnabled()
  })

  it('sends the matchup and shows the result, factors and note', async () => {
    render(<MatchupPredictor />)
    await pickTeams(OKC, NYK)
    expect(await screen.findByText(/All-time: OKC 5-3 NYK/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Predict' }))

    expect(await screen.findByText('63.3%')).toBeInTheDocument()
    expect(screen.getByText('36.7%')).toBeInTheDocument()
    expect(screen.getByText('Home court advantage')).toBeInTheDocument()
    expect(screen.getByText(PREDICTION.note!)).toBeInTheDocument()

    const [, init] = fetchMock.mock.calls.find(([url]) => url.endsWith('/predict/winprob'))!
    expect(JSON.parse(init!.body as string)).toMatchObject({ home_team_id: OKC.id, away_team_id: NYK.id, postseason: false })
  })

  it('shows the error message from the API', async () => {
    fetchMock.mockImplementationOnce(async () => new Response(JSON.stringify({ detail: 'API is down' }), { status: 503 }))
    render(<MatchupPredictor />)
    expect(await screen.findByText('API is down')).toBeInTheDocument()
  })

  it('fills both teams from a marquee matchup', async () => {
    render(<MatchupPredictor />)
    fireEvent.click(await screen.findByRole('button', { name: /#1 vs #2 by Elo/ }))
    expect(screen.getByLabelText(/Home team/)).toHaveValue(String(OKC.id))
    expect(screen.getByLabelText(/Away team/)).toHaveValue(String(NYK.id))
  })

  it('swaps home and away', async () => {
    render(<MatchupPredictor />)
    await pickTeams(OKC, NYK)
    fireEvent.click(screen.getByRole('button', { name: 'Swap home and away' }))
    expect(screen.getByLabelText(/Home team/)).toHaveValue(String(NYK.id))
    expect(screen.getByLabelText(/Away team/)).toHaveValue(String(OKC.id))
  })

  it('compares the two teams once both are picked', async () => {
    render(<MatchupPredictor />)
    await pickTeams(OKC, NYK)
    expect(await screen.findByText('Tale of the tape')).toBeInTheDocument()
    // Net rating: OKC +12.0 vs NYK +4.0 - the better side is highlighted.
    expect(screen.getByText('+12.0')).toHaveClass('better')
    expect(screen.getByText('+4.0')).not.toHaveClass('better')
    // Marquee matchups make way for the comparison.
    expect(screen.queryByText('Marquee matchups')).not.toBeInTheDocument()
  })

  it('shows the model card', async () => {
    render(<MatchupPredictor />)
    expect(await screen.findByText('How the prediction works')).toBeInTheDocument()
    expect(screen.getByText('69.3%')).toBeInTheDocument()
    expect(screen.getByText('Elo rating')).toBeInTheDocument()
  })

  it('clears a shown prediction when the matchup changes', async () => {
    render(<MatchupPredictor />)
    await pickTeams(OKC, NYK)
    fireEvent.click(screen.getByRole('button', { name: 'Predict' }))
    expect(await screen.findByText('63.3%')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/Away team/), { target: { value: String(BOS.id) } })
    expect(screen.queryByText('63.3%')).not.toBeInTheDocument()
  })
})
