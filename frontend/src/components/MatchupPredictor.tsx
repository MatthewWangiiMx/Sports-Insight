import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import {
  getHeadToHead,
  getModelInfo,
  getStandings,
  getTeamStats,
  getTeams,
  predictWinProb,
  type HeadToHead,
  type ModelInfo,
  type PredictResponse,
  type StandingsRow,
  type Team,
  type TeamSeasonStats,
} from '../api'
import { matchupThemes } from '../branding'
import { num } from '../format'
import { TeamLogo } from './Logos'
import { MarqueeMatchups, ModelCard, TaleOfTheTape } from './MatchupExtras'
import { Skeleton } from './Skeleton'
import { BasketballIcon } from './TeamExplorer'

function InfoIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" />
      <path d="M8 7.2v4M8 4.8v.1" strokeLinecap="round" />
    </svg>
  )
}

function SwapIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M3 5.5h9.5M10 3l2.5 2.5L10 8M13 10.5H3.5M6 8l-2.5 2.5L6 13" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function MatchupPredictor() {
  const [teams, setTeams] = useState<Team[]>([])
  const [standings, setStandings] = useState<StandingsRow[]>([])
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null)
  const [homeId, setHomeId] = useState<number | ''>('')
  const [awayId, setAwayId] = useState<number | ''>('')
  const [gameDate, setGameDate] = useState('')
  const [postseason, setPostseason] = useState(false)
  const [result, setResult] = useState<PredictResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [h2h, setH2h] = useState<HeadToHead | null>(null)
  const [tape, setTape] = useState<[TeamSeasonStats, TeamSeasonStats] | null>(null)

  useEffect(() => {
    // Teams are essential; standings and the model card are extras - if they
    // fail, those sections just don't show.
    getTeams()
      .then(setTeams)
      .catch((e: Error) => setError(e.message))
    getStandings()
      .then(setStandings)
      .catch(() => setStandings([]))
    getModelInfo()
      .then(setModelInfo)
      .catch(() => setModelInfo(null))
  }, [])

  const canPredict = homeId !== '' && awayId !== '' && homeId !== awayId
  const standingById = useMemo(() => new Map(standings.map((r) => [r.team.id, r])), [standings])
  const homeTeam = teams.find((t) => t.id === homeId)
  const awayTeam = teams.find((t) => t.id === awayId)

  useEffect(() => {
    setH2h(null)
    setTape(null)
    if (!canPredict) return
    let current = true // ignore answers for a matchup that's no longer selected
    getHeadToHead(homeId as number, awayId as number)
      .then((r) => current && setH2h(r))
      .catch(() => {})
    Promise.all([getTeamStats(homeId as number), getTeamStats(awayId as number)])
      .then((pair) => current && setTape(pair))
      .catch(() => {})
    return () => {
      current = false
    }
  }, [homeId, awayId, canPredict])

  // Any change to the matchup makes a shown prediction stale.
  function pick(home: number | '', away: number | '') {
    setHomeId(home)
    setAwayId(away)
    setResult(null)
    setError(null)
  }

  async function handlePredict() {
    if (!canPredict) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await predictWinProb({
        home_team_id: homeId as number,
        away_team_id: awayId as number,
        game_date: gameDate || undefined,
        postseason,
      })
      setResult(res)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const toId = (value: string) => (value === '' ? '' : Number(value))
  // Shared by everything showing both teams, so clashing colors are swapped consistently.
  const [homeTheme, awayTheme] = matchupThemes(homeTeam?.abbreviation, awayTeam?.abbreviation)
  const [resultHomeTheme, resultAwayTheme] = matchupThemes(result?.home_team.abbreviation, result?.away_team.abbreviation)

  return (
    <div className="predict-page">
      <div className="panel predictor">
        <div className="stage">
          <TeamSlot
            side="Home"
            team={homeTeam}
            theme={homeTheme}
            teams={teams}
            value={homeId}
            onChange={(v) => pick(toId(v), awayId)}
            standing={homeTeam && standingById.get(homeTeam.id)}
            probability={result?.home_win_probability}
          />
          <div className="stage-middle">
            <span className="stage-vs">VS</span>
            <button
              type="button"
              className="swap-button"
              aria-label="Swap home and away"
              title="Swap home and away"
              disabled={homeId === '' && awayId === ''}
              onClick={() => pick(awayId, homeId)}
            >
              <SwapIcon />
            </button>
          </div>
          <TeamSlot
            side="Away"
            team={awayTeam}
            theme={awayTheme}
            teams={teams}
            value={awayId}
            onChange={(v) => pick(homeId, toId(v))}
            standing={awayTeam && standingById.get(awayTeam.id)}
            probability={result?.away_win_probability}
          />
        </div>

        {h2h && (
          <p className="h2h">
            All-time: {h2h.team_a.abbreviation} {h2h.team_a_wins}-{h2h.team_b_wins} {h2h.team_b.abbreviation}
            {h2h.last_meeting_date && (
              <>
                {' '}
                &middot; last met {h2h.last_meeting_date} (
                {h2h.last_meeting_winner_id === h2h.team_a.id ? h2h.team_a.abbreviation : h2h.team_b.abbreviation} won)
              </>
            )}
          </p>
        )}

        <div className="matchup-form">
          <div className="form-row">
            <label>
              Date <span className="hint-inline">(optional, defaults to our latest data)</span>
              <input
                type="date"
                value={gameDate}
                onChange={(e) => {
                  setGameDate(e.target.value)
                  setResult(null)
                }}
              />
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={postseason}
                onChange={(e) => {
                  setPostseason(e.target.checked)
                  setResult(null)
                }}
              />
              Postseason
            </label>
            <button type="button" className="predict-button" disabled={!canPredict || loading} onClick={handlePredict}>
              {loading ? 'Predicting…' : 'Predict'}
            </button>
          </div>
        </div>

        {error && <p className="error">{error}</p>}

        {loading && (
          <div className="result">
            <Skeleton height={40} className="skeleton-rounded" />
          </div>
        )}

        {result && !loading && (
          <div className="result">
            <div className="prob-bar">
              <div
                className="prob-segment home"
                style={{ ...resultHomeTheme, width: `${result.home_win_probability * 100}%` }}
              >
                {result.home_win_probability >= 0.12 &&
                  `${result.home_team.abbreviation} ${(result.home_win_probability * 100).toFixed(1)}%`}
              </div>
              <div
                className="prob-segment away"
                style={{ ...resultAwayTheme, width: `${result.away_win_probability * 100}%` }}
              >
                {result.away_win_probability >= 0.12 &&
                  `${result.away_team.abbreviation} ${(result.away_win_probability * 100).toFixed(1)}%`}
              </div>
            </div>
            {result.note && (
              <p className="note-callout">
                <InfoIcon />
                {result.note}
              </p>
            )}
            <p className="meta">
              Season {result.season} &middot; as of {result.as_of_date} &middot; model {result.model_version}
            </p>

            <div className="factors">
              <span className="stat-label">What's driving this prediction</span>
              <ul>
                {(() => {
                  const maxImpact = Math.max(...result.factors.map((f) => f.impact_pct), 0.01)
                  return result.factors.map((f) => (
                    <li
                      key={f.label}
                      className="factor-row team-colored"
                      // Tag and bar take the color of the team this factor favors.
                      style={f.favors === 'home' ? resultHomeTheme : resultAwayTheme}
                    >
                      <div className="factor-top">
                        <span className="factor-label">
                          <span className={`factor-side ${f.favors}`}>
                            {f.favors === 'home' ? result.home_team.abbreviation : result.away_team.abbreviation}
                          </span>
                          {f.label}
                        </span>
                        <span className="factor-impact">+{f.impact_pct.toFixed(1)}%</span>
                      </div>
                      <div className="factor-bar-track">
                        <div
                          className={`factor-bar-fill ${f.favors}`}
                          style={{ width: `${(f.impact_pct / maxImpact) * 100}%` }}
                        />
                      </div>
                    </li>
                  ))
                })()}
              </ul>
              <p className="hint-inline">
                Approximate, derived from the model's own coefficients - not an exact attribution.
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="predict-extras">
        {homeTeam && awayTeam && tape ? (
          <TaleOfTheTape home={homeTeam} away={awayTeam} homeStats={tape[0]} awayStats={tape[1]} />
        ) : (
          <MarqueeMatchups standings={standings} onPick={(h, a) => pick(h, a)} />
        )}
        {modelInfo && <ModelCard info={modelInfo} />}
      </div>
    </div>
  )
}

interface TeamSlotProps {
  side: 'Home' | 'Away'
  team: Team | undefined
  // Colors for this side - may be the team's alternate if the two teams' colors clash.
  theme: CSSProperties
  teams: Team[]
  value: number | ''
  onChange: (value: string) => void
  standing: StandingsRow | undefined
  probability: number | undefined
}

// One side of the matchup stage: logo (or a placeholder), the team picker, and
// a one-line summary - recolored in the team's colors once chosen.
function TeamSlot({ side, team, theme, teams, value, onChange, standing, probability }: TeamSlotProps) {
  return (
    <div
      className={`team-slot ${team ? 'filled' : ''} ${probability != null && probability >= 0.5 ? 'favored' : ''}`}
      style={team ? theme : undefined}
    >
      {team ? (
        <TeamLogo key={team.id} abbreviation={team.abbreviation} teamId={team.id} size={84} className="slot-logo" />
      ) : (
        <span className="slot-placeholder">
          <BasketballIcon />
        </span>
      )}
      <label className="slot-picker">
        <span className="hero-kicker">{side} team</span>
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">Choose a team...</option>
          {teams.map((t) => (
            <option key={t.id} value={t.id}>
              {t.full_name}
            </option>
          ))}
        </select>
      </label>
      <span className="slot-meta">
        {standing
          ? `${standing.wins}-${standing.losses} · Elo ${num(standing.elo, 0)} · ${standing.team.conference} #${standing.conference_rank}`
          : ' '}
      </span>
      {probability != null && <span className="slot-pct">{(probability * 100).toFixed(1)}%</span>}
    </div>
  )
}
