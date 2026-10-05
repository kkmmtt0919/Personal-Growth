import { Link } from 'react-router-dom'
import type { Evidence } from '../types/growth'

const sourceTypes: Record<string, string> = { repo_artifact: '项目材料', uploaded_doc: '上传文档', task_submission: '任务提交', probe_result: '现场作答' }

export function EvidenceChain({ evidence }: { evidence: Evidence }) {
  return <main>
    <section className="page-hero detail-hero"><div><p className="eyebrow">01 / EVIDENCE EXPLORER</p><h1>{evidence.capability}</h1><p className="lead">为什么是这个等级？从原始证据，读懂评定依据。</p></div><Link className="button outline" to="/#capability-map">返回能力地图 ↗</Link></section>
    <div className="assessment-strip"><span>当前评估</span><div><span className="muted">理解</span><strong>{evidence.assessment.understanding ?? '未评估'}</strong></div><div><span className="muted">实践</span><strong>{evidence.assessment.practice ?? '未评估'}</strong></div></div>
    <section className="evidence-section"><div className="section-heading"><h2><span className="section-number">02 /</span> 等级的证据依据</h2><span className="muted small">{evidence.supports.length} 条支持记录</span></div>
      {evidence.supports.length ? evidence.supports.map((item, index) => <article className="evidence-row" key={item.claim_id}>
        <div className="evidence-meta"><span className="eyebrow">{String(index + 1).padStart(2, '0')} / SOURCE</span><h3>{item.source.name ?? '来源未命名'}</h3><span className="tag">{sourceTypes[item.source.type ?? ''] ?? item.source.type ?? '类型未记录'}</span></div>
        <div className="evidence-body"><p className="eyebrow">证据 → 主张 → 能力 → 评估</p><blockquote>{item.quote.text ?? '暂无原文引用'}</blockquote><h3>评定依据</h3><p>{item.binding_reason.split('理由：').at(-1)}</p><details><summary>核对证据引用</summary><p>主张：{item.claim_id}</p><p>定位：{JSON.stringify(item.quote.locator)}</p><p>{item.binding_reason}</p></details></div>
      </article>) : <div className="empty-state"><h3>尚无支持证据</h3><p>新的证据记录会显示在这里。</p></div>}
    </section>
    <section className="evidence-gaps"><div className="section-heading"><h2><span className="section-number">03 /</span> 尚待补齐</h2></div>{evidence.gaps.length ? evidence.gaps.map(gap => <p key={gap}><i className="status-dot gap" />{gap}</p>) : <p className="muted">暂无已记录的证据缺口。</p>}</section>
  </main>
}
