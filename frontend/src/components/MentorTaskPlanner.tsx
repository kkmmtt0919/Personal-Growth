import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { productRequest } from '../api/product'

interface Capability { id: string; name: string; path: string }
interface Task { id: string; title: string; objective: string; acceptance: string; status: string }
export function MentorTaskPlanner({ goalId }: { goalId: string }) {
  const [capabilities, setCapabilities] = useState<Capability[]>([])
  const [capabilityId, setCapabilityId] = useState('')
  const [dimension, setDimension] = useState('practice')
  const [review, setReview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [task, setTask] = useState<Task | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    productRequest<{ capabilities: Capability[] }>(`/api/product/goals/${goalId}/overview`).then(value => { if (active) { setCapabilities(value.capabilities); setCapabilityId(value.capabilities[0]?.id ?? '') } }).catch(reason => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [goalId])
  async function generate() {
    setBusy(true); setError('')
    try { setTask((await productRequest<{ task: Task }>(`/api/onboarding/goals/${goalId}/capabilities/${capabilityId}/tasks`, { dimension })).task); setReview(false) }
    catch (reason) { setError(reason instanceof Error ? reason.message : '生成失败') }
    finally { setBusy(false) }
  }
  return <details className="mentor-task-planner"><summary>把下一步变成任务</summary><p>选择要验证的能力和维度，确认后检查证据缺口并生成任务。现有未完成任务会复用；任务仍需你在任务页启动。</p>
    {capabilities.length ? <><label htmlFor="mentor-task-capability">要验证的能力</label><select id="mentor-task-capability" disabled={busy} value={capabilityId} onChange={event => { setCapabilityId(event.target.value); setReview(false); setTask(null) }}>{capabilities.map(capability => <option key={capability.id} value={capability.id}>{capability.path}</option>)}</select>
    <label htmlFor="mentor-task-dimension">任务维度</label><select id="mentor-task-dimension" disabled={busy} value={dimension} onChange={event => { setDimension(event.target.value); setReview(false); setTask(null) }}><option value="practice">实践 · 提交产物</option><option value="understanding">理解 · 作答验证</option></select>
    {!review ? <button className="button outline" disabled={busy} onClick={() => setReview(true)}>核对任务生成</button> : <div className="action-review"><p>为“{capabilities.find(capability => capability.id === capabilityId)?.name}”生成{dimension === 'practice' ? '实践' : '理解'}任务？确认会记录证据评定和任务提议。</p><button className="button primary" disabled={busy} onClick={() => void generate()}>{busy ? '生成中…' : '确认生成任务'}</button><button className="button outline" disabled={busy} onClick={() => setReview(false)}>取消</button></div>}
    {task && <section><h3>已保存任务：{task.title}</h3><p>{task.objective}</p><p>验收：{task.acceptance}</p><Link className="button primary" to={`/growth/${goalId}?goal=${goalId}#task-${task.id}`}>查看并启动任务 ↗</Link></section>}</> : <p><Link to={`/start?goal=${goalId}`}>先确认目标并建立能力树</Link></p>}
    {error && <p role="alert">{error}</p>}
  </details>
}
