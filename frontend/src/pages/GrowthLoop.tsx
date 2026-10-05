import { useEffect, useState } from 'react'
import { loadGrowth } from '../api/growth'
import { TaskTimeline } from '../components/TaskTimeline'
import { PageState } from '../components/PageState'
import type { GrowthTask } from '../types/growth'

export function GrowthLoop() {
  const [tasks, setTasks] = useState<GrowthTask[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    loadGrowth().then(body => { if (active) setTasks(body.tasks) }).catch((reason: Error) => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [])
  if (error) return <PageState error={error} />
  return tasks ? <TaskTimeline tasks={tasks} /> : <PageState />
}
