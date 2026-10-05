import type { Evidence } from '../types/growth'

export function EvidenceChain({ evidence }: { evidence: Evidence }) {
  return (
    <section>
      <h1>为什么是这个等级：{evidence.capability}</h1>
      <p>理解 {evidence.assessment.understanding ?? '未评估'} · 实践 {evidence.assessment.practice ?? '未评估'}</p>
      {evidence.supports.map((item) => (
        <article key={item.claim_id}>
          <h2>证据 → 主张 → 能力 → 评估</h2>
          <p>来源：{item.source.name}（{item.source.type}）</p>
          <blockquote>{item.quote.text}</blockquote>
          <p>绑定理由：{item.binding_reason}</p>
        </article>
      ))}
      {evidence.gaps.map((gap) => <p key={gap}>不足：{gap}</p>)}
    </section>
  )
}
