import type { Capability, Evidence, Goal, GrowthTask, ReturnDemo } from '../types/growth'

const DEMO_GOAL = 'goal_demo'
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

async function read<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) throw new Error(`${response.status} ${path}`)
  return response.json()
}

export const loadGoal = () => read<Goal>(`/api/goals/${DEMO_GOAL}`)
export const loadCapabilities = () => read<{ capabilities: Capability[] }>(`/api/goals/${DEMO_GOAL}/capabilities`)
export const loadEvidence = (id: string) => read<Evidence>(`/api/evidence/${id}`)
export const loadGrowth = () => read<{ tasks: GrowthTask[] }>(`/api/growth-loop/${DEMO_GOAL}`)
export async function loadReturnDemo(): Promise<ReturnDemo | null> {
  const response = await fetch(`${API_BASE}/api/return-demo/${DEMO_GOAL}`)
  if (response.status === 404) return null
  if (!response.ok) throw new Error(`${response.status} 返回场景无法核验`)
  return response.json()
}
