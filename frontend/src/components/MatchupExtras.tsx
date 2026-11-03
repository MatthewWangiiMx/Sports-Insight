import type { ModelInfo, StandingsRow, Team, TeamSeasonStats } from '../api'
import { matchupThemes } from '../branding'
import { num, pct, signed } from '../format'
import { TeamLogo } from './Logos'

const seasonLabel = (season: number) => `${season}-${String(season + 1).slice(-2)}`

// ---------------------------------------------------------------------------
// Tale of the tape: the two teams side by side before (and after) predicting.

interface TapeRow {
  label: string
  value: (s: TeamSeasonStats) => number
  format: (v: number) => string
  // A gap this big (or bigger) fills the bar entirely toward the better side.
  scale: number
  higherIsBetter: boolean
}

const TAPE_ROWS: TapeRow[] = [
  { label: 'Win %', value: (s) => s.win_pct, format: (v) => pct(v), scale: 0.3, higherIsBetter: true },
  { label: 'Elo rating', value: (s) => s.elo, format: (v) => num(v, 0), scale: 150, higherIsBetter: true },
  { label: 'Net rating', value: (s) => s.advanced.net_rtg.value, format: (v) => signed(v), scale: 8, higherIsBetter: true },
  { label: 'Offensive rating', value: (s) => s.advanced.off_rtg.value, format: (v) => num(v), scale: 6, higherIsBetter: true },
  { label: 'Defensive rating', value: (s) => s.advanced.def_rtg.value, format: (v) => num(v), scale: 6, higherIsBetter: false },
  { label: 'Effective FG%', value: (s) => s.advanced.efg.value, format: (v) => pct(v), scale: 0.04, higherIsBetter: true },
  { label: 'Avg point diff', value: (s) => s.avg_point_diff, format: (v) => signed(v), scale: 10, higherIsBetter: true },
]

interface TaleProps {
  home: Team
  away: Team
  homeStats: TeamSeasonStats
  awayStats: TeamSeasonStats
}

export function TaleOfTheTape({ home, away, homeStats, awayStats }: TaleProps) {
  const [homeTheme, awayTheme] = matchupThemes(home.abbreviation, away.abbreviation)
  return (
    <section className="panel tape">
      <div className="card-head">
        <h3>Tale of the tape</h3>
        <span className="hint-inline">{seasonLabel(homeStats.season)} regular season so far</span>
      </div>

      <div className="tape-teams">
        <TapeTeam team={home} stats={homeStats} />
        <TapeTeam team={away} stats={awayStats} alignRight />
      </div>

      <ul className="tape-rows">
        {TAPE_ROWS.map((row) => {
          const h = row.value(homeStats)
          const a = row.value(awayStats)
          // -1..1, positive = home is better on this stat.
          const raw = ((h - a) / row.scale) * (row.higherIsBetter ? 1 : -1)
          const edge = Math.max(-1, Math.min(1, raw))
          const homeShare = 50 + edge * 50
          return (
            <li key={row.label} className="tape-row">
              <span className={`tape-value ${edge > 0.02 ? 'better' : ''}`}>{row.format(h)}</span>
              <div className="tape-middle">
                <span className="tape-label">{row.label}</span>
                <div className="tape-bar">
                  <span className="tape-fill home" style={{ ...homeTheme, width: `${homeShare}%` }} />
                  <span className="tape-fill away" style={{ ...awayTheme, width: `${100 - homeShare}%` }} />
                </div>
              </div>
              <span className={`tape-value right ${edge < -0.02 ? 'better' : ''}`}>{row.format(a)}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function TapeTeam({ team, stats, alignRight }: { team: Team; stats: TeamSeasonStats; alignRight?: boolean }) {
  const lastFive = stats.game_log.slice(-5)
  return (
    <div className={`tape-team ${alignRight ? 'right' : ''}`}>
      <TeamLogo abbreviation={team.abbreviation} teamId={team.id} size={36} />
      <div className="tape-team-text">
        <span className="tape-team-name">{team.abbreviation}</span>
        <span className="form-dots" aria-label={`Last ${lastFive.length} games`}>
          {lastFive.map((g, i) => (
            <span key={i} className={`form-dot ${g.win ? 'win' : 'loss'}`} title={`${g.win ? 'W' : 'L'} vs ${g.opponent_abbreviation}`}>
              {g.win ? 'W' : 'L'}
            </span>
          ))}
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Marquee matchups: one-click picks among the top teams by Elo.

export function MarqueeMatchups({
  standings,
  onPick,
}: {
  standings: StandingsRow[]
  onPick: (homeId: number, awayId: number) => void
}) {
  const ranked = [...standings].sort((a, b) => b.elo - a.elo)
  if (ranked.length < 4) return null

  const pairs: [StandingsRow, StandingsRow, string][] = [
    [ranked[0], ranked[1], '#1 vs #2 by Elo'],
    [ranked[0], ranked[2], '#1 vs #3 by Elo'],
    [ranked[1], ranked[2], '#2 vs #3 by Elo'],
  ]
  // Best of the East vs best of the West - a Finals preview, if it isn't already listed.
  const bestEast = ranked.find((r) => r.team.conference === 'East')
  const bestWest = ranked.find((r) => r.team.conference === 'West')
  if (bestEast && bestWest) {
    const already = pairs.some(([x, y]) => new Set([x.team.id, y.team.id, bestEast.team.id, bestWest.team.id]).size === 2)
    pairs.push(already ? [ranked[0], ranked[3], '#1 vs #4 by Elo'] : [bestWest, bestEast, 'Finals preview'])
  }

  return (
    <section className="panel marquee">
      <div className="card-head">
        <h3>Marquee matchups</h3>
        <span className="hint-inline">tap one to fill in the teams</span>
      </div>
      <div className="marquee-grid">
        {pairs.map(([h, a, caption]) => (
          <button key={`${h.team.id}-${a.team.id}`} type="button" className="marquee-card" onClick={() => onPick(h.team.id, a.team.id)}>
            <span className="marquee-caption">{caption}</span>
            <span className="marquee-teams">
              <MarqueeSide row={h} />
              <span className="marquee-at">vs</span>
              <MarqueeSide row={a} />
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}

function MarqueeSide({ row }: { row: StandingsRow }) {
  return (
    <span className="marquee-side">
      <TeamLogo abbreviation={row.team.abbreviation} teamId={row.team.id} size={40} />
      <span className="marquee-abbr">{row.team.abbreviation}</span>
      <span className="marquee-elo">{num(row.elo, 0)}</span>
    </span>
  )
}

// ---------------------------------------------------------------------------
// Model card: what the predictor is, how accurate it's been, what it weighs.

export function ModelCard({ info }: { info: ModelInfo }) {
  const [from, to] = info.training_seasons
  const maxWeight = Math.max(...info.drivers.map((d) => d.weight))
  return (
    <section className="panel model-card">
      <div className="card-head">
        <h3>How the prediction works</h3>
      </div>

      <div className="model-stats">
        <div>
          <span className="model-big">{pct(info.test_accuracy)}</span>
          <span className="stat-label">winners picked</span>
        </div>
        <div>
          <span className="model-big">{info.test_auc.toFixed(2)}</span>
          <span className="stat-label">AUC</span>
        </div>
      </div>
      <p className="model-blurb">
        Tested on {info.test_games.toLocaleString()} games from {seasonLabel(info.test_season)} it never saw during
        training ({info.training_games.toLocaleString()} games, {seasonLabel(from)} to {seasonLabel(to)}).
      </p>

      <span className="stat-label">What it weighs most</span>
      <ul className="driver-list">
        {info.drivers
          .filter((d) => d.weight >= 0.03)
          .map((d) => (
            <li key={d.label}>
              <div className="driver-top">
                <span>{d.label}</span>
                <span className="driver-pct">{Math.round(d.weight * 100)}%</span>
              </div>
              <div className="factor-bar-track">
                <div className="factor-bar-fill home" style={{ width: `${(d.weight / maxWeight) * 100}%` }} />
              </div>
            </li>
          ))}
      </ul>
      <p className="hint-inline">
        Until both teams have played {info.min_games_for_model} games in a season, it falls back to Elo ratings alone.
      </p>
    </section>
  )
}
