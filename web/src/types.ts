// Shapes of the local demo API responses (src/sepsiscope/api/app.py).
export type Verdict = {
  outcome: string
  badge: string
  sentence: string
  lead_hours: number | null
  first_alert_hour: number | null
  alert_hours: number
  false_alarm_hours: number
}

export type PatientRow = {
  key: string
  label: string
  story: string
  story_note: string | null
  hours: number
  septic: boolean
  verdict: { sepsiscope: Verdict; news2: Verdict }
}

export type VitalInfo = { label: string; unit: string; normal: [number, number] }

export type Summary = {
  direction: string
  note: string
  lgbm_threshold: number
  news2_threshold: number
  alarm_budget: number
  rules: string[]
  vitals: Record<string, VitalInfo>
  patients: PatientRow[]
}

export type Reason = {
  feature: string
  label: string
  value: number | null
  unit: string
  process: boolean
  contribution: number
  sentence: string
}

export type Patient = PatientRow & {
  onset_hour: number | null
  window: [number, number] | null
  age_group: string
  risk: number[]
  news2: number[]
  vitals: Record<string, (number | null)[]>
  alert_hours: number[]
  news2_alert_hours: number[]
  banner: string
  reasons: Reason[][]
}

export type ResultRow = {
  direction: string
  model: string
  label: string
  utility: number
  utility_ci: [number, number]
  auroc: number
  auprc: number
  alert_rate: number
  false_alerts_per_100_days: number
  timely_sensitivity: number
  rethresholded_alert_rate: number
  rethresholded_utility: number
}

export type Results = {
  alarm_budget: number
  rows: ResultRow[]
  criterion: Record<string, { ci95_utility_difference: [number, number]; met_in_this_direction: boolean }>
}
