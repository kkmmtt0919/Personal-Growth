import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { productRequest } from '../api/product'

interface Action { id: string; kind: string; payload: { text?: string; note?: string; before?: number; target_level?: number }; result: { goal_id?: string } | null }
export function GoalRevision({ goalId, title }: { goalId: string; title: string }) {
  const navigate = useNavigate()
  const [actions, setActions] = useState<Action[]>([])
  const [text, setText] = useState(title)
  const [review, setReview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [requestId, setRequestId] = useState(() => crypto.randomUUID())
  useEffect(() => {
    let active = true
    productRequest<{ actions: Action[] }>(`/api/product/goals/${goalId}/actions`).then(value => { if (active) setActions(value.actions) }).catch(() => { /* 调整请求会显示错误 */ })
    return () => { active = false }
  }, [goalId])
  async function revise() {
    setBusy(true); setError('')
    try {
      const value = await productRequest<{ state: { goal: { id: string } } }>(`/api/product/goals/${goalId}/revisions`, { request_id: requestId, text, confirm: true })
      navigate(`/start?goal=${value.state.goal.id}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '调整未完成')
      try { setActions((await productRequest<{ actions: Action[] }>(`/api/product/goals/${goalId}/actions`)).actions) } catch { /* 保留错误 */ }
    } finally { setBusy(false) }
  }
  return <details className="goal-revision"><summary>调整目标与操作历史</summary><p>调整会建立新的目标版本，重新澄清并由你确认。原目标、能力和任务保留，可返回查看；新版本不会直接继承旧等级。</p>
    <label htmlFor="revision-text">调整后的目标</label><textarea id="revision-text" rows={4} maxLength={4000} value={text} disabled={busy} onChange={event => { setText(event.target.value); setReview(false); setRequestId(crypto.randomUUID()) }} />
    {!review ? <button className="button outline" disabled={busy || !text.trim() || text.trim() === title.trim()} onClick={() => setReview(true)}>核对目标调整</button> : <div className="action-review"><h3>确认开始调整</h3><blockquote>{text}</blockquote><p>原目标保留；接下来继续澄清调整后的四要素，再确认新目标。</p><button className="button primary" disabled={busy} onClick={() => void revise()}>{busy ? '处理中…' : '确认开始调整'}</button><button className="button outline" disabled={busy} onClick={() => setReview(false)}>返回编辑</button></div>}
    {error && <p role="alert">{error}</p>}{actions.length > 0 && <section><h3>已保存操作</h3>{actions.map(action => <p key={action.id}>{action.kind === 'goal_revision' ? <Link to={`/start?goal=${action.result?.goal_id}`}>目标调整：{action.payload.text}</Link> : `目标要求 ${action.payload.before} → ${action.payload.target_level}：${action.payload.note}`}</p>)}</section>}
  </details>
}
