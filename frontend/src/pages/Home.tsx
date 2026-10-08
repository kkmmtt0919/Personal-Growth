import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { productRequest, useProduct } from '../api/product'
import type { ProductGoal } from '../api/product'
import type { Capability } from '../types/growth'
import { Dashboard } from './Dashboard'
import { PageState } from '../components/PageState'
import { CapabilityMap } from '../components/CapabilityMap'
import { GoalRevision } from '../components/GoalRevision'

interface Overview { goal: ProductGoal; capabilities: Capability[]; tasks: { id: string; title: string; status: string }[]; gaps: { id: string; rationale: string }[]; history: { id: string }[] }
export function Home() {
  const { product, error: serviceError, refresh } = useProduct()
  const [search, setSearch] = useSearchParams()
  const selectedGoal = search.get('goal')
  const [overview, setOverview] = useState<Overview | null>(null)
  const [goals, setGoals] = useState<ProductGoal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState('')
  useEffect(() => {
    if (!product?.enabled) return
    let active = true
    refresh().then(async current => {
      const available = current.goals ?? []
      const remembered = localStorage.getItem('growth.selectedGoal')
      const goal = selectedGoal ?? available.find(item => item.id === remembered)?.id ?? available.at(-1)?.id
      const data = goal ? await productRequest<Overview>(`/api/product/goals/${encodeURIComponent(goal)}/overview`) : null
      if (active) {
        setError('')
        setGoals(available); setOverview(data); setSelectedId(data?.capabilities[0]?.id ?? '')
        if (goal) localStorage.setItem('growth.selectedGoal', goal)
        if (goal && !selectedGoal) setSearch({ goal }, { replace: true })
      }
    }).catch(reason => { if (active) setError(reason.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [product?.enabled, selectedGoal, refresh, setSearch])
  if (serviceError || error) return <PageState error={serviceError || error} />
  if (product?.enabled === false) return <Dashboard />
  if (!product || loading || (selectedGoal && overview?.goal.id !== selectedGoal)) return <PageState />
  if (!overview) return <main className="new-user-home"><p className="eyebrow">GROWTH OS / WELCOME</p><h1>从你的目标开始。</h1><p className="lead">把想达成的目标说清楚，再用你的材料和实践建立有依据的成长记录。</p>{product.configured === false && <p role="status">模型尚未配置，请先完成本地模型设置，再开始目标澄清。</p>}<Link className="button primary" to="/start">开始我的目标 ↗</Link><p className="muted">没有预设能力等级；你的目标、材料和对话会保存在本机。</p></main>
  const goal = overview.goal
  const selected = overview.capabilities.find(node => node.id === selectedId)
  const next = overview.tasks.find(task => ['active', 'blocked', 'proposed'].includes(task.status))
  return <main>
    <section className="page-hero"><div><p className="eyebrow">01 / YOUR GROWTH</p><h1>{goal.title}</h1><p className="lead">{goal.status !== 'confirmed' ? '目标尚未确认，先继续澄清。' : !overview.capabilities.length ? '目标已确认，下一步建立能力树。' : '查看当前证据、能力缺口与下一步。'}</p></div><Link className="button primary" to={goal.status !== 'confirmed' || !overview.capabilities.length ? `/start?goal=${goal.id}` : `/mentor/${goal.id}?goal=${goal.id}`}>{goal.status !== 'confirmed' || !overview.capabilities.length ? '继续设置目标' : '与导师聊聊'} ↗</Link></section>
    <div className="home-switcher"><label htmlFor="home-goal">当前目标</label><select id="home-goal" value={goal.id} onChange={event => { window.location.href = `/?goal=${encodeURIComponent(event.target.value)}` }}>{goals.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select><Link to="/start">新建目标</Link></div>
    <section className="home-next"><h2>下一步</h2><p>{next ? next.title : overview.gaps[0]?.rationale ?? (overview.capabilities.length ? '先补充个人材料，或与导师讨论要验证的能力。' : '确认目标后生成能力树。')}</p><div className="task-action-buttons"><Link className="button outline" to={next ? `/growth/${goal.id}?goal=${goal.id}` : `/start?goal=${goal.id}`}>{next ? '继续任务' : '目标与材料'}</Link><Link className="button outline" to={`/mentor/${goal.id}?goal=${goal.id}`}>AI 导师</Link><Link className="button outline" to={`/growth/${goal.id}?goal=${goal.id}`}>全部任务</Link></div></section>
    {overview.capabilities.length > 0 && <section id="capability-map"><div className="section-heading"><h2>能力地图</h2><span className="muted">{overview.capabilities.length} 个能力点 · {overview.gaps.length} 个待补缺口</span></div><CapabilityMap goal={goal} capabilities={overview.capabilities} selected={selected} onSelect={setSelectedId} />{selected && <section className="home-selected"><h3>{selected.name}</h3><p>理解：{selected.understanding ?? '未评估'} · 实践：{selected.practice ?? '未评估'} · 目标要求：{selected.target_level}</p><Link to={`/evidence/${selected.id}?goal=${goal.id}`}>查看证据与评级依据 →</Link></section>}</section>}
    <p className="muted">已完成 {overview.tasks.filter(task => task.status === 'done').length} 项任务 · {overview.history.length} 条评定记录。任务完成不直接代表能力提升。</p>
    {goal.status === 'confirmed' && <GoalRevision key={goal.id} goalId={goal.id} title={goal.title} />}
  </main>
}
