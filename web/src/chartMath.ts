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
