import type { ReturnDemo } from '../types/growth'

export function ReturnSummary({ value }: { value: ReturnDemo | null }) {
  const report = value?.report
  return <section className="return-summary">
    <div className="section-heading"><h2><span className="section-number">03 /</span> 最近变化</h2><span className="muted small">{report ? '欢迎回来' : '成长记录'}</span></div>
    {report ? <>
      <div className="summary-grid">
        <div><h3>发生了什么变化</h3><p className="summary-value">{report.summary.text || '暂无已记录的变化'}</p></div>
        <div><h3>接下来做什么</h3><p>{report.next_step_text || '暂无推荐的下一步'}</p></div>
        <div><h3>记住的学习偏好</h3><p>{report.preference_text || '尚未记录学习偏好'}</p></div>
      </div>
      <details className="summary-sources"><summary>核对这份摘要的来源</summary>
        <p>受控材料与长期偏好；时间模拟为次日。摘要按已有记录生成。</p>
        <p>模拟返回时间：{new Date(report.returned_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}（北京时间）</p>
        <p>前快照：{report.baseline_snapshot_id ?? '未记录'}；后快照：{report.current_snapshot_id}</p>
        {report.summary.changes.map((change) => <p key={change.after_assessment_id}>前评定：{change.before_assessment_id ?? '未记录'}；后评定：{change.after_assessment_id ?? '未记录'}</p>)}
        {report.next_steps.map((step) => <p key={`${step.gap_id}-${step.task_id}`}>缺口：{step.gap_id}；任务：{step.task_id ?? '尚未生成'}</p>)}
        {report.preferences.map((preference) => <p key={preference.memory_id}>偏好记忆：{preference.memory_id}；用户陈述：{preference.source_id}</p>)}
      </details>
    </> : <div className="empty-state"><h3>暂无返回摘要</h3><p>当前场景尚未记录返回后的变化与学习偏好。你仍可以查看能力、证据和关联任务。</p></div>}
  </section>
}
