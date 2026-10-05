import { useEffect } from 'react'
import type { GrowthTask } from '../types/growth'
import { Link, useLocation } from 'react-router-dom'
import { taskAnchor } from './taskLinks'

const statuses: Record<string, string> = { proposed: '待确认', active: '进行中', blocked: '受阻', done: '已完成', abandoned: '已放弃' }

export function TaskTimeline({ tasks }: { tasks: GrowthTask[] }) {
  const { hash } = useLocation()
  useEffect(() => {
    if (!hash) return
    let id: string
    try { id = decodeURIComponent(hash.slice(1)) } catch { return }
    const target = document.getElementById(id)
    if (target) { target.scrollIntoView({ block: 'start' }); target.focus({ preventScroll: true }) }
  }, [hash, tasks])
  return <main>
    <section className="page-hero detail-hero"><div><p className="eyebrow">01 / GROWTH LOOP</p><h1>让下一步，有据可循。</h1><p className="lead">从证据缺口生成任务，通过提交与重评验证成长。</p></div><Link className="button outline" to="/#capability-map">返回能力地图 ↗</Link></section>
    <div className="section-heading"><h2><span className="section-number">02 /</span> 成长任务</h2><span className="muted small">{tasks.length} 项任务</span></div>
    {tasks.length ? tasks.map((task, index) => <article className="task-article" key={task.id} id={taskAnchor(task.id)} tabIndex={-1}>
      <div className="task-heading"><div><p className="eyebrow">TASK / {String(index + 1).padStart(2, '0')}</p><h2>{task.title}</h2></div><span className={`tag ${task.status === 'done' ? 'tag-complete' : ''}`}>{statuses[task.status] ?? task.status}</span></div>
      <div className="task-gap"><span className="eyebrow">证据缺口</span><p>{task.gap ? <>{task.gap.rationale} <span className="tag">{task.gap.status === 'closed' ? '已补齐' : '待补齐'}</span></> : '暂无已关联的证据缺口。'}</p></div>
      <div className="task-stages">
        <div className="task-stage"><div className="stage-label"><span className="stage-number">01</span><h3>任务</h3></div><h4>交付目标</h4><p>{task.objective}</p><h4>验收标准</h4><p>{task.acceptance}</p></div>
        <div className="task-stage"><div className="stage-label"><span className={`stage-number ${task.submissions.length ? 'stage-complete' : ''}`}>02</span><h3>提交</h3></div><h4>{task.submissions.length ? '已记录的提交' : '等待提交'}</h4>{task.submissions.length ? <details open><summary>{task.submissions.length} 条提交记录</summary>{task.submissions.map((item, submissionIndex) => <p className="source-id" key={`${item.source_id}-${submissionIndex}`}>{item.source_id}</p>)}</details> : <p className="muted">尚未提交。新证据记录后，会显示在此阶段。</p>}</div>
        <div className="task-stage"><div className="stage-label"><span className={`stage-number ${task.attribution ? 'stage-complete' : ''}`}>03</span><h3>重评</h3></div>{task.attribution ? <><h4>实践等级变化</h4><p className="level-change">{task.attribution.before.practice.level ?? '未评估'} <span>→</span> {task.attribution.after.practice.level ?? '未评估'}</p><p className="muted">归因链{Object.values(task.attribution.guard).every(Boolean) ? '完整' : '待核对'}</p><details><summary>核对归因检查</summary>{Object.entries(task.attribution.guard).map(([name, passed]) => <p key={name}>{name}：{passed ? '通过' : '待核对'}</p>)}</details></> : <><h4>等待重评</h4><p className="muted">等级由新证据重评产生，任务完成本身不代表等级提升。</p></>}</div>
      </div>
      <Link className="text-link" to={`/evidence/${encodeURIComponent(task.capability_id)}`}>查看等级依据 →</Link>
    </article>) : <div className="empty-state"><h3>暂无成长任务</h3><p>当前场景尚未生成任务，可以先查看能力与证据缺口。</p></div>}
  </main>
}
