import { useState } from 'react'
import { productRequest } from '../api/product'

export function CapabilityAdjustment({ goalId, capability, refresh }: { goalId: string; capability: { id: string; target_level: number; name: string }; refresh: () => Promise<void> }) {
  const [level, setLevel] = useState(capability.target_level)
  const [note, setNote] = useState('')
  const [review, setReview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [requestId, setRequestId] = useState(() => crypto.randomUUID())
  async function adjust() {
    setBusy(true); setMessage('')
    try {
      await productRequest(`/api/product/goals/${goalId}/capabilities/${capability.id}/adjust`, { request_id: requestId, target_level: level, expected_target_level: capability.target_level, note, confirm: true })
      await refresh(); setReview(false); setMessage('目标要求已调整并记录理由，当前能力等级保持原评定。'); setRequestId(crypto.randomUUID())
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : '调整失败') }
    finally { setBusy(false) }
  }
  return <details><summary>调整此能力的目标要求</summary><p>这里只调整希望达到的要求；当前理解和实践等级由证据评定。</p><label htmlFor={`level-${capability.id}`}>目标要求</label><select id={`level-${capability.id}`} value={level} disabled={busy} onChange={event => { setLevel(Number(event.target.value)); setReview(false); setRequestId(crypto.randomUUID()) }}>{[1, 2, 3, 4, 5].map(value => <option key={value} value={value}>{value}</option>)}</select><label htmlFor={`note-${capability.id}`}>调整理由</label><textarea id={`note-${capability.id}`} rows={2} maxLength={2000} disabled={busy} value={note} onChange={event => { setNote(event.target.value); setReview(false); setRequestId(crypto.randomUUID()) }} />
    {!review ? <button className="button outline" disabled={busy || !note.trim() || level === capability.target_level} onClick={() => setReview(true)}>核对要求调整</button> : <div className="action-review"><p>{capability.name}：目标要求 {capability.target_level} → {level}；理由：{note}</p><button className="button primary" disabled={busy} onClick={() => void adjust()}>{busy ? '保存中…' : '确认调整要求'}</button><button className="button outline" disabled={busy} onClick={() => setReview(false)}>取消</button></div>}{message && <p role="status">{message}</p>}
  </details>
}
