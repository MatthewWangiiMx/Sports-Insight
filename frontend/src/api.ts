export interface Team {
  id: number
  full_name: string
  abbreviation: string
  conference: string
  division: string
}

export interface GameLogEntry {
  date: string
  opponent_abbreviation: string
  is_home: boolean
  win: boolean
  point_diff: number
}

export interface TeamSeasonStats {
  team_id: number
  season: number
  games_played: number
  wins: number
  losses: number
  win_pct: number
  avg_point_diff: number
  home_wins: number
  home_losses: number
  away_wins: number
  away_losses: number
  current_streak: string
  game_log: GameLogEntry[]
}

export interface StandingsRow {
  team: Team
  season: number
  wins: number
  losses: number
  win_pct: number
  conference_rank: number
  division_rank: number
  games_behind: number
}

export interface HeadToHead {
  team_a: Team
  team_b: Team
  team_a_wins: number
  team_b_wins: number
  games_played: number
  last_meeting_date: string | null
  last_meeting_winner_id: number | null
}

export interface PredictionFactor {
  label: string
  favors: 'home' | 'away'
  impact_pct: number
}

export interface PredictRequest {
  home_team_id: number
  away_team_id: number
  game_date?: string
  postseason?: boolean
}

export interface PredictResponse {
  home_team: Team
  away_team: Team
  home_win_probability: number
  away_win_probability: number
  as_of_date: string
  season: number
  model_version: string
  factors: PredictionFactor[]
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export function getTeams(): Promise<Team[]> {
  return request('/teams')
}

export function getTeamStats(teamId: number, season?: number): Promise<TeamSeasonStats> {
  const qs = season != null ? `?season=${season}` : ''
  return request(`/teams/${teamId}/stats${qs}`)
}

export function predictWinProb(body: PredictRequest): Promise<PredictResponse> {
  return request('/predict/winprob', { method: 'POST', body: JSON.stringify(body) })
}

export function getStandings(season?: number): Promise<StandingsRow[]> {
  const qs = season != null ? `?season=${season}` : ''
  return request(`/standings${qs}`)
}

export function getHeadToHead(teamAId: number, teamBId: number): Promise<HeadToHead> {
  return request(`/teams/${teamAId}/vs/${teamBId}`)
}
