// "Patient replay": pick a held-out patient, then replay their ICU stay hour by hour.
import { useEffect, useState } from 'react'
import { LineChart } from './LineChart'
import { WhyPanel } from './WhyPanel'
import type { Patient, Summary, Verdict } from './types'

const VITAL_ORDER = ['HR', 'Resp', 'Temp', 'SBP', 'O2Sat']

function badgeClass(v: Verdict): string {
  if (v.outcome === 'warned' || v.outcome === 'quiet') return 'badge good'
  return 'badge bad'
}

export function Replay({ summary }: { summary: Summary }) {
  const [patient, setPatient] = useState<Patient | null>(null)
  const [revealed, setRevealed] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [hover, setHover] = useState<number | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  function open(key: string) {
    setPlaying(false)
    fetch(`/api/patients/${key}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((p: Patient) => {
        setPatient(p)
        setRevealed(p.hours - 1)
        setPicked(p.alert_hours.length ? p.alert_hours[0] : null)
        setError(null)
      })
      .catch(() => setError('Could not load that patient.'))
  }

  useEffect(() => {
    if (!playing || !patient) return
    const id = window.setInterval(() => {
      setRevealed((r) => {
        if (r >= patient.hours - 1) {
          setPlaying(false)
          return r
        }
        return r + 1
      })
    }, 450)
    return () => window.clearInterval(id)
  }, [playing, patient])

  function togglePlay() {
    if (!patient) return
    if (!playing && revealed >= patient.hours - 1) {
      setRevealed(0)
      setPicked(null)
    }
    setPlaying(!playing)
  }

  const shown = hover ?? picked ?? (patient ? revealed : null)
  const thr = summary.lgbm_threshold
  const thrLabel = `Alert threshold (${(thr * 100).toFixed(1)} %)`

  return (
    <div className="replay">
      <nav className="cards" aria-label="Demo patients">
        {summary.patients.map((p) => (
          <button
            key={p.key}
            type="button"
            className={patient?.key === p.key ? 'card selected' : 'card'}
            aria-pressed={patient?.key === p.key}
            onClick={() => open(p.key)}
          >
            <span className="card-title">{p.label}</span>
            <span className="card-story" title={p.story_note ?? undefined}>
              {p.story}
              {p.story_note && <span className="info" aria-label={p.story_note}> ⓘ</span>}
            </span>
            <span className="card-meta">
              {p.hours} h in ICU · {p.septic ? 'developed sepsis' : 'no sepsis'}
            </span>
            <span className="badges">
              <span className={badgeClass(p.verdict.sepsiscope)}>SepsiScope: {p.verdict.sepsiscope.badge}</span>
              <span className={badgeClass(p.verdict.news2)}>NEWS2: {p.verdict.news2.badge}</span>
            </span>
          </button>
        ))}
      </nav>
      {error && <p className="error">{error}</p>}
      {!patient && (
        <p className="help big">
          Choose a patient above. Each one is a real, de-identified ICU stay from a hospital the model
          never saw during training. Successes and failures are both shown.
        </p>
      )}
      {patient && (
        <>
          <div className="banner-verdict" role="status">
            <strong>{patient.label}:</strong> {patient.banner}
          </div>
          {patient.story_note && <p className="help">{patient.story_note}</p>}
          <div className="controls">
            <button type="button" className="play" onClick={togglePlay} aria-pressed={playing}>
              {playing ? '❚❚ Pause' : '▶ Play'}
            </button>
            <label className="slider">
              <span>
                Hour {revealed} of {patient.hours - 1}
              </span>
              <input
                type="range"
                min={0}
                max={patient.hours - 1}
                value={revealed}
                onChange={(e) => {
                  const h = Number(e.target.value)
                  setPlaying(false)
                  setRevealed(h)
                  setPicked(h)
                }}
                aria-label="Replay hour"
              />
            </label>
          </div>
          <Readout patient={patient} hour={shown} summary={summary} />
          <div className="replay-grid">
            <div className="charts">
              <LineChart
                title="SepsiScope: predicted sepsis risk"
                help={`LightGBM's calibrated probability each hour. A dot marks an hour above the threshold, which was chosen on the training hospital so about ${(summary.alarm_budget * 100).toFixed(0)} % of hours alert there (it is not the 5 % itself).`}
                values={patient.risk}
                totalHours={patient.hours}
                revealed={revealed}
                hover={hover}
                onHover={setHover}
                onPick={setPicked}
                picked={picked}
                color="var(--risk)"
                yLabel="Predicted sepsis risk (%)"
                format={(v) => `${(v * 100).toFixed(1)} %`}
                yMin={0}
                threshold={{ value: thr, label: thrLabel }}
                window={patient.window}
                onset={patient.onset_hour}
                alerts={patient.alert_hours}
              />
              <LineChart
                title="Modified NEWS2 (max 17)"
                help={`The bedside early-warning score most UK hospitals use. It alerts at ${summary.news2_threshold} or more (same 5 % rule).`}
                values={patient.news2}
                totalHours={patient.hours}
                revealed={revealed}
                hover={hover}
                onHover={setHover}
                color="var(--news2)"
                yLabel="NEWS2 points"
                format={(v) => v.toFixed(0)}
                yMin={0}
                yMax={17}
                threshold={{ value: summary.news2_threshold, label: `Alert threshold (${summary.news2_threshold})` }}
                window={patient.window}
                onset={patient.onset_hour}
                alerts={patient.news2_alert_hours}
                height={190}
              />
              <h3 className="vitals-title">Vital signs</h3>
              <p className="help">Last measured value each hour; the green band is the range that scores 0 NEWS2 points.</p>
              <div className="vitals">
                {VITAL_ORDER.map((v) => {
                  const info = summary.vitals[v]
                  return (
                    <LineChart
                      key={v}
                      compact
                      title={`${info.label} (${info.unit})`}
                      help={`Normal ${info.normal[0]}–${info.normal[1]} ${info.unit}`}
                      values={patient.vitals[v]}
                      totalHours={patient.hours}
                      revealed={revealed}
                      hover={hover}
                      onHover={setHover}
                      color="var(--text)"
                      yLabel={info.unit}
                      format={(x) => (Math.abs(x) >= 20 ? x.toFixed(0) : x.toFixed(1))}
                      normal={info.normal}
                      window={patient.window}
                      onset={patient.onset_hour}
                      height={170}
                    />
                  )
                })}
              </div>
            </div>
            <WhyPanel
              hour={picked}
              reasons={picked === null ? [] : patient.reasons[picked]}
              risk={picked === null ? null : patient.risk[picked]}
              alerted={picked !== null && patient.alert_hours.includes(picked)}
            />
          </div>
          <details className="rules">
            <summary>How the verdicts are decided</summary>
            <ol>
              {summary.rules.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ol>
          </details>
        </>
      )}
    </div>
  )
}

function Readout({ patient, hour, summary }: { patient: Patient; hour: number | null; summary: Summary }) {
  if (hour === null) return null
  const v = (k: string) => {
    const x = patient.vitals[k]?.[hour]
    return x === null || x === undefined ? '—' : `${x} ${summary.vitals[k].unit}`
  }
  return (
    <p className="readout" aria-live="polite">
      <strong>Hour {hour}</strong> · risk {(patient.risk[hour] * 100).toFixed(1)} %
      {patient.alert_hours.includes(hour) ? ' (alert)' : ''} · NEWS2 {patient.news2[hour]} · HR {v('HR')} · breathing{' '}
      {v('Resp')} · temp {v('Temp')} · SBP {v('SBP')} · SpO₂ {v('O2Sat')}
    </p>
  )
}
