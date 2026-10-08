import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')
interface Material {
  request_id: string; filename: string; capability_id: string; evidence_type: string; attribution: string
  binding_status: string; passage_count: number; source_id: string
  proposal: { capability_path: string; claim_id: string; rationale: string }
  quotes: { text: string; locator: unknown }[]
  decision?: { accepted: boolean; reject_reason: string | null }
}

export function PersonalMaterials({ goalId, capabilities, refresh }: {
  goalId: string; capabilities: { id: string; path: string }[]; refresh: () => Promise<void>
}) {
  const [materials, setMaterials] = useState<Material[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [target, setTarget] = useState(capabilities[0]?.id ?? '')
  const [type, setType] = useState('uploaded_doc')
  const [owned, setOwned] = useState(false)
  const [requestId, setRequestId] = useState(() => crypto.randomUUID())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const path = `/api/onboarding/goals/${encodeURIComponent(goalId)}/materials`
  async function request<T>(suffix = '', body?: unknown): Promise<T> {
    const response = await fetch(`${BASE}${path}${suffix}`, body === undefined ? undefined : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
    const value = await response.json()
    if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : '材料操作失败')
    return value
  }
  useEffect(() => {
    let active = true
    fetch(`${BASE}${path}`).then(async response => {
      if (!response.ok) throw new Error('无法读取已保存材料')
      const value = await response.json()
      if (active) setMaterials(value.materials)
    }).catch(reason => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [path])
  async function upload() {
    if (busy || !file || !target) return
    if (file.size > 2 * 1024 * 1024) { setError('材料过大，最多2 MB。'); return }
    setBusy(true); setError('')
    try {
      const content = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result).split(',')[1])
        reader.onerror = () => reject(new Error('无法读取材料'))
        reader.readAsDataURL(file)
      })
      const material = await request<Material>('', { request_id: requestId, filename: file.name,
        content_base64: content, capability_id: target, evidence_type: type, attribution: owned ? 'user_declared' : 'unknown' })
      setMaterials(previous => [...previous.filter(item => item.request_id !== material.request_id), material])
    } catch (reason) { setError(reason instanceof Error ? reason.message : '材料上传失败') }
    finally { setBusy(false) }
  }
  async function confirm(material: Material) {
    if (busy) return
    setBusy(true); setError('')
    try {
      const result = await request<Material>(`/${material.request_id}/confirm`, { confirm: true })
      setMaterials(previous => previous.map(item => item.request_id === result.request_id ? result : item))
      await refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '绑定失败')
      try { setMaterials((await request<{ materials: Material[] }>()).materials) } catch { /* 保留原始错误 */ }
    } finally { setBusy(false) }
  }
  const changed = () => setRequestId(crypto.randomUUID())
  return <section className="personal-materials">
    <h3>导入已有个人材料</h3>
    <p className="muted">支持UTF-8 Markdown、TXT和代码，最多2 MB。先入库并预览，确认后才绑定与重评；不会自动判断材料质量。</p>
    <div className="task-actions">
      <label htmlFor="material-file">材料文件</label><input id="material-file" type="file" disabled={busy} onChange={event => { setFile(event.target.files?.[0] ?? null); changed() }} />
      <label htmlFor="material-type">材料类型</label><select id="material-type" value={type} disabled={busy} onChange={event => { setType(event.target.value); changed() }}><option value="uploaded_doc">知识笔记与文档</option><option value="repo_artifact">项目产物（含代码）</option></select>
      <label htmlFor="material-capability">你认为相关的能力点</label><select id="material-capability" value={target} disabled={busy} onChange={event => { setTarget(event.target.value); changed() }}>{capabilities.map(node => <option key={node.id} value={node.id}>{node.path}</option>)}</select>
      <label><input type="checkbox" checked={owned} disabled={busy} onChange={event => { setOwned(event.target.checked); changed() }} /> 我声明这是我的个人材料</label>
      {!owned && <p className="muted">未声明归属的材料仍可入库；绑定与评级会受证据闸门限制。</p>}
      <button className="button outline" disabled={busy || !file || !target} onClick={() => void upload()}>{busy ? '处理中…' : '上传并预览绑定'}</button>
    </div>
    {error && <p role="alert">{error}</p>}
    {materials.map(material => <article className="material-preview" key={material.request_id}>
      <h4>{material.filename}</h4><p className="tag">{material.binding_status === 'confirmed' ? '已绑定并重评' : material.binding_status === 'bound_pending_assessment' ? '已绑定，重评待恢复' : '待确认绑定'}</p>
      <p>候选能力：{material.proposal.capability_path}</p><p>类型：{material.evidence_type === 'repo_artifact' ? '项目产物' : '知识文档'} · 归属：{material.attribution === 'user_declared' ? '用户声明' : '未知'} · {material.passage_count} 个原文片段</p>
      <p className="muted">{material.proposal.rationale}</p>
      <details open><summary>核对引用原文（前3个片段）</summary>{material.quotes.map((quote, index) => <div key={index}><blockquote>{quote.text}</blockquote><p className="source-id">定位：{JSON.stringify(quote.locator)}</p></div>)}</details>
      {material.decision && !material.decision.accepted && <p>{material.decision.reject_reason}</p>}
      {material.binding_status === 'confirmed' ? <Link to={`/evidence/${material.capability_id}?goal=${goalId}`}>查看证据与评级</Link>
        : <button className="button outline" disabled={busy} onClick={() => void confirm(material)}>{material.binding_status === 'bound_pending_assessment' ? '恢复重评' : '确认绑定并重评'}</button>}
      <details><summary>追溯材料</summary><p className="source-id">来源：{material.source_id}</p><p className="source-id">主张：{material.proposal.claim_id}</p></details>
    </article>)}
  </section>
}
