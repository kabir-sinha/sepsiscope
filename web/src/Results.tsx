// "Results": headline numbers from the committed aggregate result files (no patient data).
import { useEffect, useState } from 'react'
import { Legend } from './LineChart'
import type { ResultRow, Results as ResultsDoc } from './types'

const ORDER = ['lgbm', 'lr', 'news2', 'sirs', 'qsofa']
const NAMES: Record<string, string> = {
  lgbm: 'SepsiScope (LightGBM)',
  lr: 'Logistic regression',
  news2: 'Modified NEWS2 (max 17)',
  sirs: 'SIRS (max 4)',
  qsofa: 'Modified qSOFA (max 2)',
}
const DIRS: Record<string, string> = {
  A2B: 'Trained on A, tested on B',
  B2A: 'Trained on B, tested on A',
}
const pct = (v: number) => `${(v * 100).toFixed(1)} %`

export function Results() {
  const [doc, setDoc] = useState<ResultsDoc | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    fetch('/api/results')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setDoc)
      .catch(() => setError('Results not reachable.'))
  }, [])
  if (error) return <p className="error">{error}</p>
  if (!doc) return <p className="help">Loading…</p>
  const rows = (d: string) =>
    ORDER.map((m) => doc.rows.find((r) => r.model === m && r.direction === d)).filter(
      (r): r is ResultRow => r !== undefined,
    )

  return (
    <div className="results">
      <section className="panel">
        <h2>Utility on the unseen hospital</h2>
        <p className="help">
          The official PhysioNet utility rewards early warnings and penalises misses and false alarms
          (1 = perfect, 0 = never alerting). Bars show the value; lines show the 95 % confidence
          interval from 1,000 patient-level resamples.
        </p>
        <UtilityChart groups={Object.keys(DIRS).map((d) => ({ dir: d, rows: rows(d) }))} />
        <p className="help">
          Pre-registered test: SepsiScope beats the logistic regression only if the 95 % interval of
          the difference excludes 0 in both directions —{' '}
          {Object.entries(doc.criterion)
            .map(([d, c]) => `${d}: ${c.met_in_this_direction ? 'met' : 'not met'} (+${c.ci95_utility_difference[0].toFixed(3)} to +${c.ci95_utility_difference[1].toFixed(3)})`)
            .join('; ')}
          .
        </p>
      </section>
      {Object.entries(DIRS).map(([d, title]) => (
        <section className="panel" key={d}>
          <h2>{title}</h2>
          <p className="help">Threshold chosen on the training hospital; every patient of the other hospital tested.</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Model</th>
                  <th scope="col">Utility (95 % CI)</th>
                  <th scope="col">AUROC</th>
                  <th scope="col">Alert rate</th>
                  <th scope="col">False alerts / 100 non-septic days</th>
                </tr>
              </thead>
              <tbody>
                {rows(d).map((r) => (
                  <tr key={r.model} className={r.model === 'lgbm' ? 'highlight' : undefined}>
                    <th scope="row">{NAMES[r.model]}</th>
                    <td>
                      {r.utility.toFixed(3)} ({r.utility_ci[0].toFixed(3)}–{r.utility_ci[1].toFixed(3)})
                    </td>
                    <td>{r.auroc.toFixed(3)}</td>
                    <td className={r.alert_rate > doc.alarm_budget * 1.2 ? 'over' : undefined}>{pct(r.alert_rate)}</td>
                    <td>{r.false_alerts_per_100_days.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
      <section className="panel">
        <h2>Alert drift at the unseen hospital (trained on B, tested on A)</h2>
        <p className="help">
          A threshold set for a {pct(doc.alarm_budget)} alert budget at one hospital alerts more often at
          another. Re-setting it from the new hospital's own unlabelled risk scores (no outcomes needed)
          brings it back.
        </p>
        <DriftChart rows={rows('B2A')} budget={doc.alarm_budget} />
      </section>
      <section className="panel limits">
        <h2>Limitations</h2>
        <ul>
          <li>Research prototype on two US hospitals' retrospective data; never tested on live patients.</li>
          <li>"Measurements so far" counts partly reflect time in the ICU and staff habits, not only illness.</li>
          <li>Even at the best threshold most septic patients are not warned in time, and most alerts are false.</li>
          <li>Patients septic on admission cannot be warned early; their onset is set by a dataset rule.</li>
          <li>The modified scores lack items the data does not record (consciousness, mental state, band cells).</li>
        </ul>
      </section>
    </div>
  )
}

function UtilityChart({ groups }: { groups: { dir: string; rows: ResultRow[] }[] }) {
  const W = 760
  const H = 300
  const pad = { l: 56, r: 12, t: 12, b: 64 }
  const max = Math.max(...groups.flatMap((g) => g.rows.map((r) => r.utility_ci[1])), 0.05) * 1.1
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b)
  const gw = (W - pad.l - pad.r) / groups.length
  const bw = gw / (ORDER.length + 1.5)
  const colors: Record<string, string> = {
    lgbm: 'var(--risk)',
    lr: 'var(--window)',
    news2: 'var(--news2)',
    sirs: 'var(--ok)',
    qsofa: '#cc79a7',
  }
  return (
    <>
      <Legend items={ORDER.map((m) => ({ label: NAMES[m], kind: 'band' as const, color: colors[m] }))} />
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Utility by model and direction with 95 % intervals">
        {[0, max / 2, max].map((v) => (
          <g key={v}>
            <line className="grid" x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} />
            <text className="tick" x={pad.l - 6} y={y(v) + 4} textAnchor="end">
              {v.toFixed(2)}
            </text>
          </g>
        ))}
        <text className="axis-label" transform={`translate(14 ${H / 2 - 20}) rotate(-90)`} textAnchor="middle">
          Normalised utility
        </text>
        {groups.map((g, gi) => (
          <g key={g.dir}>
            {g.rows.map((r, i) => {
              const x = pad.l + gi * gw + (i + 0.75) * bw
              return (
                <g key={r.model}>
                  <rect x={x} y={y(r.utility)} width={bw * 0.8} height={y(0) - y(r.utility)} fill={colors[r.model]} opacity="0.85">
                    <title>{`${NAMES[r.model]}: ${r.utility.toFixed(3)} (${r.utility_ci[0].toFixed(3)}–${r.utility_ci[1].toFixed(3)})`}</title>
                  </rect>
                  <line className="ci" x1={x + bw * 0.4} x2={x + bw * 0.4} y1={y(r.utility_ci[0])} y2={y(r.utility_ci[1])} />
                </g>
              )
            })}
            <text className="axis-label" x={pad.l + gi * gw + gw / 2} y={H - pad.b + 22} textAnchor="middle">
              {DIRS[g.dir]}
            </text>
          </g>
        ))}
      </svg>
    </>
  )
}

function DriftChart({ rows, budget }: { rows: ResultRow[]; budget: number }) {
  const lr = rows.find((r) => r.model === 'lr')
  const lg = rows.find((r) => r.model === 'lgbm')
  if (!lr || !lg) return null
  const bars = [
    { label: 'Logistic regression', v: lr.alert_rate, c: 'var(--window)' },
    { label: 'Logistic regression, re-thresholded', v: lr.rethresholded_alert_rate, c: 'var(--window)' },
    { label: 'SepsiScope', v: lg.alert_rate, c: 'var(--risk)' },
    { label: 'SepsiScope, re-thresholded', v: lg.rethresholded_alert_rate, c: 'var(--risk)' },
  ]
  const W = 760
  const rowH = 40
  const pad = { l: 270, r: 70 }
  const max = Math.max(...bars.map((b) => b.v), budget) * 1.1
  const x = (v: number) => pad.l + (v / max) * (W - pad.l - pad.r)
  const H = bars.length * rowH + 30
  return (
    <>
      <Legend
        items={[
          { label: `Alert budget (${(budget * 100).toFixed(0)} % of hours)`, kind: 'dash', color: 'var(--alert)' },
          { label: 'Realised alert rate', kind: 'band', color: 'var(--risk)' },
        ]}
      />
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Realised alert rate against the 5 % budget">
        {bars.map((b, i) => (
          <g key={b.label} transform={`translate(0 ${i * rowH + 6})`}>
            <text className="bar-label" x={pad.l - 8} y={rowH / 2} textAnchor="end">
              {b.label}
            </text>
            <rect x={pad.l} y={6} width={x(b.v) - pad.l} height={rowH - 16} fill={b.c} opacity={b.label.includes('re-') ? 0.5 : 0.9} />
            <text className="bar-value" x={x(b.v) + 6} y={rowH / 2} >
              {(b.v * 100).toFixed(1)} %
            </text>
          </g>
        ))}
        <line className="budget" x1={x(budget)} x2={x(budget)} y1={0} y2={H - 20} />
        <text className="budget-label" x={x(budget) + 4} y={H - 6}>
          {(budget * 100).toFixed(0)} % budget
        </text>
      </svg>
    </>
  )
}
