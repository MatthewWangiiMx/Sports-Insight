import { useEffect, useMemo, useState } from 'react'
import {
  getLeaders,
  getPlayerStats,
  getPlayers,
  type LeaderEntry,
  type LeaderStat,
  type PlayerStats,
  type PlayerSummary,
} from '../api'
import { num, pct, signed } from '../format'
import { SeasonPicker } from './SeasonPicker'
import { Skeleton } from './Skeleton'
import { Sparkline } from './Sparkline'
import { SearchIcon } from './TeamExplorer'

// Long lists are slow to scan; show this many and let search do the rest.
const LIST_LIMIT = 100

interface PlayerExplorerProps {
  playerId: number | null
  onSelectPlayer: (playerId: number | null) => void
}

export function PlayerExplorer({ playerId, onSelectPlayer }: PlayerExplorerProps) {
  const [players, setPlayers] = useState<PlayerSummary[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPlayers()
      .then(setPlayers)
      .catch((e: Error) => setError(e.message))
  }, [])

  const matches = useMemo(() => {
    const q = search.trim().toLowerCase()
    return q ? players.filter((p) => p.name.toLowerCase().includes(q)) : players
  }, [players, search])

  return (
    <div className="panel split">
      <div className="team-list">
        <div className="search-box">
          <SearchIcon />
          <input
            type="text"
            placeholder={`Search ${players.length || ''} players...`}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {error && <p className="error">{error}</p>}
        <ul>
          {matches.slice(0, LIST_LIMIT).map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className={p.id === playerId ? 'team-row selected' : 'team-row'}
                onClick={() => onSelectPlayer(p.id)}
              >
                <span className="abbr">{p.team_abbreviation}</span>
                <span className="player-name">{p.name}</span>
              </button>
            </li>
          ))}
        </ul>
        {matches.length > LIST_LIMIT && (
          <p className="hint-inline list-note">
            Showing {LIST_LIMIT} of {matches.length} - search to narrow down.
          </p>
        )}
      </div>

      <div className="team-detail">
        {playerId == null ? (
          // The player list is sorted latest season first, so its head is the latest season.
          <LeadersBoard onSelectPlayer={onSelectPlayer} latestSeason={players[0]?.last_season} />
        ) : (
          <PlayerDetail key={playerId} playerId={playerId} onBack={() => onSelectPlayer(null)} />
        )}
      </div>
    </div>
  )
}

const LEADER_STATS: { key: LeaderStat; label: string }[] = [
  { key: 'pts', label: 'Points' },
  { key: 'reb', label: 'Rebounds' },
  { key: 'ast', label: 'Assists' },
  { key: 'stl', label: 'Steals' },
  { key: 'blk', label: 'Blocks' },
  { key: 'fg3m', label: '3PM' },
  { key: 'game_score', label: 'Game Score' },
]

function LeadersBoard({
  onSelectPlayer,
  latestSeason,
}: {
  onSelectPlayer: (id: number) => void
  latestSeason: number | undefined
}) {
  const [stat, setStat] = useState<LeaderStat>('pts')
  const [season, setSeason] = useState<number | null>(null)
  const [rows, setRows] = useState<LeaderEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getLeaders(stat, season ?? undefined, 15)
      .then(setRows)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [stat, season])

  const statLabel = LEADER_STATS.find((s) => s.key === stat)!.label

  return (
    <>
      <div className="detail-head">
        <h3>League leaders</h3>
        <SeasonPicker season={season ?? latestSeason ?? null} onChange={setSeason} max={latestSeason} />
      </div>
      <div className="chip-row">
        {LEADER_STATS.map((s) => (
          <button
            key={s.key}
            type="button"
            className={s.key === stat ? 'chip active' : 'chip'}
            onClick={() => setStat(s.key)}
          >
            {s.label}
          </button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Player</th>
              <th>Team</th>
              <th>GP</th>
              <th>{statLabel} / game</th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={5}>
                      <Skeleton height={14} />
                    </td>
                  </tr>
                ))
              : rows.map((r) => (
                  <tr key={r.player_id} className={r.rank === 1 ? 'clickable leader' : 'clickable'} onClick={() => onSelectPlayer(r.player_id)}>
                    <td className="rank-cell">{r.rank}</td>
                    <td className="name-cell">{r.name}</td>
                    <td>{r.team_abbreviation}</td>
                    <td>{r.games_played}</td>
                    <td className="strong">{num(r.value)}</td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
      <p className="hint-inline table-note">Regular season. Minimum games played: half of the season's most.</p>
    </>
  )
}

function PlayerDetail({ playerId, onBack }: { playerId: number; onBack: () => void }) {
  const [season, setSeason] = useState<number | null>(null)
  const [stats, setStats] = useState<PlayerStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getPlayerStats(playerId, season ?? undefined)
      .then(setStats)
      .catch((e: Error) => {
        setStats(null)
        setError(e.message)
      })
      .finally(() => setLoading(false))
  }, [playerId, season])

  const a = stats?.averages
  const log = stats ? [...stats.game_log].reverse() : []

  return (
    <>
      <button type="button" className="back-link" onClick={onBack}>
        &larr; League leaders
      </button>

      <div className="detail-head">
        <div>
          <h3>{stats?.name ?? <Skeleton width={180} height={20} />}</h3>
          {stats && <span className="hint-inline">{stats.teams.join(' → ')}{stats.teams.length > 1 && ' (traded mid-season)'}</span>}
        </div>
        {stats && stats.seasons.length > 1 && (
          <select className="season-select" value={stats.season} onChange={(e) => setSeason(Number(e.target.value))}>
            {[...stats.seasons].reverse().map((s) => (
              <option key={s} value={s}>
                {s}-{String(s + 1).slice(-2)}
              </option>
            ))}
          </select>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      {loading || !a ? (
        <div className="stats-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div className="stat" key={i}>
              <Skeleton height={21} width="60%" />
              <Skeleton height={11} width="40%" />
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="stats-grid">
            <Tile label="Points" value={num(a.pts)} />
            <Tile label="Rebounds" value={num(a.reb)} />
            <Tile label="Assists" value={num(a.ast)} />
            <Tile label="Steals / Blocks" value={`${num(a.stl)} / ${num(a.blk)}`} />
            <Tile label="Minutes" value={num(a.min)} />
            <Tile label="Games" value={String(a.games_played)} />
          </div>
          <div className="shooting-row">
            <ShootingStat label="FG%" value={a.fg_pct} />
            <ShootingStat label="3P%" value={a.fg3_pct} />
            <ShootingStat label="FT%" value={a.ft_pct} />
            <div className="shooting-stat">
              <span className={`stat-value small ${a.plus_minus > 0 ? 'pos' : a.plus_minus < 0 ? 'neg' : ''}`}>{signed(a.plus_minus)}</span>
              <span className="stat-label">+/- per game</span>
            </div>
          </div>

          <div className="trend">
            <span className="stat-label">Points, game by game (line = season average)</span>
            <Sparkline values={stats!.game_log.map((g) => g.pts)} wins={stats!.game_log.map((g) => g.win)} baseline={a.pts} />
          </div>

          <section className="section">
            <h4 className="section-title">Game log <span className="hint-inline">most recent first</span></h4>
            <div className="table-scroll tall">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Opp</th>
                    <th>Result</th>
                    <th>MIN</th>
                    <th>PTS</th>
                    <th>REB</th>
                    <th>AST</th>
                    <th>FG</th>
                    <th>3P</th>
                    <th>+/-</th>
                  </tr>
                </thead>
                <tbody>
                  {log.map((g) => (
                    <tr key={g.date}>
                      <td>{g.date.slice(5)}</td>
                      <td className="name-cell">{g.is_home ? 'vs' : '@'} {g.opponent_abbreviation}</td>
                      <td>
                        <span className={`badge small ${g.win ? 'win' : 'loss'}`}>{g.win ? 'W' : 'L'}</span>
                      </td>
                      <td>{g.min}</td>
                      <td className="strong">{g.pts}</td>
                      <td>{g.reb}</td>
                      <td>{g.ast}</td>
                      <td>{g.fgm}-{g.fga}</td>
                      <td>{g.fg3m}-{g.fg3a}</td>
                      <td>{signed(g.plus_minus, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </>
  )
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}

function ShootingStat({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="shooting-stat">
      <span className="stat-value small">{pct(value)}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}
