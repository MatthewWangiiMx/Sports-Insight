import { useEffect, useState } from 'react'
import { getStandings, type StandingsRow } from '../api'
import { num, pct } from '../format'
import { SeasonPicker } from './SeasonPicker'
import { Skeleton } from './Skeleton'

type View = 'conference' | 'power'

export function Standings() {
  const [rows, setRows] = useState<StandingsRow[]>([])
  // null = "latest"; see TeamExplorer for why the picker shows the returned season.
  const [season, setSeason] = useState<number | null>(null)
  const [latestSeason, setLatestSeason] = useState<number | undefined>(undefined)
  const [view, setView] = useState<View>('conference')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getStandings(season ?? undefined)
      .then((result) => {
        setRows(result)
        if (season == null) setLatestSeason(result[0]?.season)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [season])

  const byConf = (conf: string) =>
    rows.filter((r) => r.team.conference === conf).sort((a, b) => a.conference_rank - b.conference_rank)
  const power = [...rows].sort((a, b) => b.elo - a.elo)

  return (
    <div className="panel">
      <div className="standings-header">
        <div className="season-row">
          <span className="stat-label">Season</span>
          <SeasonPicker season={season ?? rows[0]?.season ?? null} onChange={setSeason} max={latestSeason} />
        </div>
        <div className="segmented">
          <button type="button" className={view === 'conference' ? 'active' : ''} onClick={() => setView('conference')}>
            Conference
          </button>
          <button type="button" className={view === 'power' ? 'active' : ''} onClick={() => setView('power')}>
            Power rankings
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {view === 'conference' ? (
        <div className="standings-grid">
          <ConferenceTable title="Eastern Conference" rows={byConf('East')} loading={loading} />
          <ConferenceTable title="Western Conference" rows={byConf('West')} loading={loading} />
        </div>
      ) : (
        <div className="conference-table">
          <h3>
            Power rankings by Elo{' '}
            <span className="hint-inline">end-of-season rating, playoffs included - unlike the record, Elo weighs who you beat</span>
          </h3>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Team</th>
                <th>Elo</th>
                <th>W</th>
                <th>L</th>
                <th>Conf. rank</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? <SkeletonRows count={30} cols={6} />
                : power.map((r, i) => (
                    <tr key={r.team.id} className={i === 0 ? 'leader' : ''}>
                      <td className="rank-cell">{i + 1}</td>
                      <td className="team-cell">{r.team.full_name}</td>
                      <td className="win-pct">{num(r.elo, 0)}</td>
                      <td>{r.wins}</td>
                      <td>{r.losses}</td>
                      <td>
                        {r.team.conference} #{r.conference_rank}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="hint-inline table-note">W/L and conference rank are regular season only.</p>
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
            <th>Elo</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <SkeletonRows count={15} cols={7} />
          ) : (
            rows.map((r) => (
              <tr key={r.team.id} className={r.conference_rank === 1 ? 'leader' : ''}>
                <td className="rank-cell">{r.conference_rank}</td>
                <td className="team-cell">{r.team.full_name}</td>
                <td>{r.wins}</td>
                <td>{r.losses}</td>
                <td className="win-pct">{pct(r.win_pct)}</td>
                <td>{r.games_behind === 0 ? '-' : r.games_behind.toFixed(1)}</td>
                <td>{num(r.elo, 0)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

function SkeletonRows({ count, cols }: { count: number; cols: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <tr key={i}>
          <td colSpan={cols}>
            <Skeleton height={14} />
          </td>
        </tr>
      ))}
    </>
  )
}
