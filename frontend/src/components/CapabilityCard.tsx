import { Link } from 'react-router-dom'
import type { Capability } from '../types/growth'

export function CapabilityCard({ item }: { item: Capability }) {
  return (
    <article>
      <h2>{item.name}</h2>
      <p>理解 {item.understanding ?? '未评估'} / {item.target_level}</p>
      <p>实践 {item.practice ?? '未评估'} / {item.target_level}</p>
      {item.open_gaps.map((gap) => <p key={gap.dimension}>当前缺口：{gap.dimension} · {gap.severity}</p>)}
      <Link to={`/evidence/${item.id}`}>查看证据</Link>
    </article>
  )
}
