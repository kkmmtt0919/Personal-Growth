import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { PersonalMaterials } from '../components/PersonalMaterials'
import { useProduct } from '../api/product'
import { GoalRevision } from '../components/GoalRevision'
import { CapabilityAdjustment } from '../components/CapabilityAdjustment'

const BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')
const labels: Record<string, string> = { direction: '方向', purpose: '目的', horizon: '周期', measurable_result: '可衡量结果' }
interface Goal { id: string; title: string; status: string; direction?: string; purpose?: string; horizon?: string; measurable_result?: string; source_quote?: string }
interface Capability { id: string; name: string; path: string; depth: number; target_level: number; current_level: number | null; current_level_understanding: number | null; current_level_practice: number | null; source_note: string; generated_by_run_id: string }
interface State { goal: Goal; revision_of?: { goal_id: string; quote: string } | null; history: { round: number; question: string; answer: string | null }[]; pending: { round: number; question: string } | null; rounds_left: number; needs_retry: boolean; mode: string; capabilities: Capability[] }

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE}/api/onboarding${path}`, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (response.status === 404) throw new Error('当前服务尚未开放目标澄清。')
  const value = await response.json()
  if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : '操作失败，请稍后重试。')
  return value
}

export function Onboarding() {
  const { product } = useProduct()
  const navigate = useNavigate()
  const [search, setSearch] = useSearchParams()
  const selectedGoal = search.get('goal')
  const [goals, setGoals] = useState<Goal[]>([])
  const [mode, setMode] = useState('')
  const [state, setState] = useState<State | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [requestId, setRequestId] = useState(() => crypto.randomUUID())
  useEffect(() => {
    let active = true
    request<{ goals: Goal[]; mode: string }>('').then(body => {
      if (active) { setGoals(body.goals); setMode(body.mode) }
    }).catch(reason => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [])
  useEffect(() => {
    if (!selectedGoal || selectedGoal === state?.goal.id) return
    let active = true
    request<State>(`/goals/${encodeURIComponent(selectedGoal)}`).then(value => {
      if (active) { setState(value); setText('') }
    }).catch(reason => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [selectedGoal, state?.goal.id])
  async function run(path: string, body?: unknown) {
    if (busy) return
    setBusy(true); setError('')
    try {
      const result = await request<State>(path, body)
      setState(result); setText('')
      localStorage.setItem('growth.selectedGoal', result.goal.id)
      setSearch({ goal: result.goal.id }, { replace: true })
      setGoals((await request<{ goals: Goal[] }>('')).goals)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '操作失败')
      if (state) {
        try { setState(await request<State>(`/goals/${state.goal.id}`)) } catch { /* 保留原状态与错误 */ }
      } else {
        try { setGoals((await request<{ goals: Goal[] }>('')).goals) } catch { /* 保留错误 */ }
      }
    } finally { setBusy(false) }
  }
  const status = state?.goal.status
  async function plan(node: Capability, dimension: 'understanding' | 'practice') {
    if (busy || !state) return
    setBusy(true); setError('')
    try {
      await request(`/goals/${state.goal.id}/capabilities/${node.id}/tasks`, { dimension })
      navigate(`/growth/${state.goal.id}?goal=${state.goal.id}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '任务生成失败')
    } finally { setBusy(false) }
  }
  async function submit() {
    if (!text.trim()) { setError('请填写内容。'); return }
    if (!state) await run('/goals', { request_id: requestId, text })
    else if (status === 'proposed') await run(`/goals/${state.goal.id}/confirm`, { quote: text })
    else if (state.pending) await run(`/goals/${state.goal.id}/answers`, { round: state.pending.round, text })
  }
  return <main>
    <section className="page-hero"><div><p className="eyebrow">01 / YOUR GOAL</p><h1>先把目标，说清楚。</h1><p className="lead">明确方向、目的、周期和成果，再由你确认。</p></div>{product?.enabled && state && <Link className="button outline" to={`/?goal=${state.goal.id}`}>查看个人首页 ↗</Link>}</section>
    {mode && <p className="muted">{mode === 'fixed_questions' ? '固定问句实验：回答按原话记录，不推断未提供的信息。' : '模型澄清：提议需由你显式确认。'}最多六轮。</p>}
    <div className="onboarding-layout">
      <section className="onboarding-session">
        {state && <><h2>{state.goal.title}</h2><p className="tag">{status === 'confirmed' ? '已确认' : status === 'proposed' ? '待确认' : '澄清中'}</p>
          {state.revision_of && <p>这是调整后的目标版本。<Link to={`/start?goal=${state.revision_of.goal_id}`}>查看保留的原目标 →</Link></p>}
          {state.history.map(item => <article className="goal-turn" key={item.round}><h3>第 {item.round} 轮</h3><p>{item.question}</p>{item.answer && <blockquote>{item.answer}</blockquote>}</article>)}
          <div className="goal-elements">{Object.entries(labels).map(([field, label]) => <p key={field}><strong>{label}：</strong>{state.goal[field as keyof Goal] || '尚未确定'}</p>)}</div>
        </>}
        {status === 'confirmed' && state ? <section><h3>目标已确认并保存</h3><p>确认原话：{state.goal.source_quote}</p>
          <p className="muted">{state.mode === 'fixed_questions' ? '结构演示模板：尚未核对与目标的相关性，目标等级为占位值。' : '模型生成的能力要求尚未校验外部来源。'}当前能力尚未评估。</p>
          {!state.capabilities.length ? <button className="button outline" disabled={busy} onClick={() => void run(`/goals/${state.goal.id}/capabilities`, {})}>{busy ? '生成中…' : state.mode === 'fixed_questions' ? '生成结构演示模板' : '生成能力树'}</button>
            : <div className="onboarding-tree"><h3>能力树 · 未校验</h3><p>{state.capabilities.filter(node => node.depth === 1).length} 个领域 · {state.capabilities.filter(node => node.depth === 3).length} 个能力点</p>
              <p className="muted">选择能力点的任务维度，先检查证据与缺口，再提议任务。{state.mode === 'fixed_questions' ? '固定模板与绑定规则只演示流程，不判断产物质量。' : '模型提出任务与关联，等级由证据规则评定。'}</p>
              <Link to={`/growth/${state.goal.id}?goal=${state.goal.id}`}>查看本目标任务</Link>
              {state.capabilities.map(node => <article key={node.id} className={`capability-depth-${node.depth}`}><h4>{node.name}</h4><p>目标要求 {node.target_level} · 当前{node.current_level_understanding === null && node.current_level_practice === null ? '未知' : `理解 ${node.current_level_understanding ?? '未知'} / 实践 ${node.current_level_practice ?? '未知'}`} · 未校验</p>{node.depth === 3 && <><p>理解：{node.current_level_understanding ?? '未知'} · 实践：{node.current_level_practice ?? '未知'}</p><div className="task-action-buttons"><button className="button outline" disabled={busy} onClick={() => void plan(node, 'understanding')}>生成理解任务</button><button className="button outline" disabled={busy} onClick={() => void plan(node, 'practice')}>生成实践任务</button><Link to={`/evidence/${node.id}?goal=${state.goal.id}`}>查看证据与评级</Link></div>{product?.enabled && <CapabilityAdjustment key={node.id} goalId={state.goal.id} capability={node} refresh={async () => setState(await request<State>(`/goals/${state.goal.id}`))} />}</>}<details><summary>来源与追溯</summary><p>{node.source_note}</p><p>路径：{node.path}</p><p>生成记录：{node.generated_by_run_id}</p></details></article>)}
            </div>}
        </section>
          : state?.needs_retry ? <div><p>上次提问未完成，已答内容已保存。</p><button className="button outline" disabled={busy || state.rounds_left === 0} onClick={() => void run(`/goals/${state.goal.id}/resume`, {})}>恢复提问</button>{state.rounds_left === 0 && <p>已达轮次上限，请重新开始目标。</p>}</div>
          : <form className="task-actions" onSubmit={event => { event.preventDefault(); void submit() }}>
            <label htmlFor="goal-text">{!state ? '你想达成什么？' : status === 'proposed' ? '你的确认原话' : state.pending?.question}</label>
            {status === 'proposed' && <p>请核对以上四要素；确认按钮会保存你的原话。</p>}
            <textarea id="goal-text" rows={5} maxLength={4000} value={text} disabled={busy || !mode}
              onChange={event => { setText(event.target.value); if (!state) setRequestId(crypto.randomUUID()) }} />
            <button className="button outline" disabled={busy || !mode || !text.trim()}>{busy ? '处理中…' : !state ? '开始澄清' : status === 'proposed' ? '确认目标' : '提交回答'}</button>
          </form>}
        {error && <p role="alert">{error}</p>}{product?.enabled && state && status === 'confirmed' && <GoalRevision key={"revision-" + state.goal.id} goalId={state.goal.id} title={state.goal.title} />}
        {state && status === 'confirmed' && state.capabilities.length > 0 && <PersonalMaterials key={state.goal.id} goalId={state.goal.id} capabilities={state.capabilities.filter(node => node.depth === 3)} refresh={async () => setState(await request<State>(`/goals/${state.goal.id}`))} />}
      </section>
      <aside className="onboarding-history"><h2>已保存的目标</h2><p className="muted">刷新后可从这里继续。</p>
        {goals.map(goal => <button className="button outline" key={goal.id} disabled={busy} onClick={() => void run(`/goals/${goal.id}`)}>{goal.title}</button>)}
        {!goals.length && <p className="muted">暂无目标记录。</p>}
        <button className="button outline" disabled={busy || !mode} onClick={() => { setSearch({}); setState(null); setText(''); setError(''); setRequestId(crypto.randomUUID()) }}>重新开始目标</button>
      </aside>
    </div>
  </main>
}
