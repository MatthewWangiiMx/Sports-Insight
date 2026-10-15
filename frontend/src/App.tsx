import { useState } from 'react'
import { MatchupPredictor } from './components/MatchupPredictor'
import { Standings } from './components/Standings'
import { TeamExplorer } from './components/TeamExplorer'
import './App.css'

type Tab = 'predict' | 'teams' | 'standings'

const TABS: { id: Tab; label: string; title: string; description: string }[] = [
  {
    id: 'predict',
    label: 'Predict',
    title: 'Predict a matchup',
    description: 'Pick two teams and get a win probability from the trained model.',
  },
  {
    id: 'teams',
    label: 'Teams',
    title: 'Team explorer',
    description: 'Season record, home/away splits, and recent form by team.',
  },
  {
    id: 'standings',
    label: 'Standings',
    title: 'League standings',
    description: 'Regular-season rankings by conference.',
  },
]

function App() {
  const [tab, setTab] = useState<Tab>('predict')
  const active = TABS.find((t) => t.id === tab)!

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              SI
            </span>
            <h1>Sports Insight</h1>
          </div>
          <nav>
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={tab === t.id ? 'active' : ''}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="page">
        <div className="page-head">
          <h2>{active.title}</h2>
          <p className="page-desc">{active.description}</p>
        </div>
        <div className="page-content" key={tab}>
          {tab === 'predict' && <MatchupPredictor />}
          {tab === 'teams' && <TeamExplorer />}
          {tab === 'standings' && <Standings />}
        </div>
      </main>
    </div>
  )
}

export default App
