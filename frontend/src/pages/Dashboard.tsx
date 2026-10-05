import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { loadCapabilities, loadGoal, loadGrowth, loadReturnDemo } from '../api/growth'
import { CapabilityMap } from '../components/CapabilityMap'
import { CapabilityCard } from '../components/CapabilityCard'
import { ReturnSummary } from '../components/ReturnSummary'
import { PageState } from '../components/PageState'
import { taskHref } from '../components/taskLinks'
import type { Capability, Goal, GrowthTask, ReturnDemo } from '../types/growth'

export function Dashboard() {
  const { hash } = useLocation()
  const [goal, setGoal] = useState<Goal>()
  const [capabilities, setCapabilities] = useState<Capability[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [tasks, setTasks] = useState<GrowthTask[]>([])
  const [error, setError] = useState('')
  const [returnDemo, setReturnDemo] = useState<ReturnDemo | null>(null)
  useEffect(() => {
    if (!goal || !hash) return
    const target = document.getElementById(hash.slice(1))
    target?.scrollIntoView({ block: 'start' })
    if (hash === '#capability-detail') target?.focus({ preventScroll: true })
  }, [goal, hash])
  useEffect(() => {
    let active = true
    const load = async () => {
      const goalRow = await loadGoal()
      const body = await loadCapabilities()
      const returned = await loadReturnDemo()
      const growth = await loadGrowth()
      return { goalRow, body, returned, growth }
    }
    load().then(({ goalRow, body, returned, growth }) => {
        if (!active) return
        setGoal(goalRow); setCapabilities(body.capabilities); setReturnDemo(returned); setTasks(growth.tasks)
        setSelectedId((body.capabilities.find(item => item.open_gaps.length) ?? body.capabilities[0])?.id ?? '')
      }).catch((reason: Error) => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [])
  if (error) return <PageState error={error} />
  if (!goal) return <PageState />
  const selected = capabilities.find(item => item.id === selectedId)
  const related = tasks.filter(task => task.capability_id === selectedId)
  const relatedTask = related.find(task => !['done', 'abandoned'].includes(task.status)) ?? related[0]
  const recommended = returnDemo?.report.next_steps.map(step => tasks.find(task => task.id === step.task_id)).find(Boolean)
  const nextTask = recommended ?? related.find(task => !['done', 'abandoned'].includes(task.status))
  const subtitle = selected ? selected.open_gaps.length ? `下一步补齐${selected.open_gaps.map(gap => gap.dimension === 'understanding' ? '理解' : gap.dimension === 'practice' ? '实践' : gap.dimension).join('、')}证据，向目标靠近。` : '查看当前能力的评估与成长记录。' : '从能力与证据出发，找到下一步。'
  return <main>
    <section className="page-hero">
      <div><p className="eyebrow">01 / YOUR GROWTH</p><h1>{goal.title}</h1><p className="lead">{subtitle}</p></div>
      <Link className="button primary" to={nextTask ? taskHref(goal.id, nextTask.id) : '#capability-detail'}>查看下一步 <span aria-hidden="true">↗</span></Link>
    </section>
    <section className="map-workspace" id="capability-map" aria-label="能力地图与详情">
      <div className="map-column">
        <div className="section-heading"><h2><span className="section-number">02 /</span> 能力地图</h2><div className="legend"><span><i className="status-dot complete" />已达标</span><span><i className="status-dot gap" />待补齐</span><span><i className="status-dot unknown" />未评估</span></div></div>
        <CapabilityMap goal={goal} capabilities={capabilities} selected={selected} task={relatedTask} onSelect={setSelectedId} />
      </div>
      <aside className="inspector" id="capability-detail" tabIndex={-1}>
        {selected ? <CapabilityCard item={selected} task={relatedTask} goalId={goal.id} /> : <div className="empty-state"><p className="eyebrow">SELECTED CAPABILITY</p><h2>尚无能力记录</h2><p>能力评估完成后，等级与证据缺口会显示在这里。</p></div>}
      </aside>
    </section>
    <ReturnSummary value={returnDemo} />
  </main>
}
