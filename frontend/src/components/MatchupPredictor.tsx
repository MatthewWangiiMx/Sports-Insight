import { useEffect, useState } from 'react'
import {
  getHeadToHead,
  getTeams,
  predictWinProb,
  type HeadToHead,
  type PredictResponse,
  type Team,
} from '../api'
import { teamTheme } from '../branding'
import { TeamLogo } from './Logos'
import { Skeleton } from './Skeleton'

export function MatchupPredictor() {
  const [teams, setTeams] = useState<Team[]>([])
  const [homeId, setHomeId] = useState<number | ''>('')
  const [awayId, setAwayId] = useState<number | ''>('')
  const [gameDate, setGameDate] = useState('')
  const [postseason, setPostseason] = useState(false)
  const [result, setResult] = useState<PredictResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [h2h, setH2h] = useState<HeadToHead | null>(null)

  useEffect(() => {
    getTeams()
      .then(setTeams)
      .catch((e: Error) => setError(e.message))
  }, [])

  const canPredict = homeId !== '' && awayId !== '' && homeId !== awayId

  useEffect(() => {
    setH2h(null)
    if (!canPredict) return
    getHeadToHead(homeId as number, awayId as number)
      .then(setH2h)
      .catch(() => setH2h(null))
  }, [homeId, awayId, canPredict])

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

  return (
    <div className="panel predictor">
      <div className="matchup-form">
        <div className="team-pickers">
          <label>
            Home team
            <select
              value={homeId}
              onChange={(e) => setHomeId(e.target.value === '' ? '' : Number(e.target.value))}
            >
              <option value="">Select...</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name}
                </option>
              ))}
            </select>
          </label>
          <span className="vs-divider">VS</span>
          <label>
            Away team
            <select
              value={awayId}
              onChange={(e) => setAwayId(e.target.value === '' ? '' : Number(e.target.value))}
            >
              <option value="">Select...</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="form-row">
          <label>
            Date <span className="hint-inline">(optional, defaults to our latest data)</span>
            <input type="date" value={gameDate} onChange={(e) => setGameDate(e.target.value)} />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={postseason}
              onChange={(e) => setPostseason(e.target.checked)}
            />
            Postseason
          </label>
        </div>
        <button type="button" disabled={!canPredict || loading} onClick={handlePredict}>
          {loading ? 'Predicting…' : 'Predict'}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

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

      {loading && (
        <div className="result">
          <Skeleton height={40} className="skeleton-rounded" />
        </div>
      )}

      {result && !loading && (
        <div className="result">
          <div className="faceoff">
            {[
              { team: result.home_team, p: result.home_win_probability, side: 'Home' },
              { team: result.away_team, p: result.away_win_probability, side: 'Away' },
            ].map(({ team, p, side }, i) => (
              <div
                key={team.id}
                className={`faceoff-team ${p >= 0.5 ? 'favored' : ''}`}
                style={teamTheme(team.abbreviation)}
              >
                <TeamLogo abbreviation={team.abbreviation} teamId={team.id} size={72} />
                <div className="faceoff-text">
                  <span className="hero-kicker">{side}</span>
                  <span className="faceoff-name">{team.full_name}</span>
                  <span className="faceoff-pct">{(p * 100).toFixed(1)}%</span>
                </div>
                {i === 0 && <span className="faceoff-vs">VS</span>}
              </div>
            ))}
          </div>
          <div className="prob-bar">
            <div
              className="prob-segment home"
              style={{ ...teamTheme(result.home_team.abbreviation), width: `${result.home_win_probability * 100}%` }}
            >
              {result.home_win_probability >= 0.12 &&
                `${result.home_team.abbreviation} ${(result.home_win_probability * 100).toFixed(1)}%`}
            </div>
            <div
              className="prob-segment away"
              style={{ ...teamTheme(result.away_team.abbreviation), width: `${result.away_win_probability * 100}%` }}
            >
              {result.away_win_probability >= 0.12 &&
                `${result.away_team.abbreviation} ${(result.away_win_probability * 100).toFixed(1)}%`}
            </div>
          </div>
          <p className="meta">
            Season {result.season} &middot; as of {result.as_of_date} &middot; model{' '}
            {result.model_version}
          </p>

          <div className="factors">
            <span className="stat-label">What's driving this prediction</span>
            <ul>
              {(() => {
                const maxImpact = Math.max(...result.factors.map((f) => f.impact_pct), 0.01)
                return result.factors.map((f) => (
                  <li key={f.label} className="factor-row">
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
  )
}
