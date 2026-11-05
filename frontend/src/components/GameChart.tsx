import { useLayoutEffect, useRef, useState } from 'react'
import type { GameLogEntry } from '../api'
import { num, signed } from '../format'
import { TeamLogo } from './Logos'

// "2026-11-02" -> "Nov 2". Built from the parts so the browser's time zone
// can't shift the date by a day.
export function shortDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function venue(game: GameLogEntry): string {
  if (game.neutral_site) return 'vs'
  return game.is_home ? 'vs' : '@'
}

interface GameChartProps {
  games: GameLogEntry[]
  // Jump to this game in the full games list.
  onOpenGame: (index: number) => void
  // Open a game's box score (clicking its bar).
  onSelectGame: (index: number) => void
}

/** Point differential per game as up/down bars. Each game gets a minimum
 *  width, so a long season scrolls sideways instead of getting cramped. */
export function GameChart({ games, onOpenGame, onSelectGame }: GameChartProps) {
  const [hovered, setHovered] = useState<number | null>(null)
  const [pinned, setPinned] = useState<number | null>(null)
  const scroller = useRef<HTMLDivElement>(null)

  // Open on the most recent games.
  useLayoutEffect(() => {
    if (scroller.current) scroller.current.scrollLeft = scroller.current.scrollWidth
  }, [games])

  if (games.length === 0) return null

  // Symmetric axis rounded up to a multiple of 10, so 0 sits in the middle.
  const maxAbs = Math.max(10, Math.ceil(Math.max(...games.map((g) => Math.abs(g.point_diff))) / 10) * 10)
  const ticks = [maxAbs, maxAbs / 2, 0, -maxAbs / 2, -maxAbs]
  const toPct = (v: number) => ((maxAbs - v) / (2 * maxAbs)) * 100 // top offset, in % of the plot height

  const active = hovered ?? pinned ?? games.length - 1
  const game = games[active]

  return (
    <div className="game-chart">
      <div className="chart-readout" aria-live="polite">
        <span className="readout-label">{hovered == null && pinned == null ? 'Latest game' : `Game ${active + 1}`}</span>
        <span className="readout-game">
          {shortDate(game.date)} &middot; {venue(game)}
          <TeamLogo abbreviation={game.opponent_abbreviation} teamId={game.opponent_id} size={18} />
          {game.opponent_abbreviation}
        </span>
        <span className={`badge small ${game.win ? 'win' : 'loss'}`}>{game.win ? 'W' : 'L'}</span>
        <span className="readout-score">
          {game.team_score}&ndash;{game.opp_score}{' '}
          <span className={game.point_diff > 0 ? 'pos' : 'neg'}>({signed(game.point_diff, 0)})</span>
        </span>
        <span className="readout-elo">Elo {num(game.elo, 0)}</span>
        <button type="button" className="link-button" onClick={() => onOpenGame(active)}>
          See in games list &rarr;
        </button>
      </div>

      <div className="chart-body">
        <div className="chart-axis" aria-hidden="true">
          {ticks.map((t) => (
            <span key={t} style={{ top: `${toPct(t)}%` }}>
              {t > 0 ? `+${t}` : t}
            </span>
          ))}
        </div>
        <div className="chart-scroll" ref={scroller} onMouseLeave={() => setHovered(null)}>
          <div className="chart-content">
            {ticks.map((t) => (
              <span key={t} className={`chart-grid ${t === 0 ? 'zero' : ''}`} style={{ top: `${toPct(t)}%` }} />
            ))}
            {games.map((g, i) => {
              const newMonth = i === 0 || g.date.slice(0, 7) !== games[i - 1].date.slice(0, 7)
              const height = (Math.abs(g.point_diff) / maxAbs) * 50
              return (
                <button
                  key={g.date}
                  type="button"
                  className={`chart-col ${i === active ? 'active' : ''}`}
                  aria-label={`${shortDate(g.date)} ${venue(g)} ${g.opponent_abbreviation}: ${g.win ? 'won' : 'lost'} ${g.team_score} to ${g.opp_score}`}
                  onMouseEnter={() => setHovered(i)}
                  onFocus={() => setHovered(i)}
                  onBlur={() => setHovered(null)}
                  onClick={() => {
                    setPinned(i)
                    onSelectGame(i)
                  }}
                >
                  <span
                    className={`chart-bar ${g.win ? 'win' : 'loss'}`}
                    style={g.point_diff >= 0 ? { bottom: '50%', height: `${height}%` } : { top: '50%', height: `${height}%` }}
                  />
                  {newMonth && <span className="chart-month">{shortDate(g.date).split(' ')[0]}</span>}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

/** Every game of the season, most recent first. `focus` (an index into
 *  `games`) is highlighted and scrolled into view - e.g. after clicking
 *  "See in games list" under the chart. */
interface GamesTableProps {
  games: GameLogEntry[]
  focus: number | null
  onSelectGame: (index: number) => void
}

export function GamesTable({ games, focus, onSelectGame }: GamesTableProps) {
  const scroller = useRef<HTMLDivElement>(null)
  const focusRow = useRef<HTMLTableRowElement>(null)

  // Scroll inside the table only - scrollIntoView would also move the page.
  useLayoutEffect(() => {
    const box = scroller.current
    const row = focusRow.current
    if (box && row) box.scrollTop = row.offsetTop - box.clientHeight / 2 + row.clientHeight / 2
  }, [focus])

  const rows = games.map((g, i) => ({ g, i, eloChange: i > 0 ? g.elo - games[i - 1].elo : null })).reverse()
  return (
    <div className="table-scroll tall" ref={scroller}>
      <table className="data-table games-table">
        <thead>
          <tr>
            <th>Date</th>
            <th className="name-cell">Opponent</th>
            <th>Result</th>
            <th>Score</th>
            <th>+/-</th>
            <th>Elo after</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ g, i, eloChange }) => (
            <tr
              key={g.date}
              ref={i === focus ? focusRow : undefined}
              className={`clickable ${i === focus ? 'focused' : ''}`}
              onClick={() => onSelectGame(i)}
            >
              <td>{shortDate(g.date)}</td>
              <td className="name-cell">
                <span className="team-inline">
                  <span className="opp-prefix">{venue(g)}</span>
                  <TeamLogo abbreviation={g.opponent_abbreviation} teamId={g.opponent_id} size={18} />
                  {g.opponent_abbreviation}
                  {g.neutral_site && <span className="hint-inline">neutral</span>}
                </span>
              </td>
              <td>
                <span className={`badge small ${g.win ? 'win' : 'loss'}`}>{g.win ? 'W' : 'L'}</span>
              </td>
              <td className="strong">
                {g.team_score}&ndash;{g.opp_score}
              </td>
              <td className={g.point_diff > 0 ? 'pos' : 'neg'}>{signed(g.point_diff, 0)}</td>
              <td>
                {num(g.elo, 0)}
                {eloChange != null && <span className={`elo-change ${eloChange >= 0 ? 'pos' : 'neg'}`}> {signed(eloChange, 0)}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
