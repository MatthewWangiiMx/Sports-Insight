import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { getGame, type GameDetail, type GameSide } from '../api'
import { matchupThemes } from '../branding'
import { num, signed } from '../format'
import { shortDate } from './GameChart'
import { Headshot, TeamLogo } from './Logos'
import { Skeleton } from './Skeleton'

interface GameModalProps {
  gameId: string
  // Which team's box score to show first (the page you came from).
  focusTeamId?: number
  onClose: () => void
  onOpenPlayer: (playerId: number) => void
}

/** Popup with one game's final score, the model's pre-game call, and both
 *  teams' box scores. Closes with the X, Escape, or a click outside. */
export function GameModal({ gameId, focusTeamId, onClose, onOpenPlayer }: GameModalProps) {
  const [game, setGame] = useState<GameDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [side, setSide] = useState<'home' | 'away' | null>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  // Latest onClose without re-running the setup below when the parent re-renders.
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    let current = true
    getGame(gameId)
      .then((g) => current && setGame(g))
      .catch((e: Error) => current && setError(e.message))
    return () => {
      current = false
    }
  }, [gameId])

  // Modal behavior: Escape closes, the page behind doesn't scroll, and focus
  // moves into the popup - then back to whatever opened it.
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    closeButton.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onCloseRef.current()
    window.addEventListener('keydown', onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      opener?.focus()
    }
  }, [])

  const shownSide = side ?? (game && focusTeamId === game.away.team.id ? 'away' : 'home')
  const [homeTheme, awayTheme] = matchupThemes(game?.home.team.abbreviation, game?.away.team.abbreviation)

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Game details">
        <button ref={closeButton} type="button" className="modal-close" aria-label="Close" onClick={onClose}>
          &times;
        </button>

        {error && <p className="error">{error}</p>}
        {!game && !error && (
          <div className="modal-loading">
            <Skeleton height={110} className="skeleton-rounded" />
            <Skeleton height={220} className="skeleton-rounded" />
          </div>
        )}

        {game && (
          <>
            <div className="game-header">
              <ScoreSide side={game.home} theme={homeTheme} />
              <div className="game-header-middle">
                <span className="hero-kicker">{game.postseason ? 'Playoffs · Final' : 'Final'}</span>
                <span className="game-date">{shortDate(game.date)}, {game.date.slice(0, 4)}</span>
                <span className="game-venue">
                  {game.neutral_site ? 'Neutral site' : `Home: ${game.home.team.abbreviation}`}
                </span>
              </div>
              <ScoreSide side={game.away} theme={awayTheme} alignRight />
            </div>

            <div className="game-facts">
              {game.prediction && (
                <span className={`game-fact ${game.prediction.correct ? 'good' : 'bad'}`}>
                  {(() => {
                    const p = game.prediction.home_win_probability
                    const fav = p >= 0.5 ? game.home : game.away
                    const pct = (Math.max(p, 1 - p) * 100).toFixed(1)
                    return `Pre-game: model gave ${fav.team.abbreviation} ${pct}% — ${game.prediction.correct ? 'called it' : 'upset'}`
                  })()}
                </span>
              )}
              {[game.home, game.away].map((s) => (
                <span key={s.team.id} className="game-fact">
                  {s.team.abbreviation} Elo {num(s.elo_before, 0)} &rarr; {num(s.elo_after, 0)}{' '}
                  <span className={s.elo_after >= s.elo_before ? 'pos' : 'neg'}>({signed(s.elo_after - s.elo_before, 0)})</span>
                </span>
              ))}
            </div>

            <div className="segmented box-tabs" role="tablist">
              {(['home', 'away'] as const).map((key) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={shownSide === key}
                  className={shownSide === key ? 'active' : ''}
                  onClick={() => setSide(key)}
                >
                  <TeamLogo abbreviation={game[key].team.abbreviation} teamId={game[key].team.id} size={18} />
                  {game[key].team.abbreviation}
                </button>
              ))}
            </div>

            <BoxScore
              side={game[shownSide]}
              onOpenPlayer={(id) => {
                onClose()
                onOpenPlayer(id)
              }}
            />
          </>
        )}
      </div>
    </div>
  )
}

function ScoreSide({ side, theme, alignRight }: { side: GameSide; theme: CSSProperties; alignRight?: boolean }) {
  return (
    <div className={`score-side ${alignRight ? 'right' : ''} ${side.win ? 'winner' : ''}`} style={theme}>
      <TeamLogo abbreviation={side.team.abbreviation} teamId={side.team.id} size={56} className="score-logo" />
      <div className="score-text">
        <span className="score-team">{side.team.full_name}</span>
        <span className="score-points">{side.score}</span>
      </div>
    </div>
  )
}

function BoxScore({ side, onOpenPlayer }: { side: GameSide; onOpenPlayer: (id: number) => void }) {
  const t = side.totals
  const pair = (made: number, att: number) => `${made}-${att}`
  return (
    <div className="table-scroll box-scroll">
      <table className="data-table box-table">
        <thead>
          <tr>
            <th>Player</th>
            <th>MIN</th>
            <th>PTS</th>
            <th>REB</th>
            <th>AST</th>
            <th>STL</th>
            <th>BLK</th>
            <th>TO</th>
            <th>FG</th>
            <th>3P</th>
            <th>FT</th>
            <th>+/-</th>
          </tr>
        </thead>
        <tbody>
          {side.players.map((p) => (
            <tr key={p.player_id} className="clickable" onClick={() => onOpenPlayer(p.player_id)}>
              <td className="name-cell">
                <span className="person">
                  <Headshot playerId={p.player_id} name={p.name} />
                  {p.name}
                </span>
              </td>
              <td>{p.min}</td>
              <td className="strong">{p.pts}</td>
              <td>{p.reb}</td>
              <td>{p.ast}</td>
              <td>{p.stl}</td>
              <td>{p.blk}</td>
              <td>{p.tov}</td>
              <td>{pair(p.fgm, p.fga)}</td>
              <td>{pair(p.fg3m, p.fg3a)}</td>
              <td>{pair(p.ftm, p.fta)}</td>
              <td className={p.plus_minus > 0 ? 'pos' : p.plus_minus < 0 ? 'neg' : ''}>{signed(p.plus_minus, 0)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>Team</td>
            <td />
            <td className="strong">{side.score}</td>
            <td>{t.reb}</td>
            <td>{t.ast}</td>
            <td>{t.stl}</td>
            <td>{t.blk}</td>
            <td>{t.tov}</td>
            <td>{pair(t.fgm, t.fga)}</td>
            <td>{pair(t.fg3m, t.fg3a)}</td>
            <td>{pair(t.ftm, t.fta)}</td>
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
