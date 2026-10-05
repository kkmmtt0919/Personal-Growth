import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { loadCapabilities, loadGoal } from '../api/growth'
import { CapabilityCard } from '../components/CapabilityCard'
import type { Capability, Goal } from '../types/growth'

export function Dashboard() {
  const [goal, setGoal] = useState<Goal>()
  const [capabilities, setCapabilities] = useState<Capability[]>([])
  const [error, setError] = useState('')
  useEffect(() => { Promise.all([loadGoal(), loadCapabilities()]).then(([goalRow, body]) => { setGoal(goalRow); setCapabilities(body.capabilities) }).catch((reason: Error) => setError(reason.message)) }, [])
  if (error) return <p>{error}</p>
  return <main><p>受控 Demo，不代表真实用户成果</p><h1>{goal?.title ?? '加载中'}</h1>{capabilities.map((item) => <CapabilityCard key={item.id} item={item} />)}<Link to="/growth/goal_demo">查看成长任务</Link></main>
}
