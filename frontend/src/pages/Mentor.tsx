import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { productRequest, useProduct } from '../api/product'
import { PageState } from '../components/PageState'
import { MentorMessage } from '../components/MentorMessage'
import { MentorTaskPlanner } from '../components/MentorTaskPlanner'

interface Turn { id: string; text: string; status: string; response: { answer: string; references: string[]; citations?: { label: string; href: string }[]; model: string } | null }
export function Mentor() {
  const { goalId = '' } = useParams()
  const { product } = useProduct()
  const [turns, setTurns] = useState<Turn[] | null>(null)
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [requestId, setRequestId] = useState(() => crypto.randomUUID())
  const [preference, setPreference] = useState('')
  const [preferenceSaved, setPreferenceSaved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    Promise.all([productRequest<{ turns: Turn[] }>(`/api/mentor/${goalId}`), productRequest<{ title: string }>(`/api/goals/${goalId}`), productRequest<{ preferences: { value: { text?: string } }[] }>('/api/product/preferences')]).then(([conversation, goal, memories]) => {
      if (active) { setTurns(conversation.turns); setTitle(goal.title); setPreference(memories.preferences.find(item => item.value.text)?.value.text ?? '') }
    }).catch(reason => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [goalId])
  async function send(id: string = requestId, message = text) {
    if (busy || !message.trim()) return
    setBusy(true); setError('')
    setTurns(previous => previous?.some(turn => turn.id === id) ? previous : [...(previous ?? []), { id, text: message, status: 'running', response: null }])
    try {
      await productRequest(`/api/mentor/${goalId}`, { request_id: id, text: message })
      setText(''); setRequestId(crypto.randomUUID())
    } catch (reason) { setError(reason instanceof Error ? reason.message : '回复失败') }
    finally {
      try { setTurns((await productRequest<{ turns: Turn[] }>(`/api/mentor/${goalId}`)).turns) } catch { /* 保留错误 */ }
      setBusy(false)
    }
  }
  async function remember() {
    if (busy || !preference.trim()) return
    setBusy(true); setError('')
    try { await productRequest('/api/product/preferences', { text: preference }); setPreferenceSaved(true) }
    catch (reason) { setError(reason instanceof Error ? reason.message : '偏好保存失败') }
    finally { setBusy(false) }
  }
  if (!turns && error) return <PageState error={error} />
  if (!turns) return <PageState />
  return <main className="mentor-page"><section className="page-hero"><div><p className="eyebrow">AI MENTOR</p><h1>把下一步，聊清楚。</h1><p className="lead">{title}</p></div><Link className="button outline" to={`/?goal=${goalId}`}>返回个人首页 ↗</Link></section>
    <p className="muted">{product?.mode === 'demo' ? '离线演示，未调用真实模型。' : '导师依据当前目标、偏好、能力、证据与评定历史回复。'}聊天建议需由你确认后执行；对话不会直接修改目标或等级。</p>
    <details className="mentor-preference"><summary>我的学习偏好</summary><label htmlFor="mentor-preference">例如：偏好实践，先看架构再看代码</label><textarea id="mentor-preference" rows={2} value={preference} maxLength={2000} disabled={busy} onChange={event => { setPreference(event.target.value); setPreferenceSaved(false) }} /><button className="button outline" disabled={busy || !preference.trim()} onClick={() => void remember()}>保存偏好</button>{preferenceSaved && <p role="status">偏好已保存，下次对话会使用。</p>}</details>
    <section className="mentor-conversation" aria-label="导师对话" aria-live="polite">
      {!turns.length && <div className="empty-state"><h2>从当前目标聊起</h2><p>你可以问：我现在该做什么、为什么证据不足、如何设计下一个项目。</p></div>}
      {turns.map(turn => <article className="mentor-turn" key={turn.id}><div className="mentor-user"><span className="eyebrow">你</span><p>{turn.text}</p></div>
        {turn.response ? <div className="mentor-answer"><span className="eyebrow">导师</span><MentorMessage text={turn.response.references.reduce((answer, reference, index) => answer.replaceAll(reference, turn.response?.citations?.[index]?.label ?? reference), turn.response.answer)} />
          {turn.response.references.length > 0 && <details><summary>核对回答依据</summary>{turn.response.citations?.map((citation, index) => <p key={index}><Link to={citation.href}>{citation.label}</Link></p>)}</details>}
        </div> : <div className="mentor-answer"><p>{turn.status === 'running' ? '正在回复…' : '回复未完成，消息已保存。'}</p><button className="button outline" disabled={busy || turn.status === 'running'} onClick={() => void send(turn.id, turn.text)}>重试这条消息</button></div>}
      </article>)}
    </section>
    <form className="mentor-compose task-actions" onSubmit={event => { event.preventDefault(); void send() }}><label htmlFor="mentor-message">继续对话</label><textarea id="mentor-message" rows={4} maxLength={6000} value={text} disabled={busy} onChange={event => { setText(event.target.value); setRequestId(crypto.randomUUID()) }} /><button className="button primary" disabled={busy || !text.trim()}>{busy ? '导师正在思考…' : '发送消息'}</button></form>
    {error && <p role="alert">{error}</p>}<MentorTaskPlanner key={goalId} goalId={goalId} /><div className="task-action-buttons"><Link to={`/start?goal=${goalId}`}>目标与材料</Link><Link to={`/growth/${goalId}?goal=${goalId}`}>任务与提交</Link><Link to="/start">建立新目标</Link></div>
  </main>
}
