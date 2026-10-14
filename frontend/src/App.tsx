import { useState } from 'react'
import { MatchupPredictor } from './components/MatchupPredictor'
import { TeamExplorer } from './components/TeamExplorer'
import './App.css'

type Tab = 'predict' | 'teams'

function App() {
  const [tab, setTab] = useState<Tab>('predict')

  return (
    <div className="app">
      <header>
        <h1>Sports Insight</h1>
        <nav>
          <button
            type="button"
            className={tab === 'predict' ? 'active' : ''}
            onClick={() => setTab('predict')}
          >
            Predict Matchup
          </button>
          <button
            type="button"
            className={tab === 'teams' ? 'active' : ''}
            onClick={() => setTab('teams')}
          >
            Teams
          </button>
        </nav>
      </header>
      <main>{tab === 'predict' ? <MatchupPredictor /> : <TeamExplorer />}</main>
    </div>
  )
}

export default App
