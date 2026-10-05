export interface Goal { id: string; title: string; status: string }
export interface ReturnDemo {
  constructed: boolean; simulated_return: boolean
  report: {
    goal_id: string; returned_at: string; mode: string
    baseline_snapshot_id: string | null; current_snapshot_id: string
    summary: { status: string; text: string; changes: { before_assessment_id: string | null; after_assessment_id: string | null }[] }
    next_step_text: string; preference_text: string
    next_steps: { gap_id: string; task_id: string | null; assessment_id: string | null }[]
    preferences: { memory_id: string; source_kind: string; source_id: string }[]
  }
}
export interface Capability { id: string; name: string; target_level: number; understanding: number | null; practice: number | null; open_gaps: { dimension: string; severity: string }[] }
export interface Evidence { capability: string; assessment: { understanding: number | null; practice: number | null }; supports: { claim_id: string; source: { name: string | null; type: string | null }; quote: { text: string | null; locator: unknown }; binding_reason: string }[]; gaps: string[] }
export interface GrowthTask {
  id: string; title: string; status: string; capability_id: string
  objective: string; acceptance: string
  gap: { rationale: string; status: string; dimension?: string } | null
  submissions: { source_id: string }[]
  attribution: {
    before: { practice: { level: number | null } }
    after: { practice: { level: number | null } }
    guard: Record<string, boolean>
  } | null
}
