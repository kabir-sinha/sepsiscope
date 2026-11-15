// "Robustness checks (Milestone 5)": C1 ICU-stay bands, C2 conformal deferral, C3 alert
// budgets. Every number comes from the committed aggregate files via /api/results.
import { DIRS, NAMES, ci, pct } from './resultsData'
import type { Metric, Robustness as RobustnessDoc } from './types'

const BAND_MODELS = ['lgbm', 'lr', 'news2']
const bandName = (b: string) => b.replace('-', '–').replace('h', ' h')
const f3 = (m: Metric) => (
  <>
    {m.point.toFixed(3)} <span className="ci-text">[{ci(m.ci)}]</span>
  </>
)
// Alert rates under 0.1 % keep two decimals, so 0.02 % does not read as zero.
const rate = (v: number) => (v > 0 && v < 0.001 ? `${(v * 100).toFixed(2)} %` : pct(v))
const signed = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(3)}`
const passFail = (ok: boolean) => <span className={ok ? 'pass' : 'fail'}>{ok ? 'pass' : 'fail'}</span>

export function Robustness({ r }: { r: RobustnessDoc }) {
  const a2b = r.bands.A2B
  const early = a2b.models.lgbm.bands
  const firstTwo = a2b.bands.slice(0, 2).map((b) => early[b].alert_rate.point)
  const last = a2b.bands[a2b.bands.length - 1]
  const collapsed = Object.values(r.bands).every((d) => d.collapse.collapse)
  const notUseful = Object.values(r.deferral).every((d) => !d.useful)
  const alpha = r.deferral.A2B.alpha
  return (
    <section className="panel" aria-labelledby="robust-title">
      <h2 id="robust-title">Robustness checks (Milestone 5)</h2>
      <p className="help">
        Three checks whose pass/fail rules were written down before any result was seen (ADR 0024). 95 % CIs in brackets, from 1,000
        patient-level resamples.
      </p>

      <h3>1. Does it still rank patients within each part of the ICU stay?</h3>
      <p className="help">AUROC inside each band of hours since ICU admission, at the headline thresholds (0.5 = chance).</p>
      {Object.entries(DIRS).map(([d, title]) => {
        const b = r.bands[d]
        return (
          <div key={d} className="table-wrap">
            <table>
              <caption>{title}</caption>
              <thead>
                <tr>
                  <th scope="col">Model</th>
                  {b.bands.map((n) => (
                    <th key={n} scope="col">
                      {bandName(n)}
                    </th>
                  ))}
                  <th scope="col">Whole stay</th>
                </tr>
              </thead>
              <tbody>
                {BAND_MODELS.map((m) => (
                  <tr key={m} className={m === 'lgbm' ? 'highlight' : undefined}>
                    <th scope="row">{NAMES[m]} AUROC</th>
                    {b.bands.map((n) => (
                      <td key={n}>{f3(b.models[m].bands[n].auroc)}</td>
                    ))}
                    <td>{b.models[m].overall_auroc.toFixed(3)}</td>
                  </tr>
                ))}
                <tr>
                  <th scope="row">SepsiScope alert rate</th>
                  {b.bands.map((n) => (
                    <td key={n}>{rate(b.models.lgbm.bands[n].alert_rate.point)}</td>
                  ))}
                  <td>—</td>
                </tr>
              </tbody>
            </table>
          </div>
        )
      })}
      <p className="finding">
        <strong>Pre-registered result: {collapsed ? 'collapse in both directions' : 'no collapse in both directions'}.</strong> The rule
        flags a band whose AUROC upper CI is below 0.60 or whose AUROC is more than 0.10 below the whole stay. Flagged:{' '}
        {Object.entries(r.bands)
          .flatMap(([d, x]) => x.collapse.flagged_bands.map((f) => `${d === 'A2B' ? 'A → B' : 'B → A'} ${bandName(f.band)}: ${f.reasons.join('; ')}`))
          .join(' · ')}
        . Trained on hospital A, SepsiScope raised {firstTwo.every((v) => v === 0) ? 'no' : 'almost no'} alerts in the first 48 hours (
        {firstTwo.map(rate).join(', ')}) and alerted in {pct(early[last].alert_rate.point)} of hours after 96 hours: its A → B
        alerts concentrate in long stays.
      </p>

      <h3>2. Can it safely hand uncertain hours to a clinician?</h3>
      <p className="help">
        Conformal deferral at α = {alpha.toFixed(2)} (the main setting): an hour is deferred when the model cannot rule either answer
        out. Criteria: (a) at most 30 % of hours deferred; (b) septic hours kept within 0.10 of non-septic ones; (c) utility on the
        hours kept above the headline.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Direction</th>
              <th scope="col">Hours deferred</th>
              <th scope="col">Coverage (non-septic / septic hours)</th>
              <th scope="col">Utility on hours kept</th>
              <th scope="col">(a)</th>
              <th scope="col">(b)</th>
              <th scope="col">(c)</th>
              <th scope="col">Useful?</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(DIRS).map(([d, title]) => {
              const x = r.deferral[d]
              return (
                <tr key={d}>
                  <th scope="row">{title}</th>
                  <td>
                    {pct(x.deferral_rate.point)} <span className="ci-text">[{ci(x.deferral_rate.ci, pct)}]</span>
                  </td>
                  <td>
                    {pct(x.coverage.label0)} / {pct(x.coverage.label1)}
                  </td>
                  <td>
                    {f3(x.utility_non_deferred)} <span className="ci-text">vs {x.headline_utility.toFixed(3)}</span>
                  </td>
                  <td>{passFail(x.criteria.a)}</td>
                  <td>{passFail(x.criteria.b)}</td>
                  <td>{passFail(x.criteria.c)}</td>
                  <td>{x.useful ? 'yes' : 'no'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="finding">
        <strong>Deferral is {notUseful ? 'not useful' : 'useful'} at the main setting.</strong> It would defer{' '}
        {Object.values(r.deferral)
          .map((x) => pct(x.deferral_rate.point))
          .join(' and ')}{' '}
        of hours, above the 30 % limit. Coverage aims at 90 % for each class; at the unseen hospital it is measured, not guaranteed.
      </p>

      <h3>3. Does the advantage hold at other alert budgets?</h3>
      <p className="help">Utility when the threshold allows 2, 5 or 10 % of hours to alert; difference = SepsiScope − logistic regression on the same resamples.</p>
      {Object.entries(DIRS).map(([d, title]) => (
        <div key={d} className="table-wrap">
          <table>
            <caption>{title}</caption>
            <thead>
              <tr>
                <th scope="col">Alert budget</th>
                <th scope="col">SepsiScope utility</th>
                <th scope="col">Logistic regression utility</th>
                <th scope="col">Difference</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(r.budgets[d]).map(([k, x]) => (
                <tr key={k}>
                  <th scope="row">{(Number(k) * 100).toFixed(0)} %</th>
                  <td>{f3(x.lgbm)}</td>
                  <td>{f3(x.lr)}</td>
                  <td>
                    {signed(x.difference.point)}{' '}
                    <span className="ci-text">
                      [{signed(x.difference.ci[0])}, {signed(x.difference.ci[1])}]
                    </span>{' '}
                    {x.difference.ci[0] > 0 ? '' : <span className="fail">interval includes 0</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  )
}
