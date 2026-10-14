import { useEffect, useMemo, useState } from 'react'
import { getTeamStats, getTeams, type Team, type TeamSeasonStats } from '../api'

export function TeamExplorer() {
  const [teams, setTeams] = useState<Team[]>([])
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [season, setSeason] = useState<number | ''>('')
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
    getTeamStats(selectedId, season === '' ? undefined : season)
      .then(setStats)
      .catch((e: Error) => {
        setStats(null)
        setError(e.message)
      })
      .finally(() => setLoading(false))
  }, [selectedId, season])

  return (
    <div className="panel split">
      <div className="team-list">
        <input
          type="text"
          placeholder="Search teams..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <ul>
          {filtered.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                className={t.id === selectedId ? 'team-row selected' : 'team-row'}
                onClick={() => setSelectedId(t.id)}
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
          <p className="hint">Select a team to see its season record.</p>
        ) : (
          <>
            <label className="season-input">
              Season
              <input
                type="number"
                placeholder="latest"
                value={season}
                onChange={(e) => setSeason(e.target.value === '' ? '' : Number(e.target.value))}
              />
            </label>
            {loading && <p className="hint">Loading...</p>}
            {error && <p className="error">{error}</p>}
            {stats && !loading && (
              <div className="stats-grid">
                <Stat label="Season" value={String(stats.season)} />
                <Stat label="Record" value={`${stats.wins}-${stats.losses}`} />
                <Stat label="Win %" value={`${(stats.win_pct * 100).toFixed(1)}%`} />
                <Stat
                  label="Avg Point Diff"
                  value={`${stats.avg_point_diff > 0 ? '+' : ''}${stats.avg_point_diff.toFixed(1)}`}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}
