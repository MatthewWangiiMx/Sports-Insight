import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PredictResponse, Team } from '../api'
import { MatchupPredictor } from './MatchupPredictor'

const OKC: Team = { id: 1610612760, full_name: 'Oklahoma City Thunder', abbreviation: 'OKC', conference: 'West', division: 'Northwest' }
const NYK: Team = { id: 1610612752, full_name: 'New York Knicks', abbreviation: 'NYK', conference: 'East', division: 'Atlantic' }

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
  if (url.endsWith('/teams')) return json([OKC, NYK])
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
})
