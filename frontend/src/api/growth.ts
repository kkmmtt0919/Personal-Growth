import type { Capability, Evidence, Goal, GrowthTask } from '../types/growth'

const DEMO_GOAL = 'goal_demo'

async function read<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`${response.status} ${path}`)
  return response.json()
}

export const loadGoal = () => read<Goal>(`/api/goals/${DEMO_GOAL}`)
export const loadCapabilities = () => read<{ capabilities: Capability[] }>(`/api/goals/${DEMO_GOAL}/capabilities`)
export const loadEvidence = (id: string) => read<Evidence>(`/api/evidence/${id}`)
export const loadGrowth = () => read<{ tasks: GrowthTask[] }>(`/api/growth-loop/${DEMO_GOAL}`)
