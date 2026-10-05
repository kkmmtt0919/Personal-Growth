import { useLayoutEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Capability, Goal, GrowthTask } from '../types/growth'
import { taskHref } from './taskLinks'

function capabilityStatus(item: Capability) {
  if (item.open_gaps.length) return { className: 'gap', label: '待补齐' }
  if (item.understanding === null || item.practice === null) return { className: 'unknown', label: '未评估' }
  return item.understanding >= item.target_level && item.practice >= item.target_level
    ? { className: 'complete', label: '已达标' } : { className: 'gap', label: '待补齐' }
}

export function CapabilityMap({ goal, capabilities, selected, task, onSelect }: {
  goal: Goal; capabilities: Capability[]; selected?: Capability; task?: GrowthTask; onSelect: (id: string) => void
}) {
  const canvasRef = useRef<HTMLDivElement>(null)
  const [lines, setLines] = useState<{ path: string; selected: boolean }[]>([])
  useLayoutEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const update = () => {
      const bounds = canvas.getBoundingClientRect()
      const point = (element: Element, bottom: boolean) => {
        const rect = element.getBoundingClientRect()
        return { x: rect.left - bounds.left + rect.width / 2, y: (bottom ? rect.bottom : rect.top) - bounds.top }
      }
      const connect = (from: Element, to: Element, active: boolean) => {
        const a = point(from, true); const b = point(to, false); const mid = (a.y + b.y) / 2
        return { path: `M ${a.x} ${a.y} V ${mid} H ${b.x} V ${b.y}`, selected: active }
      }
      const result: { path: string; selected: boolean }[] = []
      const root = canvas.querySelector('[data-goal]')
      const selectedNode = canvas.querySelector('[data-selected="true"]')
      if (root) canvas.querySelectorAll('[data-capability]').forEach(node => result.push(connect(root, node, node === selectedNode)))
      if (selectedNode) canvas.querySelectorAll('[data-dimension]').forEach(node => result.push(connect(selectedNode, node, true)))
      const taskNode = canvas.querySelector('[data-task]')
      if (taskNode) canvas.querySelectorAll('[data-dimension]').forEach(node => {
        if (node.getAttribute('data-dimension') === task?.gap?.dimension) result.push(connect(node, taskNode, true))
      })
      setLines(result)
    }
    update()
    const observer = new ResizeObserver(update)
    observer.observe(canvas)
    canvas.querySelectorAll('.map-node').forEach(node => observer.observe(node))
    return () => observer.disconnect()
  }, [capabilities, selected, task])
  return <div className="map-canvas" ref={canvasRef}>
    <svg className="map-lines" aria-hidden="true" width="100%" height="100%">{lines.map((line, index) => <path key={index} d={line.path} className={line.selected ? 'active-line' : ''} />)}</svg>
    <div className="map-node goal-node" data-goal><span className="node-label">GOAL</span><strong>{goal.title}</strong></div>
    {capabilities.length ? <div className="capability-nodes">{capabilities.map(item => {
      const status = capabilityStatus(item)
      return <button key={item.id} className={`map-node skill-node ${selected?.id === item.id ? 'selected' : ''}`} data-capability data-selected={selected?.id === item.id} aria-pressed={selected?.id === item.id} onClick={() => onSelect(item.id)}>
        <span className="node-label">SKILL</span><strong>{item.name}</strong><span className="node-status"><i className={`status-dot ${status.className}`} />{status.label}<span className="selected-label">{selected?.id === item.id ? '已选中' : ''}</span></span>
      </button>
    })}</div> : <p className="map-empty">尚无能力记录，地图将随真实能力数据生成。</p>}
    {selected && <div className="dimension-nodes">{(['understanding', 'practice'] as const).map(dimension => {
      const level = selected[dimension]
      const gap = selected.open_gaps.some(item => item.dimension === dimension) || (level !== null && level < selected.target_level)
      const status = gap ? 'gap' : level === null ? 'unknown' : 'complete'
      return <Link key={dimension} className="map-node evidence-node" data-dimension={dimension} data-gap={gap} to={`/evidence/${encodeURIComponent(selected.id)}`}>
        <span className="node-label">EVIDENCE</span><strong>{dimension === 'understanding' ? '理解证据' : '实践证据'}</strong><span className="node-status"><i className={`status-dot ${status}`} />{gap ? '待补齐' : level === null ? '未评估' : '已达标'}</span>
      </Link>
    })}</div>}
    <div className="task-slot">{task && <Link className="map-node task-node" data-task to={taskHref(goal.id, task.id)}><span className="node-label">TASK / {task.status === 'done' ? '已完成' : task.status === 'abandoned' ? '已放弃' : '关联任务'}</span><strong>{task.title} <span aria-hidden="true">→</span></strong></Link>}</div>
    <p className="map-hint">点击能力节点，查看等级与证据缺口 <span aria-hidden="true">↗</span></p>
  </div>
}
