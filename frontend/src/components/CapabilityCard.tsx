import { Link } from 'react-router-dom'
import type { Capability, GrowthTask } from '../types/growth'
import { taskHref } from './taskLinks'

const dimensions: Record<string, string> = { understanding: '理解', practice: '实践' }
const gaps: Record<string, string> = { evidence_gap: '缺少可核验证据', level_gap_1: '距目标差 1 级', level_gap_2plus: '距目标差至少 2 级' }

export function CapabilityCard({ item, task, goalId }: { item: Capability; task?: GrowthTask; goalId: string }) {
  return <div className="capability-detail">
    <p className="eyebrow">SELECTED CAPABILITY</p><h2 aria-live="polite">{item.name}</h2>
    <div className="level-meters">{(['understanding', 'practice'] as const).map(dimension => {
      const level = item[dimension]
      return <div className={`level-meter ${dimension}`} key={dimension}><div className="meter-label"><strong>{dimensions[dimension]}</strong><span>{level ?? '未评估'} / {item.target_level}</span></div><div className="meter-track" role={level === null ? undefined : 'meter'} aria-label={dimensions[dimension]} aria-valuemin={0} aria-valuemax={item.target_level} aria-valuenow={level ?? undefined}><span style={{ width: `${level === null || item.target_level <= 0 ? 0 : Math.min(100, Math.max(0, level / item.target_level * 100))}%` }} /></div></div>
    })}</div>
    <div className="gap-detail"><h3>当前缺口</h3>{item.open_gaps.length ? item.open_gaps.map(gap => <p key={`${gap.dimension}-${gap.severity}`}>{dimensions[gap.dimension] ?? gap.dimension} · {gaps[gap.severity] ?? gap.severity}</p>) : <p>{item.understanding === null || item.practice === null ? '尚未完成评估，暂无已记录的证据缺口。' : '暂无已记录的证据缺口。'}</p>}</div>
    {task ? <Link className="button primary" to={taskHref(goalId, task.id)}>查看关联任务 <span aria-hidden="true">↗</span></Link> : <p className="muted no-task">尚未生成关联任务</p>}
    <Link className="text-link" to={`/evidence/${encodeURIComponent(item.id)}`}>查看证据 <span aria-hidden="true">→</span></Link>
  </div>
}
