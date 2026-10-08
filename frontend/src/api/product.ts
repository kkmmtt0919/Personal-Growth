import { createContext, useContext } from 'react'

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')
export interface ProductGoal { id: string; title: string; status: string }
export interface Product { enabled: boolean; mode?: string; provider?: string; model?: string; configured?: boolean; goals?: ProductGoal[] }
export async function productRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const value = await response.json()
  if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : '请求未完成，请稍后重试')
  return value
}
export const ProductContext = createContext<{ product: Product | null; error: string; refresh: () => Promise<Product> }>({
  product: null, error: '', refresh: async () => ({ enabled: false }),
})
export const useProduct = () => useContext(ProductContext)
