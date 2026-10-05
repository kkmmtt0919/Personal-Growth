import type { GrowthTask } from '../types/growth'

export function TaskTimeline({ tasks }: { tasks: GrowthTask[] }) {
  return (
    <section>
      <h1>基于当前证据缺口生成任务</h1>
      {tasks.map((task) => (
        <article key={task.id}>
          <h2>{task.title}</h2>
          <p>状态：{task.status}</p>
          <p>提交：{task.submissions.map((item) => item.source_id).join(', ') || '尚未提交'}</p>
        </article>
      ))}
    </section>
  )
}
