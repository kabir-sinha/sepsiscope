// Hourly line chart in plain SVG. The SVG is drawn at its real on-screen width, so all text
// is true pixels (12 px minimum). All charts share the x-axis "Hours since ICU admission",
// one selected hour (solid line) and one hover hour (dashed preview).
import type { MouseEvent } from 'react'
import { display, hourTicks, niceAxis, thresholdLabelPlacement } from './chartMath'
import { useTooltip, useWidth } from './hooks'
import { Legend, TableToggle } from './ui'
import type { LegendItem } from './ui'

export type Series = { label: string; values: (number | null)[]; color: string; dashed?: boolean }

type Props = {
  title: string
  help: string
  series: Series[] // first = main series
  totalHours: number
  revealed: number
  hour: number | null // selected hour
  hover: number | null // preview only
  onHover: (hour: number | null) => void
  onSelect?: (hour: number) => void
  yLabel: string
  unit: string
  format: (v: number) => string
  tickFormat?: (v: number) => string // axis labels (round steps); defaults to a readable number
  yMin?: number
  yMax?: number
  threshold?: { value: number; label: string }
  normal?: [number, number]
  window?: [number, number] | null
  onset?: number | null
  alerts?: number[]
  height?: number
  legend?: boolean
}

const PAD = { left: 62, right: 14, top: 14, bottom: 42 }

export function LineChart(p: Props) {
  const [ref, W] = useWidth<HTMLDivElement>()
  const tip = useTooltip()
  const H = p.height ?? 240
  const n = Math.max(p.totalHours - 1, 1)
  const main = p.series[0]
  const extra = [p.threshold?.value, p.normal?.[0], p.normal?.[1]].filter((v): v is number => v !== undefined)
  const all = p.series.flatMap((s) => s.values.filter((v): v is number => v !== null)).concat(extra)
  const lo = p.yMin ?? (all.length ? Math.min(...all) : 0)
  const hi = p.yMax ?? (all.length ? Math.max(...all) : 1)
  // Round axis: whole nice steps (risk 0/2/4/6 %, vitals 60/80/100 ...).
  const axis = niceAxis(lo, hi, H >= 230 ? 4 : 3)
  const yLo = p.yMin ?? axis.min
  const yHi = p.yMax ?? axis.max
  const plotW = Math.max(W - PAD.left - PAD.right, 50)
  const x = (h: number) => PAD.left + (h / n) * plotW
  const y = (v: number) => PAD.top + (1 - (v - yLo) / (yHi - yLo)) * (H - PAD.top - PAD.bottom)

  const path = (values: (number | null)[]) => {
    let d = ''
    let pen = false
    for (let h = 0; h <= Math.min(p.revealed, values.length - 1); h++) {
      const v = values[h]
      if (v === null) {
        pen = false
        continue
      }
      d += `${pen ? 'L' : 'M'}${x(h).toFixed(1)},${y(v).toFixed(1)} `
      pen = true
    }
    return d
  }
  const xTicks = hourTicks(n, Math.max(2, Math.floor(plotW / 140)))
  const yTicks = (p.yMax !== undefined ? niceAxis(yLo, yHi, H >= 230 ? 4 : 3).ticks : axis.ticks).filter(
    (v) => v >= yLo - 1e-12 && v <= yHi + 1e-12,
  )
  const tickLabel = p.tickFormat ?? ((v: number) => display(v))
  const alerts = (p.alerts ?? []).filter((h) => h <= p.revealed)
  const hv = p.hover !== null && p.hover <= p.revealed ? p.hover : null

  function hourAt(e: MouseEvent<SVGSVGElement>): number {
    const box = e.currentTarget.getBoundingClientRect()
    return Math.max(0, Math.min(n, Math.round(((e.clientX - box.left - PAD.left) / plotW) * n)))
  }
  function onMove(e: MouseEvent<SVGSVGElement>) {
    const h = Math.min(hourAt(e), p.revealed)
    p.onHover(h)
    tip.show(
      e,
      <>
        <strong>Hovering hour {h}</strong>
        {p.series.map((s) => (
          <div key={s.label}>
            {s.label}: {s.values[h] === null || s.values[h] === undefined ? 'not measured yet' : `${p.format(s.values[h] as number)}${p.unit}`}
          </div>
        ))}
        {p.alerts?.includes(h) && <div>Alert hour</div>}
      </>,
    )
  }

  const legend: LegendItem[] = p.series.map((s) => ({ label: s.label, kind: s.dashed ? 'dash' : 'line', color: s.color }))
  if (p.normal) legend.push({ label: 'Normal range (0 NEWS2 points)', kind: 'band', color: 'var(--ok)' })
  if (p.threshold) legend.push({ label: p.threshold.label, kind: 'dash', color: 'var(--threshold)' })
  if (p.window) legend.push({ label: 'Early-warning window', kind: 'band', color: 'var(--window)' })
  if (p.onset !== undefined && p.onset !== null) legend.push({ label: 'Sepsis onset', kind: 'line', color: 'var(--onset)' })
  if (p.alerts) legend.push({ label: 'Alert hour', kind: 'dot', color: 'var(--raise)' })

  const rows = Array.from({ length: Math.min(p.revealed, p.totalHours - 1) + 1 }, (_, h) => [
    h,
    ...p.series.map((s) => (s.values[h] === null || s.values[h] === undefined ? 'not measured' : `${p.format(s.values[h] as number)}${p.unit}`)),
    ...(p.alerts ? [p.alerts.includes(h) ? 'alert' : ''] : []),
  ])

  return (
    <figure className="chart">
      <figcaption>
        <span className="chart-title">{p.title}</span>
        <span className="chart-help">{p.help}</span>
      </figcaption>
      {p.legend !== false && <Legend items={legend} />}
      <div ref={ref} className="plot">
        <svg
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`${p.title}. ${p.help}`}
          onMouseMove={onMove}
          onMouseLeave={() => {
            p.onHover(null)
            tip.hide()
          }}
          onClick={(e) => p.onSelect?.(Math.min(hourAt(e), p.revealed))}
        >
          {p.normal && (
            <rect className="normal-band" x={PAD.left} width={plotW} y={y(p.normal[1])} height={Math.max(0, y(p.normal[0]) - y(p.normal[1]))} />
          )}
          {p.window && (
            <g>
              <rect
                className="window-band"
                x={x(p.window[0])}
                width={Math.max(3, x(Math.min(p.window[1], n)) - x(p.window[0]))}
                y={PAD.top}
                height={H - PAD.top - PAD.bottom}
              />
              {H >= 200 && (
                <text className="band-label" x={x(p.window[0]) + 4} y={PAD.top + 15}>
                  Early-warning window
                </text>
              )}
            </g>
          )}
          {yTicks.map((v) => (
            <g key={v}>
              <line className="grid" x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} />
              <text className="tick" x={PAD.left - 6} y={y(v) + 4} textAnchor="end">
                {tickLabel(v)}
              </text>
            </g>
          ))}
          {xTicks.map((h) => (
            <text key={h} className="tick" x={x(h)} y={H - PAD.bottom + 17} textAnchor="middle">
              {h}
            </text>
          ))}
          <text className="axis-label" x={PAD.left + plotW / 2} y={H - 6} textAnchor="middle">
            Hours since ICU admission
          </text>
          <text className="axis-label" transform={`translate(14 ${(PAD.top + H - PAD.bottom) / 2}) rotate(-90)`} textAnchor="middle">
            {p.yLabel}
          </text>
          {p.threshold && (
            <g>
              <line className="threshold" x1={PAD.left} x2={W - PAD.right} y1={y(p.threshold.value)} y2={y(p.threshold.value)} />
              {(() => {
                // Keep the label clear of the onset and selected-hour lines.
                const verticals = [
                  ...(p.onset !== undefined && p.onset !== null && p.onset <= n ? [x(p.onset)] : []),
                  ...(p.hour !== null && p.hour <= p.revealed ? [x(p.hour)] : []),
                ]
                const at = thresholdLabelPlacement({
                  label: p.threshold.label,
                  left: PAD.left,
                  right: W - PAD.right,
                  lineY: y(p.threshold.value),
                  top: PAD.top,
                  verticals,
                })
                return (
                  <text className="threshold-label" x={at.x} y={at.y} textAnchor={at.anchor}>
                    {p.threshold.label}
                  </text>
                )
              })()}
            </g>
          )}
          {p.onset !== undefined && p.onset !== null && p.onset <= n && (
            <g>
              <line className="onset" x1={x(p.onset)} x2={x(p.onset)} y1={PAD.top} y2={H - PAD.bottom} />
              <text className="onset-label" x={x(p.onset) + 4} y={H - PAD.bottom - 6}>
                Onset h{p.onset}
              </text>
            </g>
          )}
          {p.series
            .slice()
            .reverse()
            .map((s) => (
              <path key={s.label} className={s.dashed ? 'series dashed' : 'series'} d={path(s.values)} stroke={s.color} />
            ))}
          {alerts.map((h) => {
            const v = main.values[h]
            if (v === null) return null
            return (
              <circle
                key={h}
                className={h === p.hour ? 'alert-dot selected' : 'alert-dot'}
                cx={x(h)}
                cy={y(v)}
                r={h === p.hour ? 7 : 5}
                tabIndex={p.onSelect ? 0 : -1}
                role={p.onSelect ? 'button' : undefined}
                aria-label={`Alert at hour ${h}: ${p.format(v)}${p.unit}. Select this hour.`}
                onClick={(e) => {
                  e.stopPropagation()
                  p.onSelect?.(h)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    p.onSelect?.(h)
                  }
                }}
              />
            )
          })}
          {p.hour !== null && p.hour <= p.revealed && (
            <line className="selected-line" x1={x(p.hour)} x2={x(p.hour)} y1={PAD.top} y2={H - PAD.bottom} />
          )}
          {hv !== null && hv !== p.hour && <line className="hover-line" x1={x(hv)} x2={x(hv)} y1={PAD.top} y2={H - PAD.bottom} />}
        </svg>
      </div>
      <TableToggle
        caption={`${p.title}, hour by hour`}
        columns={['Hour', ...p.series.map((s) => s.label), ...(p.alerts ? ['Alert'] : [])]}
        rows={rows}
      />
    </figure>
  )
}
