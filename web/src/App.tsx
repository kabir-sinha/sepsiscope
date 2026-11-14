import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import './App.css'
import { HowItWorks } from './HowItWorks'
import { Replay } from './Replay'
import { ResearchBanner } from './ResearchBanner'
import { Results } from './Results'
import type { Summary } from './types'

const TABS = [
  { id: 'how', label: 'How it works' },
  { id: 'replay', label: 'Patient replay' },
  { id: 'results', label: 'Results' },
] as const
type TabId = (typeof TABS)[number]['id']

// Local demo: data comes from the demo API on 127.0.0.1 (proxied by Vite under /api).
function App() {
  const [tab, setTab] = useState<TabId>('how')
  const [summary, setSummary] = useState<Summary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  useEffect(() => {
    fetch('/api/summary')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((s: Summary) => setSummary(s))
      .catch(() => setError('Demo API not reachable. Start it with `uv run sepsiscope demo serve`.'))
  }, [])

  // Arrow keys move between tabs (WAI-ARIA tabs pattern).
  function onKey(e: KeyboardEvent<HTMLButtonElement>, i: number) {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    e.preventDefault()
    const next = (i + step + TABS.length) % TABS.length
    setTab(TABS[next].id)
    refs.current[next]?.focus()
  }

  return (
    <>
      <ResearchBanner />
      <main className="page">
        <header className="top">
          <h1>SepsiScope</h1>
          <p className="help big">
            An early-warning model for sepsis in intensive care, tested on a hospital it never saw.
          </p>
        </header>
        <div role="tablist" aria-label="Sections" className="tabs">
          {TABS.map((t, i) => (
            <button
              key={t.id}
              ref={(el) => {
                refs.current[i] = el
              }}
              id={`tab-${t.id}`}
              role="tab"
              type="button"
              aria-selected={tab === t.id}
              aria-controls={`panel-${t.id}`}
              tabIndex={tab === t.id ? 0 : -1}
              className={tab === t.id ? 'tab active' : 'tab'}
              onClick={() => setTab(t.id)}
              onKeyDown={(e) => onKey(e, i)}
            >
              {t.label}
            </button>
          ))}
        </div>
        {error && <p className="error">{error}</p>}
        <section id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="tabpanel">
          {tab === 'how' && <HowItWorks />}
          {tab === 'replay' && summary && <Replay summary={summary} />}
          {tab === 'results' && <Results />}
        </section>
        {summary && <p className="help small footer">{summary.note}</p>}
      </main>
    </>
  )
}

export default App
