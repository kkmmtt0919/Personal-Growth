import { useEffect, useState } from 'react'
import { loadGrowth } from '../api/growth'
import { TaskTimeline } from '../components/TaskTimeline'
import type { GrowthTask } from '../types/growth'

export function GrowthLoop() {
  const [tasks, setTasks] = useState<GrowthTask[]>([])
  const [error, setError] = useState('')
  useEffect(() => { loadGrowth().then((body) => setTasks(body.tasks)).catch((reason: Error) => setError(reason.message)) }, [])
  if (error) return <p>{error}</p>
  return <TaskTimeline tasks={tasks} />
}
