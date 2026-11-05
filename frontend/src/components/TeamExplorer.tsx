import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  getRoster,
  getTeamStats,
  getTeams,
  type AdvancedStatKey,
  type RosterEntry,
  type Team,
  type TeamSeasonStats,
} from '../api'
import { teamTheme } from '../branding'
import { num, pct, rankTone, signed } from '../format'
import { Headshot, TeamLogo } from './Logos'
import { GameChart, GamesTable } from './GameChart'
import { GameModal } from './GameModal'
import { SeasonPicker } from './SeasonPicker'
import { Skeleton } from './Skeleton'

const ADVANCED_GROUPS: { title: string; stats: { key: AdvancedStatKey; label: string; format: (v: number) => string }[] }[] = [
  {
    title: 'Ratings',
    stats: [
      { key: 'off_rtg', label: 'Offensive rating', format: (v) => num(v) },
      { key: 'def_rtg', label: 'Defensive rating', format: (v) => num(v) },
      { key: 'net_rtg', label: 'Net rating', format: (v) => signed(v) },
      { key: 'pace', label: 'Pace', format: (v) => num(v) },
    ],
  },
  {
    title: 'Four Factors',
    stats: [
      { key: 'efg', label: 'Effective FG%', format: (v) => pct(v) },
      { key: 'tov_pct', label: 'Turnover rate', format: (v) => pct(v) },
      { key: 'oreb_pct', label: 'Off. rebound rate', format: (v) => pct(v) },
      { key: 'ft_rate', label: 'Free throw rate', format: (v) => pct(v) },
    ],
  },
  {
    title: 'Scoring',
    stats: [
      { key: 'ppg', label: 'Points / game', format: (v) => num(v) },
      { key: 'opp_ppg', label: 'Allowed / game', format: (v) => num(v) },
      { key: 'opp_efg', label: 'Opp. effective FG%', format: (v) => pct(v) },
    ],
  },
]

export function TeamExplorer({ onOpenPlayer }: { onOpenPlayer: (playerId: number) => void }) {
  const [teams, setTeams] = useState<Team[]>([])
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  // null = "latest" (the API picks it). The picker shows the season the API
  // actually returned, so the stepper always steps from a real number instead
  // of an empty/placeholder value.
  const [season, setSeason] = useState<number | null>(null)
  const [latestSeason, setLatestSeason] = useState<number | undefined>(undefined)
  const [stats, setStats] = useState<TeamSeasonStats | null>(null)
  const [roster, setRoster] = useState<RosterEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // The bottom section shows either the roster or the season's games.
  const [lowerView, setLowerView] = useState<'roster' | 'games'>('roster')
  const [focusGame, setFocusGame] = useState<number | null>(null)
  // Game whose box score popup is open.
  const [openGameId, setOpenGameId] = useState<string | null>(null)
  const lowerSection = useRef<HTMLElement>(null)
  const closeGame = useCallback(() => setOpenGameId(null), [])

  useEffect(() => {
    getTeams()
      .then(setTeams)
      .catch((e: Error) => setError(e.message))
  }, [])

  const filtered = useMemo(
    () => teams.filter((t) => t.full_name.toLowerCase().includes(search.toLowerCase())),
    [teams, search],
  )

  useEffect(() => {
    if (selectedId == null) return
    setLoading(true)
    setError(null)
    setFocusGame(null)
    Promise.all([getTeamStats(selectedId, season ?? undefined), getRoster(selectedId, season ?? undefined)])
      .then(([teamStats, teamRoster]) => {
        setStats(teamStats)
        setRoster(teamRoster)
        if (season == null) setLatestSeason(teamStats.season)
      })
      .catch((e: Error) => {
        setStats(null)
        setRoster([])
        setError(e.message)
      })
      .finally(() => setLoading(false))
  }, [selectedId, season])

  function selectTeam(id: number) {
    setSeason(null)
    setSelectedId(id)
  }

  const selectedTeam = teams.find((t) => t.id === selectedId)

  return (
    <div className="panel split">
      <div className="team-list">
        <div className="search-box">
          <SearchIcon />
          <input
            type="text"
            placeholder="Search teams..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <ul>
          {filtered.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                className={t.id === selectedId ? 'team-row selected' : 'team-row'}
                onClick={() => selectTeam(t.id)}
              >
                <TeamLogo abbreviation={t.abbreviation} teamId={t.id} size={24} />
                <span>{t.full_name}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="team-detail themed" style={teamTheme(selectedTeam?.abbreviation)}>
        {selectedId == null ? (
          <TeamGrid teams={teams} onSelect={selectTeam} />
        ) : (
          <>
            {selectedTeam && (
              <div className="hero" key={selectedTeam.id}>
                <TeamLogo abbreviation={selectedTeam.abbreviation} teamId={selectedTeam.id} size={260} className="hero-watermark" />
                <div className="hero-media">
                  <TeamLogo abbreviation={selectedTeam.abbreviation} teamId={selectedTeam.id} size={84} />
                </div>
                <div className="hero-text">
                  <span className="hero-kicker">
                    {selectedTeam.conference} &middot; {selectedTeam.division}
                  </span>
                  <h3>{selectedTeam.full_name}</h3>
                  <span className="hero-sub">
                    {stats && !loading ? `${stats.wins}-${stats.losses} · Elo ${num(stats.elo, 0)}` : ' '}
                  </span>
                </div>
                <div className="hero-actions">
                  <SeasonPicker season={season ?? stats?.season ?? null} onChange={setSeason} max={latestSeason} />
                </div>
              </div>
            )}

            {error && <p className="error">{error}</p>}

            {loading && (
              <div className="stats-grid">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div className="stat" key={i}>
                    <Skeleton height={21} width="60%" />
                    <Skeleton height={11} width="40%" />
                  </div>
                ))}
              </div>
            )}

            {stats && !loading && (
              <>
                <div className="stats-grid">
                  <Stat label="Record" value={`${stats.wins}-${stats.losses}`} />
                  <Stat label="Win %" value={pct(stats.win_pct)} />
                  <Stat label="Elo" value={num(stats.elo, 0)} />
                  <Stat
                    label="Avg Point Diff"
                    value={signed(stats.avg_point_diff)}
                    tone={stats.avg_point_diff > 0 ? 'pos' : stats.avg_point_diff < 0 ? 'neg' : undefined}
                  />
                  <Stat label="Home / Away" value={`${stats.home_wins}-${stats.home_losses} / ${stats.away_wins}-${stats.away_losses}`} />
                  <div className="stat">
                    <span className={`badge ${stats.current_streak.startsWith('W') ? 'win' : 'loss'}`}>
                      {stats.current_streak}
                    </span>
                    <span className="stat-label">Streak</span>
                  </div>
                </div>

                <section className="section">
                  <h4 className="section-title">
                    Point differential, game by game <span className="hint-inline">hover a bar for details, click it for the box score</span>
                  </h4>
                  <GameChart
                    key={`${stats.team_id}-${stats.season}`}
                    games={stats.game_log}
                    onOpenGame={(i) => {
                      setLowerView('games')
                      setFocusGame(i)
                      // After the list renders, bring it into view.
                      requestAnimationFrame(() => lowerSection.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
                    }}
                    onSelectGame={(i) => setOpenGameId(stats.game_log[i].game_id)}
                  />
                </section>

                <section className="section">
                  <h4 className="section-title">Advanced <span className="hint-inline">league rank in pill</span></h4>
                  <div className="advanced-grid">
                    {ADVANCED_GROUPS.map((group) => (
                      <div key={group.title} className="advanced-group">
                        <span className="stat-label">{group.title}</span>
                        {group.stats.map(({ key, label, format }) => {
                          const s = stats.advanced[key]
                          return (
                            <div key={key} className="advanced-row">
                              <span className="advanced-label">{label}</span>
                              <span className="advanced-value">{format(s.value)}</span>
                              <span className={`rank-pill ${rankTone(s.rank)}`}>#{s.rank}</span>
                            </div>
                          )
                        })}
                      </div>
                    ))}
                  </div>
                </section>

                <section className="section" ref={lowerSection}>
                  <div className="section-head">
                    <div className="segmented" role="tablist">
                      <button type="button" role="tab" aria-selected={lowerView === 'roster'} className={lowerView === 'roster' ? 'active' : ''} onClick={() => setLowerView('roster')}>
                        Roster
                      </button>
                      <button type="button" role="tab" aria-selected={lowerView === 'games'} className={lowerView === 'games' ? 'active' : ''} onClick={() => setLowerView('games')}>
                        Games
                      </button>
                    </div>
                    <span className="hint-inline">
                      {lowerView === 'roster' ? 'per game, this team only' : `${stats.game_log.length} regular-season games · click one for the box score`}
                    </span>
                  </div>
                  {lowerView === 'games' ? (
                    <GamesTable
                      games={stats.game_log}
                      focus={focusGame}
                      onSelectGame={(i) => setOpenGameId(stats.game_log[i].game_id)}
                    />
                  ) : (
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Player</th>
                          <th>GP</th>
                          <th>MIN</th>
                          <th>PTS</th>
                          <th>REB</th>
                          <th>AST</th>
                          <th>FG%</th>
                          <th>3P%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {roster.map((p) => (
                          <tr key={p.player_id} className="clickable" onClick={() => onOpenPlayer(p.player_id)}>
                            <td className="name-cell">
                              <span className="person">
                                <Headshot playerId={p.player_id} name={p.name} />
                                {p.name}
                              </span>
                            </td>
                            <td>{p.games_played}</td>
                            <td>{num(p.min)}</td>
                            <td className="strong">{num(p.pts)}</td>
                            <td>{num(p.reb)}</td>
                            <td>{num(p.ast)}</td>
                            <td>{pct(p.fg_pct)}</td>
                            <td>{pct(p.fg3_pct)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  )}
                </section>
              </>
            )}
          </>
        )}
      </div>

      {openGameId && (
        <GameModal gameId={openGameId} focusTeamId={selectedId ?? undefined} onClose={closeGame} onOpenPlayer={onOpenPlayer} />
      )}
    </div>
  )
}

// Shown before a team is picked: every team's logo, by conference, one click away.
function TeamGrid({ teams, onSelect }: { teams: Team[]; onSelect: (id: number) => void }) {
  if (teams.length === 0) {
    return (
      <div className="empty-state">
        <BasketballIcon />
        <p className="hint">Loading teams...</p>
      </div>
    )
  }
  return (
    <div className="team-grid-wrap">
      <p className="hint">Pick a team for its record, Elo trend, advanced stats and roster.</p>
      {['East', 'West'].map((conf) => (
        <section key={conf} className="team-grid-section">
          <h4 className="section-title">{conf === 'East' ? 'Eastern' : 'Western'} Conference</h4>
          <div className="team-grid">
            {teams
              .filter((t) => t.conference === conf)
              .map((t) => (
                <button key={t.id} type="button" className="team-tile" style={teamTheme(t.abbreviation)} onClick={() => onSelect(t.id)}>
                  <TeamLogo abbreviation={t.abbreviation} teamId={t.id} size={44} />
                  <span className="team-tile-name">{t.full_name.split(' ').slice(-1)[0]}</span>
                </button>
              ))}
          </div>
        </section>
      ))}
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'pos' | 'neg' }) {
  return (
    <div className="stat">
      <span className={tone ? `stat-value ${tone}` : 'stat-value'}>{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}

export function SearchIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="7" cy="7" r="5.5" />
      <path d="M11.5 11.5 15 15" strokeLinecap="round" />
    </svg>
  )
}

export function BasketballIcon() {
  return (
    <svg className="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
      <circle cx="12" cy="12" r="9.5" />
      <path d="M12 2.5v19M2.5 12h19" />
      <path d="M4.8 5.3c3 2.7 3 10.7 0 13.4M19.2 5.3c-3 2.7-3 10.7 0 13.4" />
    </svg>
  )
}
