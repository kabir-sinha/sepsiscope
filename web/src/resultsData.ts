// Shared data helpers for the Results tab and the headline strip (no components here).
import { useEffect, useState } from 'react'
import type { ResultRow, Results as ResultsDoc } from './types'

export const ORDER = ['lgbm', 'lr', 'news2', 'sirs', 'qsofa']
export const NAMES: Record<string, string> = {
  lgbm: 'SepsiScope (LightGBM)',
  lr: 'Logistic regression',
  news2: 'Modified NEWS2 (max 17)',
  sirs: 'SIRS (max 4)',
  qsofa: 'Modified qSOFA (max 2)',
}
export const DIRS: Record<string, string> = { A2B: 'Trained on A → tested on B', B2A: 'Trained on B → tested on A' }
export const pct = (v: number) => `${(v * 100).toFixed(1)} %`
export const ci = (c: [number, number], f = (v: number) => v.toFixed(3)) => `${f(c[0])}–${f(c[1])}`

export function useResults(): [ResultsDoc | null, string | null] {
  const [doc, setDoc] = useState<ResultsDoc | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    fetch('/api/results')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setDoc)
      .catch(() => setError('Results not reachable.'))
  }, [])
  return [doc, error]
}

export const rowsFor = (doc: ResultsDoc, d: string) =>
  ORDER.map((m) => doc.rows.find((r) => r.model === m && r.direction === d)).filter((r): r is ResultRow => r !== undefined)
