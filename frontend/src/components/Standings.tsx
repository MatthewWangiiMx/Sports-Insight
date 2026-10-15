import { useEffect, useState } from 'react'
import { getStandings, type StandingsRow } from '../api'
import { SeasonPicker } from './SeasonPicker'
import { Skeleton } from './Skeleton'

export function Standings() {
  const [rows, setRows] = useState<StandingsRow[]>([])
  // null = not yet resolved to a real season; see TeamExplorer for why.
  const [season, setSeason] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getStandings(season ?? undefined)
      .then((result) => {
        setRows(result)
        setSeason(result[0]?.season ?? season)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [season])

  const east = rows.filter((r) => r.team.conference === 'East').sort((a, b) => a.conference_rank - b.conference_rank)
  const west = rows.filter((r) => r.team.conference === 'West').sort((a, b) => a.conference_rank - b.conference_rank)

  return (
    <div className="panel">
      <div className="standings-header">
        <div className="season-row">
          <span className="stat-label">Season</span>
          <SeasonPicker season={season} onChange={setSeason} />
        </div>
        <span className="badge-pill">Regular season</span>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="standings-grid">
        <ConferenceTable title="Eastern Conference" rows={east} loading={loading} />
        <ConferenceTable title="Western Conference" rows={west} loading={loading} />
      </div>
    </div>
  )
}

function ConferenceTable({ title, rows, loading }: { title: string; rows: StandingsRow[]; loading: boolean }) {
  return (
    <div className="conference-table">
      <h3>{title}</h3>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Team</th>
            <th>W</th>
            <th>L</th>
            <th>Win%</th>
            <th>GB</th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 15 }).map((_, i) => (
                <tr key={i}>
                  <td colSpan={6}>
                    <Skeleton height={14} />
                  </td>
                </tr>
              ))
            : rows.map((r) => (
                <tr key={r.team.id} className={r.conference_rank === 1 ? 'leader' : ''}>
                  <td className="rank-cell">{r.conference_rank}</td>
                  <td className="team-cell">{r.team.full_name}</td>
                  <td>{r.wins}</td>
                  <td>{r.losses}</td>
                  <td className="win-pct">{(r.win_pct * 100).toFixed(1)}%</td>
                  <td>{r.games_behind === 0 ? '-' : r.games_behind.toFixed(1)}</td>
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  )
}
