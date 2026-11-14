// Hourly line chart in plain SVG. All charts in the replay share one x-axis
// ("Hours since ICU admission") and one hover hour, so their crosshairs move together.
import type { MouseEvent } from 'react'

export type LegendItem = { label: string; kind: 'line' | 'dash' | 'dot' | 'band'; color: string }

type Props = {
  title: string
  help: string
  values: (number | null)[]
  totalHours: number
  revealed: number // last hour shown (replay)
  hover: number | null
  onHover: (hour: number | null) => void
  onPick?: (hour: number) => void
  picked?: number | null
  color: string
  yLabel: string
  format: (v: number) => string
  yMin?: number
  yMax?: number
  threshold?: { value: number; label: string }
  normal?: [number, number] // shaded normal range (y)
  window?: [number, number] | null // shaded early-warning window (x)
  onset?: number | null
  alerts?: number[]
  height?: number
  compact?: boolean
}

const W = 760
const PAD = { left: 64, right: 16, top: 14, bottom: 40 }

export function LineChart(p: Props) {
  const H = p.height ?? 220
  const n = Math.max(p.totalHours - 1, 1)
  const seen = p.values.slice(0, p.revealed + 1).filter((v): v is number => v !== null)
  const extra = [p.threshold?.value, p.normal?.[0], p.normal?.[1]].filter(
    (v): v is number => v !== undefined,
  )
  const all = p.values.filter((v): v is number => v !== null).concat(extra)
  const lo = p.yMin ?? (all.length ? Math.min(...all) : 0)
  const hiRaw = p.yMax ?? (all.length ? Math.max(...all) : 1)
  const span = hiRaw - lo || 1
  const yLo = p.yMin ?? lo - span * 0.08
  const yHi = p.yMax ?? hiRaw + span * 0.08
  const x = (h: number) => PAD.left + (h / n) * (W - PAD.left - PAD.right)
  const y = (v: number) => PAD.top + (1 - (v - yLo) / (yHi - yLo)) * (H - PAD.top - PAD.bottom)

  let d = ''
  let pen = false
  for (let h = 0; h <= Math.min(p.revealed, p.values.length - 1); h++) {
    const v = p.values[h]
    if (v === null) {
      pen = false
      continue
    }
    d += `${pen ? 'L' : 'M'}${x(h).toFixed(1)},${y(v).toFixed(1)} `
    pen = true
  }
  const xTicks = Array.from(new Set([0, Math.round(n / 4), Math.round(n / 2), Math.round((3 * n) / 4), n]))
  const yTicks = [yLo + (yHi - yLo) * 0.1, (yLo + yHi) / 2, yHi - (yHi - yLo) * 0.1]
  const alerts = (p.alerts ?? []).filter((h) => h <= p.revealed)
  const hv = p.hover !== null && p.hover <= p.revealed ? p.hover : null
  const hvValue = hv !== null ? p.values[hv] : null

  function hourAt(e: MouseEvent<SVGSVGElement>): number {
    const box = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - box.left) / box.width) * W
    return Math.max(0, Math.min(n, Math.round(((px - PAD.left) / (W - PAD.left - PAD.right)) * n)))
  }

  const legend: LegendItem[] = [{ label: p.compact ? 'Last measured value' : p.title, kind: 'line', color: p.color }]
  if (p.normal) legend.push({ label: 'Normal range (NEWS2 0 points)', kind: 'band', color: 'var(--ok)' })
  if (p.threshold) legend.push({ label: p.threshold.label, kind: 'dash', color: 'var(--threshold)' })
  if (p.window) legend.push({ label: 'Early-warning window (12 h)', kind: 'band', color: 'var(--window)' })
  if (p.onset !== undefined && p.onset !== null) legend.push({ label: 'Sepsis onset', kind: 'line', color: 'var(--onset)' })
  if (p.alerts) legend.push({ label: 'Alert hour', kind: 'dot', color: 'var(--alert)' })

  return (
    <figure className={p.compact ? 'chart compact' : 'chart'}>
      <figcaption>
        <span className="chart-title">{p.title}</span>
        <span className="chart-help">{p.help}</span>
      </figcaption>
      <Legend items={legend} />
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${p.title}. ${p.help}`}
        onMouseMove={(e) => p.onHover(hourAt(e))}
        onMouseLeave={() => p.onHover(null)}
        onClick={(e) => p.onPick?.(Math.min(hourAt(e), p.revealed))}
      >
        <rect className="plot-bg" x={PAD.left} y={PAD.top} width={W - PAD.left - PAD.right} height={H - PAD.top - PAD.bottom} />
        {p.normal && (
          <rect
            className="normal-band"
            x={PAD.left}
            width={W - PAD.left - PAD.right}
            y={y(p.normal[1])}
            height={Math.max(0, y(p.normal[0]) - y(p.normal[1]))}
          />
        )}
        {p.window && (
          <g>
            <rect
              className="window-band"
              x={x(p.window[0])}
              width={Math.max(2, x(Math.min(p.window[1], n)) - x(p.window[0]))}
              y={PAD.top}
              height={H - PAD.top - PAD.bottom}
            />
            {!p.compact && (
              <text className="band-label" x={x(p.window[0]) + 4} y={PAD.top + 14}>
                Early-warning window
              </text>
            )}
          </g>
        )}
        {yTicks.map((v) => (
          <g key={v}>
            <line className="grid" x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} />
            <text className="tick" x={PAD.left - 6} y={y(v) + 4} textAnchor="end">
              {p.format(v)}
            </text>
          </g>
        ))}
        {xTicks.map((h) => (
          <text key={h} className="tick" x={x(h)} y={H - PAD.bottom + 16} textAnchor="middle">
            {h}
          </text>
        ))}
        <text className="axis-label" x={(PAD.left + W - PAD.right) / 2} y={H - 6} textAnchor="middle">
          Hours since ICU admission
        </text>
        <text className="axis-label" transform={`translate(14 ${(PAD.top + H - PAD.bottom) / 2}) rotate(-90)`} textAnchor="middle">
          {p.yLabel}
        </text>
        {p.threshold && (
          <g>
            <line className="threshold" x1={PAD.left} x2={W - PAD.right} y1={y(p.threshold.value)} y2={y(p.threshold.value)} />
            {!p.compact && (
              <text className="threshold-label" x={W - PAD.right - 4} y={y(p.threshold.value) - 5} textAnchor="end">
                {p.threshold.label}
              </text>
            )}
          </g>
        )}
        {p.onset !== undefined && p.onset !== null && p.onset <= n && (
          <g>
            <line className="onset" x1={x(p.onset)} x2={x(p.onset)} y1={PAD.top} y2={H - PAD.bottom} />
            {!p.compact && (
              <text className="onset-label" x={x(p.onset) + 4} y={H - PAD.bottom - 6}>
                Onset (hour {p.onset})
              </text>
            )}
          </g>
        )}
        <path className="series" d={d} stroke={p.color} />
        {alerts.map((h) => {
          const v = p.values[h]
          if (v === null) return null
          return (
            <circle
              key={h}
              className={h === p.picked ? 'alert-dot picked' : 'alert-dot'}
              cx={x(h)}
              cy={y(v)}
              r={h === p.picked ? 7 : 5}
              tabIndex={p.onPick ? 0 : -1}
              role={p.onPick ? 'button' : undefined}
              aria-label={`Alert at hour ${h}: ${p.format(v)}. Show reasons.`}
              onClick={(e) => {
                e.stopPropagation()
                p.onPick?.(h)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  p.onPick?.(h)
                }
              }}
            />
          )
        })}
        {p.picked !== undefined && p.picked !== null && p.picked <= p.revealed && (
          <line className="picked-line" x1={x(p.picked)} x2={x(p.picked)} y1={PAD.top} y2={H - PAD.bottom} />
        )}
        {hv !== null && (
          <g pointerEvents="none">
            <line className="crosshair" x1={x(hv)} x2={x(hv)} y1={PAD.top} y2={H - PAD.bottom} />
            <g transform={`translate(${Math.min(x(hv) + 8, W - 150)} ${PAD.top + 4})`}>
              <rect className="tip-bg" width="140" height="22" rx="4" />
              <text className="tip-text" x="8" y="15">
                h{hv}: {hvValue === null ? 'not measured' : p.format(hvValue)}
              </text>
            </g>
          </g>
        )}
        {seen.length === 0 && (
          <text className="tick" x={W / 2} y={H / 2} textAnchor="middle">
            No value measured yet
          </text>
        )}
      </svg>
    </figure>
  )
}

export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="legend" aria-label="Legend">
      {items.map((it) => (
        <li key={it.label}>
          <svg width="22" height="12" aria-hidden="true">
            {it.kind === 'line' && <line x1="1" x2="21" y1="6" y2="6" stroke={it.color} strokeWidth="3" />}
            {it.kind === 'dash' && <line x1="1" x2="21" y1="6" y2="6" stroke={it.color} strokeWidth="2" strokeDasharray="4 3" />}
            {it.kind === 'dot' && <circle cx="11" cy="6" r="5" fill={it.color} />}
            {it.kind === 'band' && <rect x="1" y="1" width="20" height="10" fill={it.color} opacity="0.3" />}
          </svg>
          {it.label}
        </li>
      ))}
    </ul>
  )
}
