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
  elo: number
}

export interface RankedStat {
  value: number
  rank: number
}

export type AdvancedStatKey =
  | 'ppg'
  | 'opp_ppg'
  | 'off_rtg'
  | 'def_rtg'
  | 'net_rtg'
  | 'pace'
  | 'efg'
  | 'opp_efg'
  | 'tov_pct'
  | 'oreb_pct'
  | 'ft_rate'

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
  elo: number
  advanced: Record<AdvancedStatKey, RankedStat>
  game_log: GameLogEntry[]
}

export interface StandingsRow {
  team: Team
  season: number
  wins: number
  losses: number
  win_pct: number
  elo: number
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

export interface PlayerSummary {
  id: number
  name: string
  team_abbreviation: string
  last_season: number
}

export interface PlayerAverages {
  games_played: number
  min: number
  pts: number
  reb: number
  ast: number
  stl: number
  blk: number
  tov: number
  fg3m: number
  fg_pct: number | null
  fg3_pct: number | null
  ft_pct: number | null
  plus_minus: number
  game_score: number
}

export interface PlayerGameLogEntry {
  date: string
  team_abbreviation: string
  opponent_abbreviation: string
  is_home: boolean
  win: boolean
  min: number
  pts: number
  reb: number
  ast: number
  stl: number
  blk: number
  fgm: number
  fga: number
  fg3m: number
  fg3a: number
  plus_minus: number
  game_score: number
}

export interface PlayerStats {
  player_id: number
  name: string
  season: number
  seasons: number[]
  teams: string[]
  averages: PlayerAverages
  game_log: PlayerGameLogEntry[]
}

export interface RosterEntry extends PlayerAverages {
  player_id: number
  name: string
}

export type LeaderStat = 'pts' | 'reb' | 'ast' | 'stl' | 'blk' | 'fg3m' | 'game_score'

export interface LeaderEntry {
  rank: number
  player_id: number
  name: string
  team_abbreviation: string
  games_played: number
  value: number
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

export function getRoster(teamId: number, season?: number): Promise<RosterEntry[]> {
  const qs = season != null ? `?season=${season}` : ''
  return request(`/teams/${teamId}/roster${qs}`)
}

export function getPlayers(): Promise<PlayerSummary[]> {
  return request('/players')
}

export function getPlayerStats(playerId: number, season?: number): Promise<PlayerStats> {
  const qs = season != null ? `?season=${season}` : ''
  return request(`/players/${playerId}/stats${qs}`)
}

export function getLeaders(stat: LeaderStat, season?: number, limit = 10): Promise<LeaderEntry[]> {
  const params = new URLSearchParams({ stat, limit: String(limit) })
  if (season != null) params.set('season', String(season))
  return request(`/leaders?${params}`)
}
