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

export type WhatIfRow = { alert_hours: number[]; verdict: Verdict }

export type PatientRow = {
  key: string
  label: string
  story: string
  story_note: string | null
  hours: number
  septic: boolean
  verdict: { sepsiscope: Verdict; news2: Verdict }
  what_if: { sepsiscope: WhatIfRow[]; news2: WhatIfRow[] }
}

export type VitalInfo = { label: string; unit: string; normal: [number, number] }

export type Summary = {
  direction: string
  note: string
  lgbm_threshold: number
  news2_threshold: number
  alarm_budget: number
  rules: string[]
  what_if: { budgets: number[]; lgbm_thresholds: number[]; news2_thresholds: number[]; source: string }
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
  compare: { lr: number[]; news2_prob: number[] }
}

export type ResultRow = {
  direction: string
  model: string
  label: string
  utility: number
  utility_ci: [number, number]
  auroc: number
  auroc_ci: [number, number]
  auprc: number
  auprc_ci: [number, number]
  alert_rate: number
  false_alerts_per_100_days: number
  timely_sensitivity: number
  timely_sensitivity_ci: [number, number]
  rethresholded_alert_rate: number
  rethresholded_utility: number
}

export type Results = {
  alarm_budget: number
  rows: ResultRow[]
  criterion: Record<string, { ci95_utility_difference: [number, number]; met_in_this_direction: boolean }>
  robustness: Robustness | null
}

// Milestone 5 robustness checks (from the committed bands_*, deferral_*, budgets_* files).
export type Metric = { point: number; ci: [number, number] }
export type BandsDir = {
  bands: string[]
  rule: string
  models: Record<string, { overall_auroc: number; bands: Record<string, { auroc: Metric; alert_rate: Metric }> }>
  collapse: { collapse: boolean; flagged_bands: { band: string; reasons: string[] }[] }
}
export type DeferralDir = {
  alpha: number
  deferral_rate: Metric
  coverage: { label0: number; label1: number }
  share_not_deferred: { label0: number; label1: number }
  utility_non_deferred: Metric
  headline_utility: number
  criteria: { a: boolean; b: boolean; c: boolean }
  useful: boolean
}
export type BudgetRow = { lgbm: Metric; lr: Metric; difference: Metric }
export type Robustness = {
  bands: Record<string, BandsDir>
  deferral: Record<string, DeferralDir>
  budgets: Record<string, Record<string, BudgetRow>>
}
