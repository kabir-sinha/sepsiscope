// "Patient replay": pick a held-out patient and replay the ICU stay hour by hour.
// One selected hour drives everything: Play, the slider, ←/→ and clicks all set it.
// Hovering a chart only previews an hour ("Hovering hour N").
import { useEffect, useMemo, useState } from 'react'
import { display } from './chartMath'
import { LineChart } from './LineChart'
import type { Series } from './LineChart'
import { Legend } from './ui'
import { WhyPanel } from './WhyPanel'
import type { Patient, PatientRow, Summary, Verdict } from './types'

const VITAL_ORDER = ['HR', 'Resp', 'Temp', 'SBP', 'O2Sat']
const SPEEDS = [0.5, 1, 2]
const BASE_MS = 600

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

function badgeClass(v: Verdict): string {
  return v.outcome === 'warned' || v.outcome === 'quiet' ? 'badge good' : 'badge bad'
}

function bannerText(p: PatientRow, k: number): string {
  const s = p.what_if.sepsiscope[k].verdict
  const n = p.what_if.news2[k].verdict
  return p.septic
    ? `SepsiScope ${s.sentence} · NEWS2 ${n.sentence}`
    : `Not septic · false alarm hours: SepsiScope ${s.false_alarm_hours} vs NEWS2 ${n.false_alarm_hours}`
}

export function Replay({ summary }: { summary: Summary }) {
  const budgets = summary.what_if.budgets
  const headlineK = Math.max(0, budgets.findIndex((b) => Math.abs(b - summary.alarm_budget) < 1e-9))
  const [patient, setPatient] = useState<Patient | null>(null)
  const [hour, setHour] = useState<number | null>(null)
  const [hover, setHover] = useState<number | null>(null)
  const [replay, setReplay] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(reducedMotion() ? 0.5 : 1)
  const [k, setK] = useState(headlineK)
  const [compare, setCompare] = useState<'none' | 'lr' | 'news2'>('none')
  const [error, setError] = useState<string | null>(null)

  const last = patient ? patient.hours - 1 : 0
  const revealed = patient ? (replay ? (hour ?? 0) : last) : 0

  function open(key: string) {
    setPlaying(false)
    fetch(`/api/patients/${key}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((p: Patient) => {
        setPatient(p)
        setReplay(false)
        // Start at the first alert hour; with no alert, at the highest-risk hour.
        const alerts = p.what_if.sepsiscope[k].alert_hours
        const peak = p.risk.reduce((best, v, h) => (v > p.risk[best] ? h : best), 0)
        setHour(alerts.length ? alerts[0] : peak)
        setError(null)
      })
      .catch(() => setError('Could not load that patient.'))
  }

  // Playback: advance the selected hour; stop at the end of the stay.
  useEffect(() => {
    if (!playing || !patient) return
    const id = window.setInterval(() => {
      setHour((h) => {
        const next = (h ?? 0) + 1
        if (next >= last) setPlaying(false)
        return Math.min(next, last)
      })
    }, BASE_MS / speed)
    return () => window.clearInterval(id)
  }, [playing, patient, speed, last])

  function togglePlay() {
    if (!patient) return
    if (!playing && (!replay || (hour ?? 0) >= last)) {
      setReplay(true)
      setHour(0)
    }
    setPlaying((v) => !v)
  }
  function step(d: number) {
    if (!patient) return
    setPlaying(false)
    setReplay(true)
    setHour((h) => Math.max(0, Math.min(last, (h ?? 0) + d)))
  }

  // Keyboard: Space = play/pause, ←/→ = one hour. Ignored while typing in a control.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement
      if (t.closest('input, select, textarea, [role="tab"], summary')) return
      if (e.key === ' ' && !t.closest('button')) {
        e.preventDefault()
        togglePlay()
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        if (t.closest('circle')) return
        e.preventDefault()
        step(e.key === 'ArrowRight' ? 1 : -1)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const thr = summary.what_if.lgbm_thresholds[k]
  const n2thr = summary.what_if.news2_thresholds[k]
  const alerts = patient?.what_if.sepsiscope[k].alert_hours ?? []
  const n2alerts = patient?.what_if.news2[k].alert_hours ?? []
  const riskSeries: Series[] = useMemo(() => {
    if (!patient) return []
    const s: Series[] = [{ label: 'SepsiScope risk', values: patient.risk, color: 'var(--risk)' }]
    if (compare === 'lr') s.push({ label: 'Logistic regression risk', values: patient.compare.lr, color: 'var(--compare)', dashed: true })
    if (compare === 'news2') s.push({ label: 'NEWS2 as a probability', values: patient.compare.news2_prob, color: 'var(--news2)', dashed: true })
    return s
  }, [patient, compare])
  const pct = (v: number) => (v * 100).toFixed(v < 0.1 ? 2 : 1)

  return (
    <div className="replay">
      <div className="controls budget">
        <label className="slider">
          <span>
            What-if alert budget: <strong className="num">{(budgets[k] * 100).toFixed(0)} %</strong> of hours
          </span>
          <input
            type="range"
            min={0}
            max={budgets.length - 1}
            value={k}
            onChange={(e) => setK(Number(e.target.value))}
            aria-label="What-if alert budget"
            aria-valuetext={`${(budgets[k] * 100).toFixed(0)} percent of hours`}
          />
        </label>
        <span className="help small">
          Threshold <span className="num">{pct(thr)} %</span> (NEWS2 ≥ {n2thr}), chosen on hospital B's validation patients only.
          {k === headlineK ? ' This is the pre-registered setting.' : ' Exploratory: the headline uses 5 %.'}
        </span>
      </div>

      <nav className="cards" aria-label="Demo patients">
        {summary.patients.map((p) => {
          const s = p.what_if.sepsiscope[k].verdict
          const n = p.what_if.news2[k].verdict
          return (
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
                <span className={badgeClass(s)}>SepsiScope: {s.badge}</span>
                <span className={badgeClass(n)}>NEWS2: {n.badge}</span>
              </span>
            </button>
          )
        })}
      </nav>
      {error && <p className="error">{error}</p>}
      {!patient && (
        <p className="help big">
          Choose a patient. Each is a real, de-identified ICU stay from a hospital the model never saw in training. Successes and failures are both shown.
        </p>
      )}
      {patient && (
        <>
          <div className="banner-verdict" role="status">
            <strong>{patient.label}:</strong> {bannerText(patient, k)}
          </div>
          {patient.story_note && <p className="help">{patient.story_note}</p>}
          <div className="controls">
            <button type="button" className="btn primary" onClick={togglePlay} aria-pressed={playing} aria-keyshortcuts="Space">
              {playing ? '❚❚ Pause' : '▶ Play'}
            </button>
            <button type="button" className="btn" onClick={() => step(-1)} aria-label="Previous hour" aria-keyshortcuts="ArrowLeft">
              ◀
            </button>
            <button type="button" className="btn" onClick={() => step(1)} aria-label="Next hour" aria-keyshortcuts="ArrowRight">
              ▶
            </button>
            <label className="slider">
              <span className="num">
                Selected hour {hour ?? 0} / {last}
              </span>
              <input
                type="range"
                min={0}
                max={last}
                value={hour ?? 0}
                onChange={(e) => {
                  setPlaying(false)
                  setReplay(true)
                  setHour(Number(e.target.value))
                }}
                aria-label="Selected hour"
              />
            </label>
            <label className="select">
              Speed{' '}
              <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
                {SPEEDS.map((s) => (
                  <option key={s} value={s}>
                    {s}×
                  </option>
                ))}
              </select>
            </label>
            <label className="select">
              Compare with{' '}
              <select value={compare} onChange={(e) => setCompare(e.target.value as 'none' | 'lr' | 'news2')}>
                <option value="none">nothing</option>
                <option value="lr">logistic regression</option>
                <option value="news2">NEWS2 (as probability)</option>
              </select>
            </label>
            {replay && (
              <button type="button" className="btn" onClick={() => setReplay(false)}>
                Show whole stay
              </button>
            )}
          </div>
          <p className="help small">Keys: Space play/pause · ← → one hour · Tab to reach alert dots, Enter to select.</p>
          <Readout patient={patient} hour={hover ?? hour} hovering={hover !== null} summary={summary} alerts={alerts} />
          <div className="replay-grid">
            <div className="charts">
              <LineChart
                title="SepsiScope: predicted sepsis risk"
                help="LightGBM's calibrated probability each hour. Dots mark alert hours (risk at or above the threshold)."
                series={riskSeries}
                totalHours={patient.hours}
                revealed={revealed}
                hour={hour}
                hover={hover}
                onHover={setHover}
                onSelect={(h) => {
                  setPlaying(false)
                  setHour(h)
                }}
                yLabel="Predicted sepsis risk (%)"
                unit=" %"
                format={(v) => pct(v)}
                tickFormat={(v) => `${display(v * 100)} %`}
                yMin={0}
                threshold={{ value: thr, label: `Alert threshold (${pct(thr)} %)` }}
                window={patient.window}
                onset={patient.onset_hour}
                alerts={alerts}
                height={270}
              />
              <LineChart
                title="Modified NEWS2 (max 17)"
                help={`The UK bedside early-warning score; alerts at ${n2thr} or more at this budget.`}
                series={[{ label: 'NEWS2 points', values: patient.news2, color: 'var(--news2)' }]}
                totalHours={patient.hours}
                revealed={revealed}
                hour={hour}
                hover={hover}
                onHover={setHover}
                onSelect={setHour}
                yLabel="NEWS2 points"
                unit=""
                format={(v) => v.toFixed(0)}
                yMin={0}
                yMax={17}
                threshold={{ value: n2thr, label: `Alert threshold (${n2thr})` }}
                window={patient.window}
                onset={patient.onset_hour}
                alerts={n2alerts}
                height={220}
              />
              <section aria-labelledby="vitals-title">
                <h3 id="vitals-title" className="vitals-title">
                  Vital signs
                </h3>
                <p className="help">Last measured value each hour. Green band = the range that scores 0 NEWS2 points.</p>
                <Legend
                  items={[
                    { label: 'Last measured value', kind: 'line', color: 'var(--text)' },
                    { label: 'Normal range (0 NEWS2 points)', kind: 'band', color: 'var(--ok)' },
                    { label: 'Early-warning window', kind: 'band', color: 'var(--window)' },
                    { label: 'Sepsis onset', kind: 'line', color: 'var(--onset)' },
                  ]}
                />
                <div className="vitals">
                  {VITAL_ORDER.map((v) => {
                    const info = summary.vitals[v]
                    return (
                      <LineChart
                        key={v}
                        legend={false}
                        title={`${info.label} (${info.unit})`}
                        help={`Normal ${info.normal[0]}–${info.normal[1]} ${info.unit}`}
                        series={[{ label: info.label, values: patient.vitals[v], color: 'var(--text)' }]}
                        totalHours={patient.hours}
                        revealed={revealed}
                        hour={hour}
                        hover={hover}
                        onHover={setHover}
                        onSelect={setHour}
                        yLabel={info.unit}
                        unit={` ${info.unit}`}
                        format={(x) => String(Number(x.toFixed(1)))}
                        normal={info.normal}
                        window={patient.window}
                        onset={patient.onset_hour}
                        height={210}
                      />
                    )
                  })}
                </div>
              </section>
            </div>
            <WhyPanel
              hour={hour}
              reasons={hour === null ? [] : patient.reasons[hour]}
              risk={hour === null ? null : patient.risk[hour]}
              alerted={hour !== null && alerts.includes(hour)}
              threshold={thr}
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

function Readout(props: { patient: Patient; hour: number | null; hovering: boolean; summary: Summary; alerts: number[] }) {
  const { patient, hour, hovering, summary, alerts } = props
  if (hour === null) return null
  const v = (k: string) => {
    const x = patient.vitals[k]?.[hour]
    return x === null || x === undefined ? 'not measured yet' : `${Number(x.toFixed(1))} ${summary.vitals[k].unit}`
  }
  return (
    <p className={hovering ? 'readout hovering' : 'readout'} aria-live="polite">
      <strong>{hovering ? `Hovering hour ${hour}` : `Selected hour ${hour}`}</strong>
      <span className="num">
        {' '}
        · risk {(patient.risk[hour] * 100).toFixed(2)} %{alerts.includes(hour) ? ' (alert)' : ''} · NEWS2 {patient.news2[hour]} · HR {v('HR')} ·
        breathing {v('Resp')} · temp {v('Temp')} · SBP {v('SBP')} · SpO₂ {v('O2Sat')}
      </span>
    </p>
  )
}
