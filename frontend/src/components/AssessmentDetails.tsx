import type { AssessmentReport } from '../types/growth'

const dimensions: Record<string, string> = { understanding: '理解', practice: '实践' }
const verdicts: Record<string, string> = { sustained: '维持', weakened: '削弱', disputed: '有争议', broken: '已失效' }

export function AssessmentDetails({ report }: { report: AssessmentReport }) {
  return <section className="assessment-details">
    <div className="section-heading"><h2><span className="section-number">04 /</span> 审计与评定详情</h2></div>
    {Object.entries(report.dimensions).map(([name, dimension]) => <article key={name}>
      <h3>{dimensions[name] ?? name}评定依据</h3>
      <p>{dimension.status === 'unassessed' ? '尚无评定结果' : dimension.status === 'insufficient_evidence' ? '现有证据不足以支持等级' : `已评定等级：${dimension.level ?? '未记录'}`}</p>
      <p>{dimension.rationale}</p>
      {dimension.why_not_higher.map((gap, index) => <p className="muted" key={index}>{gap}</p>)}
    </article>)}
    <h3>攻击复核记录</h3>
    <p className="muted">以下为已存储的复核裁决与理由，不代表独立事实，也不由页面触发新攻击。</p>
    {report.attack_reviews.length ? report.attack_reviews.map(review => <details key={review.claim_id}>
      <summary>{review.statement ?? review.claim_id} · {review.attacks.length} 条复核</summary>
      <p className="source-id">主张：{review.claim_id}</p>
      {review.attacks.map((attack, index) => <article key={index}>
        <h4>{verdicts[attack.verdict ?? ''] ?? attack.verdict ?? '裁决未记录'}</h4>
        <p>{attack.question ?? '复核问题未记录'}</p>
        <p>{attack.reasoning ?? '裁决理由未记录'}</p>
        {attack.missing_evidence.map((missing, i) => <p className="muted" key={i}>待补证据：{missing}</p>)}
      </article>)}
    </details>) : <p className="muted">暂无已记录的攻击复核，不能据此认定证据已通过攻击。</p>}
    <h3>反向证据</h3>
    {report.reverse_evidence.length ? report.reverse_evidence.map((item, index) => <article key={index}>
      <p>{dimensions[item.dimension] ?? item.dimension} · 主张 {item.claim_id}{item.cap != null ? ` · 等级上限 ${item.cap}` : ''}</p>
      {item.refuting_evidence.map((refute, i) => <div key={i}><blockquote>{refute.quote ?? '反向原文未记录'}</blockquote><p>{refute.reasoning}</p><p className="source-id">段落：{refute.passage_id}</p></div>)}
    </article>) : <p className="muted">暂无已纳入评定的反向证据。</p>}
    <h3>已排除的证据</h3>
    {report.excluded.length ? report.excluded.map(item => <article key={item.claim_id}><p className="source-id">主张：{item.claim_id}</p><p>{item.reason ?? '排除理由未记录'}</p><p className="muted">影响维度：{item.dimensions.map(d => dimensions[d] ?? d).join('、')}</p></article>) : <p className="muted">暂无已记录的排除项。</p>}
    <details><summary>规则版本与报告局限</summary><p>规则版本：{report.rule_version}</p>{report.limitations.map(text => <p key={text}>{text}</p>)}</details>
  </section>
}
