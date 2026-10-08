import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { loadGrowth, loadInteraction } from '../api/growth'
import { TaskTimeline } from '../components/TaskTimeline'
import { PageState } from '../components/PageState'
import type { GrowthTask } from '../types/growth'

export function GrowthLoop() {
  const { goalId = 'goal_demo' } = useParams()
  const [tasks, setTasks] = useState<GrowthTask[] | null>(null)
  const [error, setError] = useState('')
  const [interactive, setInteractive] = useState(false)
  const [submissionEnabled, setSubmissionEnabled] = useState(false)
  useEffect(() => {
    let active = true
    Promise.all([loadGrowth(goalId), loadInteraction()]).then(([body, enabled]) => {
      if (active) { setTasks(body.tasks); setInteractive(enabled.enabled); setSubmissionEnabled(enabled.submission_enabled) }
    }).catch((reason: Error) => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [goalId])
  if (error) return <PageState error={error} />
  async function refresh() { setTasks((await loadGrowth(goalId)).tasks) }
  return tasks ? <TaskTimeline tasks={tasks} refresh={interactive ? refresh : undefined} submissionEnabled={submissionEnabled} /> : <PageState />
}
