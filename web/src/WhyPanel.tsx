// "Why did it alert?": the top 5 reasons for one hour as a horizontal bar chart.
// Bars pointing right (vermillion) raised the risk; bars pointing left (blue) lowered it.
import type { Reason } from './types'

type Props = { hour: number | null; reasons: Reason[]; risk: number | null; alerted: boolean }

export function WhyPanel({ hour, reasons, risk, alerted }: Props) {
  if (hour === null) {
    return (
      <section className="panel why" aria-labelledby="why-title">
        <h3 id="why-title">Why did it alert?</h3>
        <p className="help">Click any hour on a chart, or an alert dot, to see the model's top 5 reasons.</p>
      </section>
    )
  }
  const max = Math.max(...reasons.map((r) => Math.abs(r.contribution)), 0.01)
  const W = 520
  const mid = W / 2
  const rowH = 30
  return (
    <section className="panel why" aria-labelledby="why-title">
      <h3 id="why-title">
        Why {alerted ? 'did it alert' : 'this risk'} at hour {hour}?
      </h3>
      <p className="help">
        Predicted risk {risk === null ? '—' : `${(risk * 100).toFixed(1)} %`}
        {alerted ? ' — above the alert threshold.' : ' — below the alert threshold, no alert.'} The
        five features that moved the model most at this hour. These explain the model, not the
        patient's illness.
      </p>
      <ul className="legend" aria-label="Legend">
        <li>
          <span className="swatch" style={{ background: 'var(--alert)' }} /> raises the risk
        </li>
        <li>
          <span className="swatch" style={{ background: 'var(--risk)' }} /> lowers the risk
        </li>
        <li>
          <span className="tag">process</span> how often staff checked, not the value itself
        </li>
      </ul>
      <svg viewBox={`0 0 ${W} ${reasons.length * rowH + 8}`} role="img" aria-label="Top 5 reasons as bars">
        <line className="axis" x1={mid} x2={mid} y1={0} y2={reasons.length * rowH + 8} />
        {reasons.map((r, i) => {
          const len = (Math.abs(r.contribution) / max) * (mid - 10)
          const up = r.contribution > 0
          return (
            <g key={r.feature} transform={`translate(0 ${i * rowH + 4})`}>
              <rect
                x={up ? mid : mid - len}
                y={4}
                width={Math.max(len, 2)}
                height={rowH - 10}
                fill={up ? 'var(--alert)' : 'var(--risk)'}
              >
                <title>{`${r.label}: ${r.contribution > 0 ? '+' : ''}${r.contribution.toFixed(3)} log-odds`}</title>
              </rect>
              <text className="bar-label" x={up ? mid - 6 : mid + 6} y={rowH / 2 + 3} textAnchor={up ? 'end' : 'start'}>
                {i + 1}. {short(r.label)}
              </text>
            </g>
          )
        })}
      </svg>
      <ol className="reasons">
        {reasons.map((r) => (
          <li key={r.feature}>
            <span className={r.contribution > 0 ? 'up' : 'down'}>{r.contribution > 0 ? '▲' : '▼'}</span>{' '}
            {r.sentence}
            {r.process && (
              <span className="tag" title="Reflects how often staff checked, not the value itself">
                process
              </span>
            )}
            {r.process && <span className="help"> Reflects how often staff checked, not the value itself.</span>}
          </li>
        ))}
      </ol>
    </section>
  )
}

function short(label: string): string {
  return label.length > 34 ? `${label.slice(0, 32)}…` : label
}
