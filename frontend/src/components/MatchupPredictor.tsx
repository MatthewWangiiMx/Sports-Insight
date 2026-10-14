import { useEffect, useState } from 'react'
import { getTeams, predictWinProb, type PredictResponse, type Team } from '../api'

export function MatchupPredictor() {
  const [teams, setTeams] = useState<Team[]>([])
  const [homeId, setHomeId] = useState<number | ''>('')
  const [awayId, setAwayId] = useState<number | ''>('')
  const [gameDate, setGameDate] = useState('')
  const [postseason, setPostseason] = useState(false)
  const [result, setResult] = useState<PredictResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getTeams()
      .then(setTeams)
      .catch((e: Error) => setError(e.message))
  }, [])

  const canPredict = homeId !== '' && awayId !== '' && homeId !== awayId

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
        <button type="button" disabled={!canPredict || loading} onClick={handlePredict}>
          {loading ? 'Predicting...' : 'Predict'}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="result">
          <div className="prob-bar">
            <div className="prob-segment home" style={{ width: `${result.home_win_probability * 100}%` }} />
            <div className="prob-segment away" style={{ width: `${result.away_win_probability * 100}%` }} />
          </div>
          <div className="prob-labels">
            <span>
              {result.home_team.abbreviation} {(result.home_win_probability * 100).toFixed(1)}%
            </span>
            <span>
              {result.away_team.abbreviation} {(result.away_win_probability * 100).toFixed(1)}%
            </span>
          </div>
          <p className="meta">
            Season {result.season} &middot; as of {result.as_of_date} &middot; model{' '}
            {result.model_version}
          </p>
        </div>
      )}
    </div>
  )
}
