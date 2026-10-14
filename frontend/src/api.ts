export interface Team {
  id: number
  full_name: string
  abbreviation: string
  conference: string
  division: string
}

export interface TeamSeasonStats {
  team_id: number
  season: number
  games_played: number
  wins: number
  losses: number
  win_pct: number
  avg_point_diff: number
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
