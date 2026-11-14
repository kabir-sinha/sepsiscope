import { useEffect, useState } from 'react'
import './App.css'
import { ResearchBanner } from './ResearchBanner'
import { Timeline } from './Timeline'
import type { Patient, Summary } from './types'

// Local demo: data comes from the demo API on 127.0.0.1 (proxied by Vite under /api).
function App() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [patient, setPatient] = useState<Patient | null>(null)
  const [hour, setHour] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/summary')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((s: Summary) => setSummary(s))
      .catch(() => setError('Demo API not reachable. Start it with `sepsiscope demo serve`.'))
  }, [])

  function open(key: string) {
    fetch(`/api/patients/${key}`)
      .then((r) => r.json())
      .then((p: Patient) => {
        setPatient(p)
        setHour(p.alert_hours.length ? p.alert_hours[0] : null)
      })
      .catch(() => setError('Could not load that patient.'))
  }

  const reasons = patient && hour !== null ? (patient.reasons[String(hour)] ?? []) : []

  return (
    <>
      <ResearchBanner />
      <main className="page">
        <header>
          <h1>SepsiScope demo</h1>
          {summary && <p className="muted">{summary.note}</p>}
        </header>
        {error && <p className="error">{error}</p>}
        <div className="layout">
          <nav aria-label="Demo patients">
            {summary?.patients.map((p) => (
              <button
                key={p.key}
                type="button"
                className={patient?.key === p.key ? 'patient active' : 'patient'}
                onClick={() => open(p.key)}
              >
                <strong>{p.label}</strong>
                <span>{p.story}</span>
                <span className="muted">
                  {p.hours} h · {p.septic ? 'septic' : 'not septic'}
                </span>
              </button>
            ))}
          </nav>
          <section className="detail">
            {!patient && <p className="muted">Choose a demo patient.</p>}
            {patient && summary && (
              <>
                <h2>
                  {patient.label}: {patient.story}
                </h2>
                <p className="muted">
                  Age {patient.age_group} · {patient.hours} hours in the ICU ·{' '}
                  {patient.onset_hour === null
                    ? 'no sepsis onset'
                    : `sepsis onset at hour ${patient.onset_hour}`}{' '}
                  · {patient.alert_hours.length} LightGBM alert hours
                </p>
                <Timeline
                  title="LightGBM risk (calibrated probability)"
                  values={patient.risk}
                  threshold={summary.lgbm_threshold}
                  alerts={patient.alert_hours}
                  onset={patient.onset_hour}
                  selected={hour}
                  onSelect={setHour}
                  format={(v) => `${(v * 100).toFixed(1)} %`}
                />
                <Timeline
                  title="Modified NEWS2 (max 17)"
                  values={patient.news2}
                  threshold={summary.news2_threshold}
                  alerts={patient.news2
                    .map((v, h) => (v >= summary.news2_threshold ? h : -1))
                    .filter((h) => h >= 0)}
                  onset={patient.onset_hour}
                  selected={hour}
                  maxValue={17}
                  format={(v) => String(v)}
                />
                <h3>{hour === null ? 'No LightGBM alerts for this patient' : `Top 5 reasons at hour ${hour}`}</h3>
                {reasons.length > 0 && (
                  <table>
                    <thead>
                      <tr>
                        <th>Reason</th>
                        <th>Value</th>
                        <th>Effect on risk</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reasons.map((r) => (
                        <tr key={r.feature}>
                          <td>{r.label}</td>
                          <td>{r.value === null ? 'not measured yet' : r.value}</td>
                          <td className={r.contribution > 0 ? 'up' : 'down'}>
                            {r.contribution > 0 ? 'raises' : 'lowers'} ({r.contribution.toFixed(2)} log-odds)
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <p className="muted small">
                  Alert threshold chosen on hospital B's validation patients for a 5 % alert budget.
                  Reasons are LightGBM feature contributions; they explain the model, not the
                  patient's illness.
                </p>
              </>
            )}
          </section>
        </div>
      </main>
    </>
  )
}

export default App
