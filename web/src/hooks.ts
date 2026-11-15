// Shared hooks (no components here): measured element width and the page tooltip API.
import { createContext, useContext, useLayoutEffect, useRef, useState } from 'react'
import type { MouseEvent, ReactNode } from 'react'

// Measured before the first paint (layout effect), so a chart is never drawn at the
// fallback width on a narrow screen; a ResizeObserver keeps it current afterwards.
export function useWidth<T extends HTMLElement>(fallback = 700): [React.RefObject<T | null>, number] {
  const ref = useRef<T | null>(null)
  const [width, setWidth] = useState(fallback)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const now = Math.floor(el.getBoundingClientRect().width)
    if (now > 0) setWidth(now)
    const obs = new ResizeObserver((entries) => {
      const w = Math.floor(entries[0].contentRect.width)
      if (w > 0) setWidth(w)
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])
  return [ref, width]
}

export type TipApi = { show: (e: MouseEvent, content: ReactNode) => void; hide: () => void }
export const TipContext = createContext<TipApi>({ show: () => {}, hide: () => {} })

export const useTooltip = () => useContext(TipContext)
