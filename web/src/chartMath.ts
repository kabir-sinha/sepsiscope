// Round axis ticks and readable numbers for the charts (no components here).

// A "nice" step (1, 2 or 5 × 10^k) so that span / step gives about `target` intervals.
export function niceStep(span: number, target: number): number {
  const raw = span / Math.max(target, 1)
  const mag = 10 ** Math.floor(Math.log10(raw))
  const f = raw / mag
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * mag
}

// Domain rounded out to whole steps, and the ticks inside it.
export function niceAxis(lo: number, hi: number, target = 4): { min: number; max: number; ticks: number[] } {
  if (hi <= lo) hi = lo + 1
  const step = niceStep(hi - lo, target)
  const min = Math.floor(lo / step) * step
  const max = Math.ceil(hi / step) * step
  const ticks: number[] = []
  for (let v = min; v <= max + step / 2; v += step) ticks.push(Number(v.toPrecision(12)))
  return { min, max, ticks }
}

// Hour axis: 0, 6, 12, 24 ... steps that people count in.
const HOUR_STEPS = [1, 2, 3, 6, 12, 24, 48, 96]
export function hourTicks(lastHour: number, maxTicks: number): number[] {
  const step = HOUR_STEPS.find((s) => lastHour / s <= maxTicks) ?? 96
  const out: number[] = []
  for (let h = 0; h <= lastHour; h += step) out.push(h)
  return out
}

// Readable value: 1 decimal from 10 upwards (37.2, not 37.17), else up to 2 decimals.
export function display(v: number): string {
  return String(Number(v.toFixed(Math.abs(v) >= 10 ? 1 : 2)))
}

// Number of decimals a tick step needs (0.02 → 2, 5 → 0).
export function stepDecimals(step: number): number {
  return Math.max(0, -Math.floor(Math.log10(step) + 1e-9))
}

// --- Label placement -------------------------------------------------------------------
// Every text label inside a chart (alert threshold, early-warning window, onset) is placed by
// `placeLabel`: it tries candidate spots in order and takes the first whose text box stays in
// the plot and touches no obstacle (vertical lines, plotted line segments, alert dots, labels
// already placed). If every spot is blocked it returns null and the label is not drawn: each
// of these labels is also in the chart legend, so nothing is lost and nothing is covered.
// Text width is estimated (13 px bold ≈ 7.8 px per char).

export type Pt = { x: number; y: number }
export type Box = { x0: number; x1: number; y0: number; y1: number }
export type Obstacles = {
  verticals?: number[] // x of full-height vertical lines
  segments?: [Pt, Pt][] // plotted lines
  dots?: (Pt & { r: number })[] // alert dots
  boxes?: Box[] // labels already placed
}
export type Spot = { x: number; y: number; anchor: 'start' | 'end' }

export const CHAR_W = 7.8
const TEXT_H = 13

// Box of a text label drawn at (x, y) as an SVG baseline with the given anchor.
export function labelBox(label: string, s: Spot, charW = CHAR_W): Box {
  const w = label.length * charW
  const x0 = s.anchor === 'end' ? s.x - w : s.x
  return { x0, x1: x0 + w, y0: s.y - TEXT_H + 2, y1: s.y + 3 }
}

function grow(b: Box, g: number): Box {
  return { x0: b.x0 - g, x1: b.x1 + g, y0: b.y0 - g, y1: b.y1 + g }
}

// Does segment a-b cross or touch box b? (Liang–Barsky clipping.)
export function segmentHitsBox(a: Pt, c: Pt, b: Box): boolean {
  let t0 = 0
  let t1 = 1
  const dx = c.x - a.x
  const dy = c.y - a.y
  const edges: [number, number][] = [
    [-dx, a.x - b.x0],
    [dx, b.x1 - a.x],
    [-dy, a.y - b.y0],
    [dy, b.y1 - a.y],
  ]
  for (const [pp, q] of edges) {
    if (pp === 0) {
      if (q < 0) return false
    } else {
      const r = q / pp
      if (pp < 0) t0 = Math.max(t0, r)
      else t1 = Math.min(t1, r)
      if (t0 > t1) return false
    }
  }
  return true
}

export function hits(box: Box, o: Obstacles, gap = 4): number {
  const b = grow(box, gap)
  let n = 0
  for (const v of o.verticals ?? []) if (v >= b.x0 && v <= b.x1) n++
  for (const [a, c] of o.segments ?? []) if (segmentHitsBox(a, c, b)) n++
  for (const o2 of o.boxes ?? []) if (o2.x0 <= b.x1 && o2.x1 >= b.x0 && o2.y0 <= b.y1 && o2.y1 >= b.y0) n++
  for (const d of o.dots ?? []) {
    const nx = Math.max(b.x0, Math.min(d.x, b.x1))
    const ny = Math.max(b.y0, Math.min(d.y, b.y1))
    if ((nx - d.x) ** 2 + (ny - d.y) ** 2 <= d.r * d.r) n++
  }
  return n
}

// First candidate spot inside `bounds` with no hits, or null when every spot is blocked.
export function placeLabel(label: string, candidates: Spot[], o: Obstacles, bounds?: Box): Spot | null {
  for (const s of candidates) {
    const box = labelBox(label, s)
    if (bounds && (box.x0 < bounds.x0 || box.x1 > bounds.x1 || box.y0 < bounds.y0 || box.y1 > bounds.y1)) continue
    if (hits(box, o) === 0) return s
  }
  return null
}

// Candidate spots for the threshold label: above the line at the right end, then the left
// end, then below the line (right, left), then above/below the middle.
export function thresholdCandidates(opts: { left: number; right: number; lineY: number; top: number }): Spot[] {
  const above = opts.lineY - 6 >= opts.top + 12 ? opts.lineY - 6 : opts.lineY + 16
  const below = opts.lineY + 16
  const mid = (opts.left + opts.right) / 2
  return [
    { x: opts.right - 4, y: above, anchor: 'end' },
    { x: opts.left + 4, y: above, anchor: 'start' },
    { x: opts.right - 4, y: below, anchor: 'end' },
    { x: opts.left + 4, y: below, anchor: 'start' },
    { x: mid, y: above, anchor: 'start' },
    { x: mid, y: below, anchor: 'start' },
  ]
}
