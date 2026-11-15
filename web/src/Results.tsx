// "Results": headline numbers from the committed aggregate result files (no patient data).
import { DIRS, NAMES, ORDER, ci, pct, rowsFor, useResults } from './resultsData'
import { Robustness } from './Robustness'
import { Legend, TableToggle } from './ui'
import { useTooltip, useWidth } from './hooks'
import type { ResultRow, Results as ResultsDoc } from './types'

const COLORS: Record<string, string> = {
  lgbm: 'var(--risk)',
  lr: 'var(--compare)',
  news2: 'var(--news2)',
  sirs: 'var(--ok)',
  qsofa: 'var(--muted)',
}
export function Results() {
  const [doc, error] = useResults()
  if (error) return <p className="error">{error}</p>
  if (!doc) return <p className="help">Loading…</p>
  return (
    <div className="results">
      <section className="panel">
        <h2>Utility on the unseen hospital</h2>
        <p className="help">
          The official PhysioNet utility rewards timely warnings and penalises misses and false alarms (1 = perfect, 0 = never
          alerting). Bars = value; black lines = 95 % confidence interval from 1,000 patient-level resamples.
        </p>
        <UtilityChart doc={doc} />
        <p className="help">
          Pre-registered test: SepsiScope beats the logistic regression only if the 95 % interval of the utility difference excludes
          0 in both directions.{' '}
          {Object.entries(doc.criterion).map(([d, c]) => (
            <span key={d} className="num">
              {d}: {c.met_in_this_direction ? 'met' : 'not met'} (+{c.ci95_utility_difference[0].toFixed(3)} to +
              {c.ci95_utility_difference[1].toFixed(3)}).{' '}
            </span>
          ))}
        </p>
      </section>
      {Object.entries(DIRS).map(([d, title]) => (
        <section className="panel" key={d}>
          <h2>{title}</h2>
          <p className="help">Threshold chosen on the training hospital; every patient of the other hospital tested. 95 % CIs in brackets.</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Model</th>
                  <th scope="col">Utility</th>
                  <th scope="col">AUROC</th>
                  <th scope="col">AUPRC</th>
                  <th scope="col">Timely sensitivity</th>
                  <th scope="col">Alert rate</th>
                  <th scope="col">False alerts / 100 non-septic days</th>
                </tr>
              </thead>
              <tbody>
                {rowsFor(doc, d).map((r) => (
                  <tr key={r.model} className={r.model === 'lgbm' ? 'highlight' : undefined}>
                    <th scope="row">{NAMES[r.model]}</th>
                    <td>
                      {r.utility.toFixed(3)} <span className="ci-text">[{ci(r.utility_ci)}]</span>
                    </td>
                    <td>
                      {r.auroc.toFixed(3)} <span className="ci-text">[{ci(r.auroc_ci)}]</span>
                    </td>
                    <td>
                      {r.auprc.toFixed(3)} <span className="ci-text">[{ci(r.auprc_ci)}]</span>
                    </td>
                    <td>
                      {pct(r.timely_sensitivity)} <span className="ci-text">[{ci(r.timely_sensitivity_ci, pct)}]</span>
                    </td>
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
        <h2>Alert drift at the unseen hospital (trained on B → tested on A)</h2>
        <p className="help">
          A threshold set for a {pct(doc.alarm_budget)} alert budget at one hospital alerts more often at another. Re-setting it from the
          new hospital's own unlabelled risk scores (no outcomes needed) brings it back.
        </p>
        <DriftChart rows={rowsFor(doc, 'B2A')} budget={doc.alarm_budget} />
      </section>
      {doc.robustness && <Robustness r={doc.robustness} />}
      <section className="panel limits">
        <h2>Limitations</h2>
        <ul>
          <li>Research prototype on retrospective data from two US hospitals; never used on live patients.</li>
          <li>"Measurements so far" counts partly reflect time in the ICU and staff habits, not only illness.</li>
          <li>Most septic patients are still not warned in time, and most alerts are false.</li>
          <li>The alert threshold drifts at a new hospital (8.3 % instead of 5 %) unless it is re-set there.</li>
          <li>Patients septic on admission cannot be warned early; their onset is set by a dataset rule.</li>
          <li>The modified scores lack items the data does not record (consciousness, mental state, band cells).</li>
          {doc.robustness && (
            <>
              <li>
                Pre-registered shortcut check failed ("collapse"): after 96 hours in the ICU the model ranks patients barely better
                than chance (AUROC {doc.robustness.bands.A2B.models.lgbm.bands['96h+'].auroc.point.toFixed(3)} and{' '}
                {doc.robustness.bands.B2A.models.lgbm.bands['96h+'].auroc.point.toFixed(3)}), and trained on hospital A it gives almost no
                alerts in the first 48 hours: much of its signal tracks time in the ICU.
              </li>
              <li>
                Conformal deferral is not useful at the main setting: it would hand{' '}
                {pct(doc.robustness.deferral.A2B.deferral_rate.point)} and {pct(doc.robustness.deferral.B2A.deferral_rate.point)} of
                hours to a clinician (limit 30 %), and its coverage is not guaranteed at a new hospital.
              </li>
            </>
          )}
        </ul>
      </section>
    </div>
  )
}

function UtilityChart({ doc }: { doc: ResultsDoc }) {
  const [ref, W] = useWidth<HTMLDivElement>()
  const tip = useTooltip()
  const H = 320
  const pad = { l: 60, r: 12, t: 14, b: 50 }
  const groups = Object.keys(DIRS).map((d) => ({ d, rows: rowsFor(doc, d) }))
  const max = Math.max(...doc.rows.map((r) => r.utility_ci[1]), 0.05) * 1.18
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b)
  const gw = (W - pad.l - pad.r) / groups.length
  const bw = gw / (ORDER.length + 1.5)
  return (
    <>
      <Legend items={ORDER.map((m) => ({ label: NAMES[m], kind: 'bar' as const, color: COLORS[m] }))} />
      <div ref={ref} className="plot">
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Utility by model and direction with 95 % intervals">
          {[0, max / 2, max].map((v) => (
            <g key={v}>
              <line className="grid" x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} />
              <text className="tick" x={pad.l - 6} y={y(v) + 4} textAnchor="end">
                {v.toFixed(2)}
              </text>
            </g>
          ))}
          <text className="axis-label" transform={`translate(14 ${(pad.t + H - pad.b) / 2}) rotate(-90)`} textAnchor="middle">
            Normalised utility
          </text>
          {groups.map((g, gi) => (
            <g key={g.d}>
              {g.rows.map((r, i) => {
                const x = pad.l + gi * gw + (i + 0.75) * bw
                return (
                  <g
                    key={r.model}
                    onMouseMove={(e) => tip.show(e, <span>{`${NAMES[r.model]}: ${r.utility.toFixed(3)} [${ci(r.utility_ci)}]`}</span>)}
                    onMouseLeave={tip.hide}
                  >
                    <rect x={x} y={y(r.utility)} width={bw * 0.82} height={Math.max(0, y(0) - y(r.utility))} fill={COLORS[r.model]} />
                    <line className="ci" x1={x + bw * 0.41} x2={x + bw * 0.41} y1={y(r.utility_ci[0])} y2={y(r.utility_ci[1])} />
                    {bw >= 34 && (
                      <text className="bar-value" x={x + bw * 0.41} y={y(r.utility_ci[1]) - 6} textAnchor="middle">
                        {r.utility.toFixed(3)}
                      </text>
                    )}
                  </g>
                )
              })}
              <text className="axis-label" x={pad.l + gi * gw + gw / 2} y={H - pad.b + 24} textAnchor="middle">
                {DIRS[g.d]}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <TableToggle
        caption="Utility with 95 % CI"
        columns={['Model', ...Object.values(DIRS)]}
        rows={ORDER.map((m) => [
          NAMES[m],
          ...groups.map((g) => {
            const r = g.rows.find((x) => x.model === m)
            return r ? `${r.utility.toFixed(3)} [${ci(r.utility_ci)}]` : '—'
          }),
        ])}
      />
    </>
  )
}

function DriftChart({ rows, budget }: { rows: ResultRow[]; budget: number }) {
  const [ref, W] = useWidth<HTMLDivElement>()
  const lr = rows.find((r) => r.model === 'lr')
  const lg = rows.find((r) => r.model === 'lgbm')
  if (!lr || !lg) return null
  const bars = [
    { label: 'Logistic regression', v: lr.alert_rate, c: 'var(--compare)' },
    { label: 'Logistic regression, re-set', v: lr.rethresholded_alert_rate, c: 'var(--compare)' },
    { label: 'SepsiScope', v: lg.alert_rate, c: 'var(--risk)' },
    { label: 'SepsiScope, re-set', v: lg.rethresholded_alert_rate, c: 'var(--risk)' },
  ]
  const narrow = W < 560
  const pad = { l: narrow ? 12 : 240, r: 80 }
  const rowH = narrow ? 58 : 44
  const max = Math.max(...bars.map((b) => b.v), budget) * 1.1
  const x = (v: number) => pad.l + (v / max) * (W - pad.l - pad.r)
  const H = bars.length * rowH + 32
  return (
    <>
      <Legend
        items={[
          { label: `Alert budget (${(budget * 100).toFixed(0)} % of hours)`, kind: 'dash', color: 'var(--raise)' },
          { label: 'Logistic regression', kind: 'bar', color: 'var(--compare)' },
          { label: 'SepsiScope', kind: 'bar', color: 'var(--risk)' },
        ]}
      />
      <div ref={ref} className="plot">
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Realised alert rate against the 5 % budget">
          {bars.map((b, i) => (
            <g key={b.label} transform={`translate(0 ${i * rowH + 6})`}>
              <text className="bar-label" x={narrow ? pad.l : pad.l - 8} y={narrow ? 14 : rowH / 2} textAnchor={narrow ? 'start' : 'end'}>
                {b.label}
              </text>
              <rect x={pad.l} y={narrow ? 22 : 8} width={Math.max(2, x(b.v) - pad.l)} height={rowH - (narrow ? 30 : 18)} fill={b.c} />
              <text className="bar-value" x={x(b.v) + 6} y={narrow ? 38 : rowH / 2 + 4}>
                {(b.v * 100).toFixed(1)} %
              </text>
            </g>
          ))}
          <line className="budget" x1={x(budget)} x2={x(budget)} y1={0} y2={H - 22} />
          <text className="budget-label" x={x(budget) + 4} y={H - 6}>
            {(budget * 100).toFixed(0)} % budget
          </text>
        </svg>
      </div>
      <TableToggle caption="Realised alert rate" columns={['Model', 'Alert rate']} rows={bars.map((b) => [b.label, `${(b.v * 100).toFixed(1)} %`])} />
    </>
  )
}
