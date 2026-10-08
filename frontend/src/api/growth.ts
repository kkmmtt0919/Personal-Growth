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
export const loadGrowth = (goalId = DEMO_GOAL) => read<{ tasks: GrowthTask[] }>(`/api/growth-loop/${encodeURIComponent(goalId)}`)
export async function loadInteraction(): Promise<{ enabled: boolean; submission_enabled: boolean }> {
  const response = await fetch(`${API_BASE}/api/interaction`)
  if (response.status === 404) return { enabled: false, submission_enabled: false }
  if (!response.ok) throw new Error('无法读取任务操作配置')
  return response.json()
}

export async function submitAnswer(id: string, requestId: string, answer: string) {
  const response = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(id)}/submissions`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_id: requestId, probe_answer: answer }),
  })
  const body = await response.json()
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : '提交失败')
  return body
}

export async function submitFile(id: string, requestId: string, file: File) {
  if (file.size > 2 * 1024 * 1024) throw new Error('文件过大，最多支持 2 MB')
  const encoded = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1])
    reader.onerror = () => reject(new Error('无法读取所选文件'))
    reader.readAsDataURL(file)
  })
  const response = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(id)}/files`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_id: requestId, filename: file.name, content_base64: encoded }),
  })
  const body = await response.json()
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : '文件提交失败')
  return body
}

export async function actOnTask(id: string, action: string, reason?: string) {
  const response = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(id)}/actions`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, reason }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : '操作失败，请刷新后重试')
  }
}
export async function loadReturnDemo(): Promise<ReturnDemo | null> {
  const response = await fetch(`${API_BASE}/api/return-demo/${DEMO_GOAL}`)
  if (response.status === 404) return null
  if (!response.ok) throw new Error(`${response.status} 返回场景无法核验`)
  return response.json()
}
