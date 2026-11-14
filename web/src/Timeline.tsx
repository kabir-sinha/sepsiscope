// Hourly line chart in plain SVG: values, threshold line, alert markers, onset marker.
type Props = {
  title: string
  values: number[]
  threshold: number
  alerts: number[]
  onset: number | null
  selected: number | null
  onSelect?: (hour: number) => void
  maxValue?: number
  format: (v: number) => string
}

const W = 720
const H = 180
const PAD = { left: 48, right: 12, top: 12, bottom: 28 }

export function Timeline(props: Props) {
  const { title, values, threshold, alerts, onset, selected, onSelect, format } = props
  const top = props.maxValue ?? Math.max(threshold * 1.6, ...values) * 1.05
  const n = Math.max(values.length - 1, 1)
  const x = (h: number) => PAD.left + (h / n) * (W - PAD.left - PAD.right)
  const y = (v: number) => PAD.top + (1 - v / top) * (H - PAD.top - PAD.bottom)
  const path = values.map((v, h) => `${h === 0 ? 'M' : 'L'}${x(h).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const ticks = [0, Math.round(n / 4), Math.round(n / 2), Math.round((3 * n) / 4), n]

  return (
    <figure className="chart">
      <figcaption>{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
        <line className="axis" x1={PAD.left} x2={W - PAD.right} y1={y(0)} y2={y(0)} />
        {ticks.map((h) => (
          <text key={h} className="tick" x={x(h)} y={H - 8} textAnchor="middle">
            {h} h
          </text>
        ))}
        <text className="tick" x={PAD.left - 6} y={y(threshold) + 4} textAnchor="end">
          {format(threshold)}
        </text>
        <line className="threshold" x1={PAD.left} x2={W - PAD.right} y1={y(threshold)} y2={y(threshold)} />
        {onset !== null && onset <= n && (
          <g>
            <line className="onset" x1={x(onset)} x2={x(onset)} y1={PAD.top} y2={y(0)} />
            <text className="onset-label" x={x(onset) + 4} y={PAD.top + 10}>
              onset
            </text>
          </g>
        )}
        <path className="series" d={path} />
        {alerts.map((h) => (
          <circle
            key={h}
            className={h === selected ? 'alert selected' : 'alert'}
            cx={x(h)}
            cy={y(values[h])}
            r={h === selected ? 6 : 4}
            onClick={onSelect ? () => onSelect(h) : undefined}
          >
            <title>{`hour ${h}: ${format(values[h])}`}</title>
          </circle>
        ))}
      </svg>
    </figure>
  )
}
