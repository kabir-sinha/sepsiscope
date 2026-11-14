// Shapes of the local demo API responses (src/sepsiscope/api/app.py).
export type PatientRow = {
  key: string
  label: string
  story: string
  hours: number
  septic: boolean
}

export type Summary = {
  direction: string
  note: string
  lgbm_threshold: number
  news2_threshold: number
  alarm_budget: number
  patients: PatientRow[]
}

export type Reason = {
  feature: string
  label: string
  value: number | null
  contribution: number
}

export type Patient = PatientRow & {
  onset_hour: number | null
  age_group: string
  risk: number[]
  news2: number[]
  alert_hours: number[]
  reasons: Record<string, Reason[]>
}
