import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import './App.css'
import { HowItWorks } from './HowItWorks'
import { Replay } from './Replay'
import { ResearchBanner } from './ResearchBanner'
import { Results } from './Results'
import { TooltipProvider } from './ui'
import type { Summary } from './types'

const TABS = [
  { id: 'how', label: 'How it works' },
  { id: 'replay', label: 'Patient replay' },
  { id: 'results', label: 'Results' },
] as const
type TabId = (typeof TABS)[number]['id']
type Theme = 'light' | 'dark'

function savedTheme(): Theme {
  try {
    return localStorage.getItem('sepsiscope-theme') === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

// Demo page: data comes from the local demo server on 127.0.0.1 (same origin).
function App() {
  const [tab, setTab] = useState<TabId>('how')
  const [theme, setTheme] = useState<Theme>(savedTheme)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  useEffect(() => {
    fetch('/api/summary')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((s: Summary) => setSummary(s))
      .catch(() => setError('Demo server not reachable. Start it with `uv run sepsiscope demo serve`.'))
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('sepsiscope-theme', theme)
    } catch {
      // storage may be unavailable; the theme still applies for this visit
    }
  }, [theme])

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
    <TooltipProvider>
      <ResearchBanner />
      <main className="page">
        <header className="top">
          <div>
            <h1>SepsiScope</h1>
            <p className="help big">An explainable early-warning model for sepsis in intensive care, tested on a hospital it never saw.</p>
          </div>
          <button type="button" className="btn" aria-pressed={theme === 'dark'} onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
            {theme === 'dark' ? '☀ Light mode' : '◐ ICU monitor mode'}
          </button>
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
        <footer className="footer">
          {summary && <p className="help">{summary.note}</p>}
          <p>
            <strong>Data:</strong> PhysioNet/CinC Challenge 2019 (CC BY 4.0). Please cite:
          </p>
          <ol className="citations">
            <li>
              Reyna M, et al. Early Prediction of Sepsis from Clinical Data: the PhysioNet/Computing in Cardiology Challenge 2019
              (version 1.0.0). PhysioNet (2019). doi:10.13026/v64v-d857
            </li>
            <li>
              Reyna MA, et al. Early Prediction of Sepsis From Clinical Data: The PhysioNet/Computing in Cardiology Challenge 2019.
              Critical Care Medicine 2020;48(2):210–217. doi:10.1097/CCM.0000000000004145
            </li>
            <li>Pollard et al. Nature Health (2026). doi:10.1038/s44360-026-00096-z</li>
          </ol>
        </footer>
      </main>
    </TooltipProvider>
  )
}

export default App
