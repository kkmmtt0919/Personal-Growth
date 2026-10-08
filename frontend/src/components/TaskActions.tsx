import { useState } from 'react'
import { actOnTask, submitAnswer, submitFile } from '../api/growth'
import type { GrowthTask } from '../types/growth'
import { useProduct } from '../api/product'

export function TaskActions({ task, refresh, submissionEnabled = false }: { task: GrowthTask; refresh: () => Promise<void>; submissionEnabled?: boolean }) {
  const { product } = useProduct()
  const live = product?.enabled && product.mode === 'model'
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [answer, setAnswer] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [requestId, setRequestId] = useState(() => crypto.randomUUID())
  const actions = task.status === 'proposed' ? [['activate', '开始任务'], ['abandon', '放弃任务']]
    : task.status === 'active' ? [['block', '标记受阻'], ['abandon', '放弃任务']]
    : task.status === 'blocked' ? [['resume', '恢复任务'], ['abandon', '放弃任务']] : []
  if (!actions.length) return null
  async function submit() {
    if (busy) return
    const isAnswer = task.deliverable_type === 'probe_answer'
    if (isAnswer ? !answer.trim() : !file) { setMessage(isAnswer ? '请填写理解回答。' : '请选择实践产物文件。'); return }
    setBusy(true)
    setMessage('正在记录证据并重评，请等待。')
    try {
      if (isAnswer) await submitAnswer(task.id, requestId, answer)
      else if (file) await submitFile(task.id, requestId, file)
      setMessage('提交已完成，请查看证据与两维度重评结果。')
      await refresh()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '提交失败')
    } finally { setBusy(false) }
  }
  async function run(action: string) {
    if (busy) return
    if (['block', 'abandon'].includes(action) && !reason.trim()) {
      setMessage('请先填写受阻或放弃的原因。')
      return
    }
    setBusy(true)
    setMessage('')
    try {
      await actOnTask(task.id, action, reason)
      await refresh()
      setReason('')
      setMessage('任务状态已更新。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '操作失败')
    } finally { setBusy(false) }
  }
  return <div className="task-actions">
    {submissionEnabled && task.status === 'active' && task.deliverable_type === 'probe_answer' && <>
      <label htmlFor={`answer-${task.id}`}>理解回答</label>
      <p className="muted">{live ? '提交后记录原文，模型只提议证据关联；评级由证据规则生成。' : '本地受控实验默认使用固定绑定规则；结果不代表导师对回答质量的判断。'}</p>
      <textarea id={`answer-${task.id}`} rows={6} value={answer} maxLength={50000} disabled={busy}
        onChange={event => { setAnswer(event.target.value); setRequestId(crypto.randomUUID()) }} />
      <button className="button outline" disabled={busy || !answer.trim()} onClick={() => void submit()}>提交并重评</button>
    </>}
    {submissionEnabled && task.status === 'active' && ['markdown', 'code', 'archive'].includes(task.deliverable_type ?? '') && <>
      <label htmlFor={`file-${task.id}`}>实践产物文件</label>
      <p className="muted">{task.deliverable_type === 'archive' ? '选择 ZIP 归档' : task.deliverable_type === 'code' ? '选择 UTF-8 代码文件' : '选择 UTF-8 Markdown 或 TXT 报告'}，最多 2 MB。提交后依据新证据重评。</p>
      <p className="muted">{live ? '模型提议证据关联，评级依据已有证据规则；材料质量还需结合引用与局限核对。' : '本地受控实验默认使用固定绑定规则，演示结果不代表对产物质量的判断。'}</p>
      <input id={`file-${task.id}`} type="file" disabled={busy}
        accept={task.deliverable_type === 'archive' ? '.zip' : task.deliverable_type === 'markdown' ? '.md,.markdown,.txt' : undefined}
        onChange={event => { setFile(event.target.files?.[0] ?? null); setRequestId(crypto.randomUUID()); setMessage('') }} />
      {file && <p className="muted">已选择：{file.name}</p>}
      <button className="button outline" disabled={busy || !file} onClick={() => void submit()}>提交文件并重评</button>
    </>}
    <label htmlFor={`reason-${task.id}`}>受阻或放弃的原因</label>
    <textarea id={`reason-${task.id}`} value={reason} maxLength={2000} disabled={busy}
      onChange={event => setReason(event.target.value)} rows={2} />
    <div className="task-action-buttons">{actions.map(([action, label]) =>
      <button className="button outline" key={action} disabled={busy}
        onClick={() => void run(action)}>{busy ? '处理中…' : label}</button>)}</div>
    <p role="status" aria-live="polite">{message}</p>
  </div>
}
