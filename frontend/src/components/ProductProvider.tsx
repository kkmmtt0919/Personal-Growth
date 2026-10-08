import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { API_BASE, ProductContext } from '../api/product'
import type { Product } from '../api/product'

export function ProductProvider({ children }: { children: ReactNode }) {
  const [product, setProduct] = useState<Product | null>(null)
  const [error, setError] = useState('')
  const refresh = useCallback(async () => {
    const response = await fetch(`${API_BASE}/api/product`)
    if (response.status === 404) { const value = { enabled: false }; setProduct(value); return value }
    if (!response.ok) throw new Error('无法读取产品状态')
    const value = await response.json() as Product
    setProduct(value); setError(''); return value
  }, [])
  useEffect(() => { void Promise.resolve().then(refresh).catch(reason => setError(reason.message)) }, [refresh])
  return <ProductContext.Provider value={{ product, error, refresh }}>{children}</ProductContext.Provider>
}
