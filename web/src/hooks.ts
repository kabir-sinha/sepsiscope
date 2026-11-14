// Shared hooks (no components here): measured element width and the page tooltip API.
import { createContext, useContext, useEffect, useRef, useState } from 'react'
import type { MouseEvent, ReactNode } from 'react'

export function useWidth<T extends HTMLElement>(fallback = 700): [React.RefObject<T | null>, number] {
  const ref = useRef<T | null>(null)
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const el = ref.current
    if (!el) return
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
