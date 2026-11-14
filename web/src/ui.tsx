// Shared UI pieces: measured width (so SVG text is drawn at true pixel size), a single
// pointer-following tooltip, legends and the "Show as table" disclosure.
import { useCallback, useEffect, useState } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { TipContext } from './hooks'

type Tip = { x: number; y: number; content: ReactNode } | null
// One tooltip for the whole page. It follows the pointer (fixed position, offset below-right,
// flipped near the window edges), ignores the pointer itself and closes on leave.
export function TooltipProvider({ children }: { children: ReactNode }) {
  const [tip, setTip] = useState<Tip>(null)
  const show = useCallback((e: MouseEvent, content: ReactNode) => {
    setTip({ x: e.clientX, y: e.clientY, content })
  }, [])
  const hide = useCallback(() => setTip(null), [])
  useEffect(() => {
    const close = () => setTip(null)
    window.addEventListener('scroll', close, true)
    window.addEventListener('blur', close)
    return () => {
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('blur', close)
    }
  }, [])
  const left = tip ? (tip.x + 260 > window.innerWidth ? tip.x - 252 : tip.x + 14) : 0
  const top = tip ? (tip.y + 90 > window.innerHeight ? tip.y - 70 : tip.y + 18) : 0
  return (
    <TipContext.Provider value={{ show, hide }}>
      {children}
      {tip && (
        <div className="tip" role="tooltip" style={{ left, top }}>
          {tip.content}
        </div>
      )}
    </TipContext.Provider>
  )
}


// 'bar' = solid swatch identical to a bar's fill; 'band' = the translucent fill of a shaded area.
export type LegendItem = { label: string; kind: 'line' | 'dash' | 'dot' | 'band' | 'bar'; color: string }

export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="legend" aria-label="Legend">
      {items.map((it) => (
        <li key={it.label}>
          <svg width="24" height="14" aria-hidden="true" className="swatch-svg">
            {it.kind === 'line' && <line x1="1" x2="23" y1="7" y2="7" stroke={it.color} strokeWidth="3" />}
            {it.kind === 'dash' && (
              <line x1="1" x2="23" y1="7" y2="7" stroke={it.color} strokeWidth="2.5" strokeDasharray="5 3" />
            )}
            {it.kind === 'dot' && <circle cx="12" cy="7" r="5" fill={it.color} />}
            {it.kind === 'band' && <rect x="1" y="1" width="22" height="12" fill={it.color} opacity="0.35" />}
            {it.kind === 'bar' && <rect x="1" y="1" width="22" height="12" fill={it.color} />}
          </svg>
          <span>{it.label}</span>
        </li>
      ))}
    </ul>
  )
}

export function TableToggle({ caption, columns, rows }: { caption: string; columns: string[]; rows: (string | number)[][] }) {
  return (
    <details className="as-table">
      <summary>Show as table</summary>
      <div className="table-wrap">
        <table>
          <caption>{caption}</caption>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c} scope="col">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => (j === 0 ? <th key={j} scope="row">{c}</th> : <td key={j}>{c}</td>))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
