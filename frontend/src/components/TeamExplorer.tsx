import { useEffect, useMemo, useState } from 'react'
import { getTeamStats, getTeams, type Team, type TeamSeasonStats } from '../api'
import { SeasonPicker } from './SeasonPicker'
import { Skeleton } from './Skeleton'
import { Sparkline } from './Sparkline'

export function TeamExplorer() {
  const [teams, setTeams] = useState<Team[]>([])
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  // null = not yet resolved to a real season (first load picks the latest one,
  // then we lock that value in so the stepper always starts from a real number
  // instead of stepping off an empty/placeholder value).
  const [season, setSeason] = useState<number | null>(null)
  const [stats, setStats] = useState<TeamSeasonStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    getTeamStats(selectedId, season ?? undefined)
      .then((result) => {
        setStats(result)
        setSeason(result.season)
      })
      .catch((e: Error) => {
        setStats(null)
        setError(e.message)
      })
      .finally(() => setLoading(false))
  }, [selectedId, season])

  function selectTeam(id: number) {
    setSeason(null)
    setSelectedId(id)
  }

  return (
    <div className="panel split">
      <div className="team-list">
        <div className="search-box">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="7" cy="7" r="5.5" />
            <path d="M11.5 11.5 15 15" strokeLinecap="round" />
          </svg>
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
                <span className="abbr">{t.abbreviation}</span>
                <span>{t.full_name}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="team-detail">
        {selectedId == null ? (
          <div className="empty-state">
            <svg className="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
              <circle cx="12" cy="12" r="9.5" />
              <path d="M12 2.5v19M2.5 12h19" />
              <path d="M4.8 5.3c3 2.7 3 10.7 0 13.4M19.2 5.3c-3 2.7-3 10.7 0 13.4" />
            </svg>
            <p className="hint">Select a team to see its season record.</p>
          </div>
        ) : (
          <>
            <div className="season-row">
              <span className="stat-label">Season</span>
              <SeasonPicker season={season} onChange={setSeason} />
            </div>

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
                  <Stat label="Win %" value={`${(stats.win_pct * 100).toFixed(1)}%`} />
                  <Stat
                    label="Avg Point Diff"
                    value={`${stats.avg_point_diff > 0 ? '+' : ''}${stats.avg_point_diff.toFixed(1)}`}
                    tone={stats.avg_point_diff > 0 ? 'pos' : stats.avg_point_diff < 0 ? 'neg' : undefined}
                  />
                  <Stat label="Home" value={`${stats.home_wins}-${stats.home_losses}`} />
                  <Stat label="Away" value={`${stats.away_wins}-${stats.away_losses}`} />
                  <div className="stat">
                    <span className={`badge ${stats.current_streak.startsWith('W') ? 'win' : 'loss'}`}>
                      {stats.current_streak}
                    </span>
                    <span className="stat-label">Streak</span>
                  </div>
                </div>

                <div className="trend">
                  <span className="stat-label">Point differential, game by game</span>
                  <Sparkline
                    values={stats.game_log.map((g) => g.point_diff)}
                    wins={stats.game_log.map((g) => g.win)}
                  />
                </div>
              </>
            )}
          </>
        )}
      </div>
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
