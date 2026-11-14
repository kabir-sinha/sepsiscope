// "Why did it alert?": the model's top 5 reasons at the selected hour, as one list.
// Each row: the full plain-English sentence, an inline bar (orange-red raises the risk,
// blue lowers it) and the value with its unit. Raw log-odds appear only in the tooltip.
import { display } from './chartMath'
import { useTooltip } from './hooks'
import type { Reason } from './types'

type Props = { hour: number | null; reasons: Reason[]; risk: number | null; alerted: boolean; threshold: number }

export function WhyPanel({ hour, reasons, risk, alerted, threshold }: Props) {
  const tip = useTooltip()
  if (hour === null) {
    return (
      <section className="panel why" aria-labelledby="why-title">
        <h3 id="why-title">Why did it alert?</h3>
        <p className="help">Select an hour (slider, ←/→, or click a chart or alert dot) to see the model's top 5 reasons.</p>
      </section>
    )
  }
  const max = Math.max(...reasons.map((r) => Math.abs(r.contribution)), 0.01)
  return (
    <section className="panel why" aria-labelledby="why-title">
      <h3 id="why-title">{alerted ? `Why did it alert at hour ${hour}?` : `What drove the risk at hour ${hour}?`}</h3>
      <p className="help">
        Risk <span className="num">{risk === null ? '—' : `${(risk * 100).toFixed(2)} %`}</span>,{' '}
        {alerted ? 'above' : 'below'} the alert threshold of <span className="num">{(threshold * 100).toFixed(2)} %</span>
        {alerted ? ' — an alert.' : ' — no alert.'} These explain the model, not the patient's illness.
      </p>
      <ul className="legend" aria-label="Legend">
        <li>
          <span className="swatch raise" aria-hidden="true" /> <span>raises the risk</span>
        </li>
        <li>
          <span className="swatch lower" aria-hidden="true" /> <span>lowers the risk</span>
        </li>
        <li>
          <span className="tag">process</span> <span>how often staff checked, not the value</span>
        </li>
      </ul>
      <ol className="reasons">
        {reasons.map((r) => {
          const up = r.contribution > 0
          const pct = (Math.abs(r.contribution) / max) * 100
          return (
            <li
              key={r.feature}
              onMouseMove={(e) =>
                tip.show(e, <span>{`${r.label}: ${up ? '+' : ''}${r.contribution.toFixed(3)} log-odds (model's internal scale)`}</span>)
              }
              onMouseLeave={tip.hide}
            >
              <p className="reason-sentence">
                <span className={up ? 'arrow raise-text' : 'arrow lower-text'} aria-label={up ? 'raises' : 'lowers'}>
                  {up ? '▲' : '▼'}
                </span>{' '}
                {r.sentence}
                {r.process && <span className="tag">process</span>}
              </p>
              <div className="reason-row">
                <div className="bar-track" aria-hidden="true">
                  <div className={up ? 'bar raise' : 'bar lower'} style={{ width: `${Math.max(pct, 3)}%` }} />
                </div>
                <span className="num reason-value">
                  {r.value === null ? 'not measured yet' : `${display(r.value)} ${r.unit}`.trim()}
                </span>
              </div>
              {r.process && <p className="help small">Reflects how often staff checked, not the value itself.</p>}
            </li>
          )
        })}
      </ol>
      {reasons.some((r) => r.value === null) && (
        <p className="help small">"Not measured yet": a missing value is itself information to the model.</p>
      )}
    </section>
  )
}
